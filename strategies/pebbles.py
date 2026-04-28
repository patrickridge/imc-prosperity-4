"""A fast-adaptive rank-pair relative-value strategy over the five PEBBLES.
It uses S in the family signal despite S being noisy, because the pair engine benefits from the full family structure.
The alpha comes from trading temporary residual dislocations, with XL as the dominant profit source.
v3 fast-adapt is currently the strongest PEBBLES version, 
but its main weakness is that it can build full-size positions in products that look cheap on a fast residual z-score while they are still trending away from the family. 
This shows up most clearly in PEBBLES_S: the strategy may buy S up to the 10-lot limit because it appears cheap relative to its recent family baseline, 
but S can continue weakening for a while, causing an ugly standalone drawdown before the pair eventually unwinds.

The important caveat is that this does not necessarily mean the trade is bad overall. 
In many cases, the S leg is paired against a more profitable rich-side short, especially involving XL. 
Attempts to mechanically block, cap, or replace S trades reduced total PnL because they disrupted the profitable pair structure. 
So S should not simply be removed or shorted independently.

The next improvement should focus on trade-level diagnostics rather than product-level PnL. 
Specifically, log each pair entry with rich product, cheap product, z-gap, entry timestamp, exit timestamp, and realised pair PnL. 
Then identify whether long-S losses are genuinely bad trades or just the losing leg of profitable pairs. 
Only after that should we add a more precise S rule, such as limiting repeated long-S re-entries after a failed S pair, rather than globally blocking S longs."""




from __future__ import annotations

import json
import math
from typing import Any, Dict, List, Optional, Tuple

try:
    from datamodel import Order, OrderDepth, TradingState
except Exception:
    class Order:  # type: ignore
        def __init__(self, symbol: str, price: int, quantity: int):
            self.symbol = symbol
            self.price = price
            self.quantity = quantity

    class OrderDepth:  # type: ignore
        buy_orders: Dict[int, int]
        sell_orders: Dict[int, int]

    class TradingState:  # type: ignore
        traderData: str
        timestamp: int
        order_depths: Dict[str, OrderDepth]
        position: Dict[str, int]


class Trader:
    """Round 5 PEBBLES family-rotation trader.

    Compact/live-safe implementation: stores EWMA residual mean/variance instead
    of 500-point histories in traderData.

    Variant: v3 fast-adapt: shorter baseline for intraday regime shifts
    """

    PEBBLES = [
        "PEBBLES_XS",
        "PEBBLES_S",
        "PEBBLES_M",
        "PEBBLES_L",
        "PEBBLES_XL",
    ]

    POSITION_LIMITS = {p: 10 for p in PEBBLES}

    # --- signal / warmup ---
    ROLLING_WINDOW = 300
    MIN_OBS = 20
    EMA_ALPHA = 2.0 / (ROLLING_WINDOW + 1.0)
    MIN_RESID_STD = 1.0

    # --- entry / exit ---
    ENTRY_Z = 1.55
    EXIT_Z = 0.25
    PAIR_GAP_Z = 2.35
    AGGRESSIVE_Z = 2.3

    # --- sizing ---
    BASE_QTY = 5
    MAX_STEP_QTY = 10
    EXIT_STEP_QTY = 10
    MAX_PRODUCT_ABS_POS_FRAC = 1.0
    MAX_FAMILY_GROSS_FRAC = 3.5
    XL_RISK_MULT = 0.95
    XS_RISK_MULT = 0.95

    # --- risk controls ---
    FAMILY_ANCHOR = 10000.0
    FAMILY_HALF_SIZE_DEVIATION = 30.0
    FAMILY_NO_OPEN_DEVIATION = 60.0
    COOLDOWN_TICKS = 25

    STUCK_WINDOW = 250
    STUCK_FRAC = 0.75
    FORCE_EXIT_FRAC = 0.25

    STOP_Z = 1.1
    HARD_STOP_Z = 1.9

    DEBUG = False

    def run(self, state: TradingState):
        data = self._load_trader_data(getattr(state, "traderData", ""))
        orders: Dict[str, List[Order]] = {}
        peb_orders = self.trade_pebbles(state, data)
        for p, os in peb_orders.items():
            if os:
                orders[p] = os
        return orders, 0, self._dump_trader_data(data)

    def trade_pebbles(self, state: TradingState, data: Dict[str, Any]) -> Dict[str, List[Order]]:
        result: Dict[str, List[Order]] = {p: [] for p in self.PEBBLES}
        peb = data.setdefault("p", self._default_state())
        self._ensure_state(peb)

        timestamp = int(getattr(state, "timestamp", 0))
        positions = getattr(state, "position", {}) or {}

        books: Dict[str, OrderDepth] = {}
        mids: Dict[str, float] = {}
        for p in self.PEBBLES:
            od = state.order_depths.get(p)
            if od is None:
                return result
            bbba = self.best_bid_ask(od)
            if bbba is None:
                return result
            bid, ask = bbba
            books[p] = od
            mids[p] = 0.5 * (bid + ask)

        family_mid = sum(mids.values()) / len(self.PEBBLES)

        z: Dict[str, Optional[float]] = {}
        residuals: Dict[str, float] = {}
        for p in self.PEBBLES:
            resid = mids[p] - family_mid
            residuals[p] = resid
            n = int(peb["n"].get(p, 0))
            ema = peb["e"].get(p)
            var = peb["v"].get(p)
            if ema is None or var is None or n < self.MIN_OBS:
                z[p] = None
            else:
                std = math.sqrt(max(float(var), self.MIN_RESID_STD * self.MIN_RESID_STD))
                z[p] = (resid - float(ema)) / std

        for p in self.PEBBLES:
            self._update_signal_state(peb, p, residuals[p])
            self._update_stuck_state(peb, p, int(positions.get(p, 0)), timestamp)

        if any(z[p] is None for p in self.PEBBLES):
            return result
        zz = {p: float(z[p]) for p in self.PEBBLES}

        did_risk_reduce = self._pair_stop_logic(result, books, zz, peb, positions, timestamp)
        self._mean_reversion_exits(result, books, zz, positions)
        self._stuck_position_exits(result, books, peb, positions, timestamp)

        if not did_risk_reduce:
            self._rank_pair_entry(result, books, zz, peb, positions, family_mid, timestamp)

        if self.DEBUG and timestamp % 2500 == 0:
            rich = max(self.PEBBLES, key=lambda p: zz[p])
            cheap = min(self.PEBBLES, key=lambda p: zz[p])
            print("PEBBLES", timestamp, "fam", round(family_mid, 2), rich, round(zz[rich], 2), cheap, round(zz[cheap], 2))

        return result

    def _rank_pair_entry(
        self,
        result: Dict[str, List[Order]],
        books: Dict[str, OrderDepth],
        z: Dict[str, float],
        peb: Dict[str, Any],
        positions: Dict[str, int],
        family_mid: float,
        timestamp: int,
    ) -> None:
        rich = max(self.PEBBLES, key=lambda p: z[p])
        cheap = min(self.PEBBLES, key=lambda p: z[p])
        if rich == cheap:
            return
        rich_z = z[rich]
        cheap_z = z[cheap]
        gap_z = rich_z - cheap_z

        if rich_z <= self.ENTRY_Z or cheap_z >= -self.ENTRY_Z or gap_z <= self.PAIR_GAP_Z:
            return
        if timestamp < int(peb["cd"].get(rich, 0)) or timestamp < int(peb["cd"].get(cheap, 0)):
            return

        fam_dev = abs(family_mid - self.FAMILY_ANCHOR)
        if fam_dev > self.FAMILY_NO_OPEN_DEVIATION:
            return
        family_size_mult = 0.5 if fam_dev > self.FAMILY_HALF_SIZE_DEVIATION else 1.0

        q = self.size_from_gap(gap_z)
        q = int(math.floor(q * family_size_mult))
        q = self._apply_pair_risk_multiplier(q, rich, cheap)
        q = self._cap_pair_quantity(q, rich, cheap, positions)
        if q <= 0:
            return

        aggressive = gap_z >= self.AGGRESSIVE_Z
        if aggressive:
            cheap_bbba = self.best_bid_ask(books[cheap])
            rich_bbba = self.best_bid_ask(books[rich])
            if cheap_bbba is None or rich_bbba is None:
                return
            _, cheap_ask = cheap_bbba
            rich_bid, _ = rich_bbba
            ask_liq = abs(int(books[cheap].sell_orders.get(cheap_ask, 0)))
            bid_liq = abs(int(books[rich].buy_orders.get(rich_bid, 0)))
            q = min(q, ask_liq, bid_liq)
        if q <= 0:
            return

        self._sell(result, rich, books[rich], q, aggressive)
        self._buy(result, cheap, books[cheap], q, aggressive)

        peb["s"][rich] = -1
        peb["s"][cheap] = 1
        peb["lp"] = {"r": rich, "c": cheap, "g": round(float(gap_z), 4), "t": int(timestamp)}

    def _mean_reversion_exits(
        self,
        result: Dict[str, List[Order]],
        books: Dict[str, OrderDepth],
        z: Dict[str, float],
        positions: Dict[str, int],
    ) -> None:
        for p in self.PEBBLES:
            pos = int(positions.get(p, 0))
            if pos > 0 and z[p] > -self.EXIT_Z:
                self._sell(result, p, books[p], min(abs(pos), self.EXIT_STEP_QTY), aggressive=False)
            elif pos < 0 and z[p] < self.EXIT_Z:
                self._buy(result, p, books[p], min(abs(pos), self.EXIT_STEP_QTY), aggressive=False)

    def _pair_stop_logic(
        self,
        result: Dict[str, List[Order]],
        books: Dict[str, OrderDepth],
        z: Dict[str, float],
        peb: Dict[str, Any],
        positions: Dict[str, int],
        timestamp: int,
    ) -> bool:
        pair = peb.get("lp") or {}
        rich = pair.get("r")
        cheap = pair.get("c")
        if rich not in self.PEBBLES or cheap not in self.PEBBLES:
            return False

        rich_pos = int(positions.get(rich, 0))
        cheap_pos = int(positions.get(cheap, 0))
        if rich_pos >= 0 or cheap_pos <= 0:
            peb["lp"] = None
            return False

        entry_gap = float(pair.get("g", 0.0))
        adverse = (z[rich] - z[cheap]) - entry_gap
        if adverse <= self.STOP_Z:
            return False

        pair_abs = min(abs(rich_pos), abs(cheap_pos))
        if pair_abs <= 0:
            return False
        full_exit = adverse >= self.HARD_STOP_Z
        q = min(pair_abs, self.MAX_STEP_QTY)
        if not full_exit:
            q = max(1, q // 2)

        self._buy(result, rich, books[rich], q, aggressive=full_exit)
        self._sell(result, cheap, books[cheap], q, aggressive=full_exit)
        if full_exit:
            peb["cd"][rich] = timestamp + self.COOLDOWN_TICKS
            peb["cd"][cheap] = timestamp + self.COOLDOWN_TICKS
            peb["lp"] = None
        return True

    def _stuck_position_exits(
        self,
        result: Dict[str, List[Order]],
        books: Dict[str, OrderDepth],
        peb: Dict[str, Any],
        positions: Dict[str, int],
        timestamp: int,
    ) -> None:
        for p in self.PEBBLES:
            pos = int(positions.get(p, 0))
            stuck_since = peb["st"].get(p)
            if stuck_since is None:
                continue
            if abs(pos) <= int(self.STUCK_FRAC * self.POSITION_LIMITS[p]):
                continue
            if timestamp - int(stuck_since) < self.STUCK_WINDOW:
                continue
            q = max(1, min(self.MAX_STEP_QTY, int(abs(pos) * self.FORCE_EXIT_FRAC)))
            if pos > 0:
                self._sell(result, p, books[p], q, aggressive=False)
            elif pos < 0:
                self._buy(result, p, books[p], q, aggressive=False)
            peb["cd"][p] = timestamp + self.COOLDOWN_TICKS
            peb["st"][p] = timestamp

    def _buy(self, result: Dict[str, List[Order]], product: str, od: OrderDepth, qty: int, aggressive: bool) -> None:
        if qty <= 0:
            return
        bbba = self.best_bid_ask(od)
        if bbba is None:
            return
        best_bid, best_ask = bbba
        if aggressive:
            price = best_ask
        else:
            price = best_bid + 1
            if price >= best_ask:
                price = best_bid
        result[product].append(Order(product, int(price), int(qty)))

    def _sell(self, result: Dict[str, List[Order]], product: str, od: OrderDepth, qty: int, aggressive: bool) -> None:
        if qty <= 0:
            return
        bbba = self.best_bid_ask(od)
        if bbba is None:
            return
        best_bid, best_ask = bbba
        if aggressive:
            price = best_bid
        else:
            price = best_ask - 1
            if price <= best_bid:
                price = best_ask
        result[product].append(Order(product, int(price), -int(qty)))

    @staticmethod
    def best_bid_ask(od: OrderDepth) -> Optional[Tuple[int, int]]:
        if od is None or not getattr(od, "buy_orders", None) or not getattr(od, "sell_orders", None):
            return None
        return int(max(od.buy_orders.keys())), int(min(od.sell_orders.keys()))

    def size_from_gap(self, gap_z: float) -> int:
        excess = max(0.0, gap_z - self.PAIR_GAP_Z)
        return min(self.MAX_STEP_QTY, self.BASE_QTY + int(3.0 * excess))

    def _apply_pair_risk_multiplier(self, q: int, rich: str, cheap: str) -> int:
        mult = 1.0
        for p in (rich, cheap):
            if p == "PEBBLES_XL":
                mult = min(mult, self.XL_RISK_MULT)
            elif p == "PEBBLES_XS":
                mult = min(mult, self.XS_RISK_MULT)
        return int(math.floor(q * mult))

    def _cap_pair_quantity(self, q: int, rich: str, cheap: str, positions: Dict[str, int]) -> int:
        if q <= 0:
            return 0
        rich_pos = int(positions.get(rich, 0))
        cheap_pos = int(positions.get(cheap, 0))
        rich_limit = self.POSITION_LIMITS[rich]
        cheap_limit = self.POSITION_LIMITS[cheap]
        rich_cap = int(rich_limit * self.MAX_PRODUCT_ABS_POS_FRAC)
        cheap_cap = int(cheap_limit * self.MAX_PRODUCT_ABS_POS_FRAC)

        # sell rich / buy cheap rooms
        q = min(q, rich_cap + rich_pos, cheap_cap - cheap_pos)
        q = min(q, rich_limit + rich_pos, cheap_limit - cheap_pos)

        max_gross = int(self.MAX_FAMILY_GROSS_FRAC * max(self.POSITION_LIMITS.values()))
        gross_now = sum(abs(int(positions.get(p, 0))) for p in self.PEBBLES)
        gross_room = max(0, max_gross - gross_now)
        q = min(q, gross_room // 2 if gross_room > 0 else 0)
        return max(0, int(q))

    def _default_state(self) -> Dict[str, Any]:
        return {
            "e": {p: None for p in self.PEBBLES},       # residual EWMA mean
            "v": {p: None for p in self.PEBBLES},       # residual EWMA variance
            "n": {p: 0 for p in self.PEBBLES},          # observation count
            "cd": {p: 0 for p in self.PEBBLES},         # cooldown until timestamp
            "s": {p: 0 for p in self.PEBBLES},          # last signal
            "st": {p: None for p in self.PEBBLES},      # stuck since timestamp
            "lp": None,                                  # last active pair
        }

    def _ensure_state(self, peb: Dict[str, Any]) -> None:
        default = self._default_state()
        for key, val in default.items():
            if key not in peb:
                peb[key] = val
        for key in ["e", "v", "n", "cd", "s", "st"]:
            if not isinstance(peb.get(key), dict):
                peb[key] = default[key]
            for p in self.PEBBLES:
                if p not in peb[key]:
                    peb[key][p] = default[key][p]

    def _update_signal_state(self, peb: Dict[str, Any], product: str, resid: float) -> None:
        old_ema = peb["e"].get(product)
        old_var = peb["v"].get(product)
        n = int(peb["n"].get(product, 0))

        if old_ema is None or old_var is None or n <= 0:
            new_ema = float(resid)
            new_var = self.MIN_RESID_STD * self.MIN_RESID_STD
        else:
            old_ema_f = float(old_ema)
            old_var_f = max(float(old_var), self.MIN_RESID_STD * self.MIN_RESID_STD)
            diff = float(resid) - old_ema_f
            a = self.EMA_ALPHA
            new_ema = old_ema_f + a * diff
            # Stable EWMA variance update around the old mean.
            new_var = (1.0 - a) * (old_var_f + a * diff * diff)

        peb["e"][product] = round(float(new_ema), 5)
        peb["v"][product] = round(float(max(new_var, self.MIN_RESID_STD * self.MIN_RESID_STD)), 5)
        peb["n"][product] = min(n + 1, 1000000)

    def _update_stuck_state(self, peb: Dict[str, Any], product: str, pos: int, timestamp: int) -> None:
        threshold = int(self.STUCK_FRAC * self.POSITION_LIMITS[product])
        if abs(int(pos)) > threshold:
            if peb["st"].get(product) is None:
                peb["st"][product] = int(timestamp)
        else:
            peb["st"][product] = None

    def _load_trader_data(self, trader_data: str) -> Dict[str, Any]:
        if not trader_data:
            return {}
        try:
            obj = json.loads(trader_data)
            if isinstance(obj, dict):
                return obj
        except Exception:
            pass
        return {}

    def _dump_trader_data(self, data: Dict[str, Any]) -> str:
        try:
            return json.dumps(data, separators=(",", ":"))
        except Exception:
            return "{}"
