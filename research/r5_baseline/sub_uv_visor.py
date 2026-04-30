from typing import Dict, List, Optional, Tuple
import jsonpickle
import math


UV_RED = "UV_VISOR_RED"
UV_AMBER = "UV_VISOR_AMBER"
UV_MAGENTA = "UV_VISOR_MAGENTA"
UV_ORANGE = "UV_VISOR_ORANGE"
UV_YELLOW = "UV_VISOR_YELLOW"

# We deliberately do not trade YELLOW. It was unstable historically.
UV_PRODUCTS = [UV_RED, UV_AMBER, UV_MAGENTA, UV_ORANGE]


class Trader:
    """
    Round 5 UV_VISOR strategy: RA core + independent MO overlay.

    Core alpha:
        LONG  UV_VISOR_RED
        SHORT UV_VISOR_AMBER

    Optional independent overlay:
        LONG  UV_VISOR_MAGENTA
        SHORT UV_VISOR_ORANGE

    Rationale:
        - RA was the cleanest UV spread and should keep full priority.
        - MO does not use RED or AMBER capacity, so it can be tested as an overlay
          without weakening the confirmed RA edge.
        - YELLOW stays disabled because it broke badly on day 4 historically.

    Position limits are the official UV limits supplied by the user: 10 each.
    """

    LIMITS: Dict[str, int] = {
        UV_RED: 10,
        UV_AMBER: 10,
        UV_MAGENTA: 10,
        UV_ORANGE: 10,
    }

    # Shared EMA trend parameters.
    FAST_WINDOW = 100
    SLOW_WINDOW = 800
    VOL_WINDOW = 500
    VOL_MULT = 8.0
    MIN_DENOM = 50.0

    # RA: confirmed best leg. Keep it unchanged versus the RA-only winner.
    ENTRY_RAW_RA = 80.0
    ENTRY_SCORE_RA = 1.0
    EXIT_RAW_RA = -10_000.0
    EXIT_SCORE_RA = -10_000.0
    TRAILING_STOP_RA = 1500.0
    TARGET_RED = 10
    TARGET_AMBER = -10

    # MO: weaker independent overlay. Smaller size and slightly easier raw threshold,
    # because MAGENTA-ORANGE has a smaller absolute spread move than RED-AMBER.
    ENTRY_RAW_MO = 45.0
    ENTRY_SCORE_MO = 0.8
    EXIT_RAW_MO = -10_000.0
    EXIT_SCORE_MO = -10_000.0
    TRAILING_STOP_MO = 1000.0
    TARGET_MAGENTA = 3
    TARGET_ORANGE = -3

    # Execution controls.
    FILTER_VOL = 8
    AGGRESSIVE_URGENCY = 0.20
    MAX_CROSS_SLIP = {
        UV_RED: 10,
        UV_AMBER: 10,
        UV_MAGENTA: 10,
        UV_ORANGE: 10,
    }
    MAX_SPREAD = {
        UV_RED: 22,
        UV_AMBER: 18,
        UV_MAGENTA: 24,
        UV_ORANGE: 22,
    }

    def run(self, state: TradingState):
        self.data = jsonpickle.decode(state.traderData) if state.traderData else {}
        if not isinstance(self.data, dict):
            self.data = {}

        result: Dict[str, List[Order]] = {}
        uv_orders = self.trade_uv_visor(state)
        for product, orders in uv_orders.items():
            if orders:
                result.setdefault(product, []).extend(orders)

        conversions = 0
        trader_data = jsonpickle.encode(self.data)
        return result, conversions, trader_data

    # -----------------
    # Book helpers
    # -----------------

    def best_bid_ask(self, od: OrderDepth) -> Tuple[Optional[int], Optional[int]]:
        best_bid = max(od.buy_orders.keys()) if od.buy_orders else None
        best_ask = min(od.sell_orders.keys()) if od.sell_orders else None
        return best_bid, best_ask

    def filtered_mid(self, od: OrderDepth, min_vol: int = FILTER_VOL) -> Optional[float]:
        if not od.buy_orders or not od.sell_orders:
            return None

        bid_levels = [(p, v) for p, v in od.buy_orders.items() if v >= min_vol]
        ask_levels = [(p, -v) for p, v in od.sell_orders.items() if -v >= min_vol]

        bid = max(p for p, _ in bid_levels) if bid_levels else max(od.buy_orders.keys())
        ask = min(p for p, _ in ask_levels) if ask_levels else min(od.sell_orders.keys())
        return (bid + ask) / 2.0

    def book_ok(self, product: str, od: OrderDepth) -> bool:
        bid, ask = self.best_bid_ask(od)
        if bid is None or ask is None:
            return False
        return (ask - bid) <= self.MAX_SPREAD.get(product, 999999)

    @staticmethod
    def ema_update(prev: Optional[float], x: float, window: int) -> float:
        alpha = 2.0 / (window + 1.0)
        if prev is None:
            return x
        return alpha * x + (1.0 - alpha) * prev

    # -----------------
    # Signal helpers
    # -----------------

    def update_pair_state(self, st: Dict, name: str, spread: float) -> Tuple[float, float]:
        prev_key = f"prev_spread_{name}"
        fast_key = f"ema_fast_{name}"
        slow_key = f"ema_slow_{name}"
        vol_key = f"ema_abs_d_{name}"

        prev_spread = st.get(prev_key)
        dspread = 0.0 if prev_spread is None else spread - prev_spread

        st[fast_key] = self.ema_update(st.get(fast_key), spread, self.FAST_WINDOW)
        st[slow_key] = self.ema_update(st.get(slow_key), spread, self.SLOW_WINDOW)
        st[vol_key] = self.ema_update(st.get(vol_key), abs(dspread), self.VOL_WINDOW)
        st[prev_key] = spread

        trend_raw = st[fast_key] - st[slow_key]
        trend_score = trend_raw / max(st[vol_key] * self.VOL_MULT, self.MIN_DENOM)
        return trend_raw, trend_score

    def update_signal_machine(
        self,
        st: Dict,
        name: str,
        spread: float,
        trend_raw: float,
        trend_score: float,
        entry_raw: float,
        entry_score: float,
        exit_raw: float,
        exit_score: float,
        trailing_stop: float,
        active_state_name: str,
    ) -> None:
        state_key = f"state_{name}"
        peak_key = f"peak_spread_{name}"
        ticks_key = f"ticks_in_{name}"

        current_state = st.get(state_key, "NEUTRAL")

        if current_state == "NEUTRAL":
            if trend_raw > entry_raw and trend_score > entry_score:
                st[state_key] = active_state_name
                st[peak_key] = spread
                st[ticks_key] = 0
            return

        st[ticks_key] = st.get(ticks_key, 0) + 1
        st[peak_key] = max(st.get(peak_key, spread), spread)

        trailing_hit = st[peak_key] - spread > trailing_stop
        trend_exit = trend_raw < exit_raw or trend_score < exit_score

        if trailing_hit or trend_exit:
            st[state_key] = "NEUTRAL"
            st[peak_key] = None
            st[ticks_key] = 0

    # -----------------
    # Execution helpers
    # -----------------

    def urgency(self, current_pos: int, target_pos: int, limit: int) -> float:
        gap = abs(target_pos - current_pos)
        return min(1.0, gap / max(1.0, 0.5 * limit))

    def buy_towards(self, product: str, od: OrderDepth, qty: int, fair: float, urgent: float) -> List[Order]:
        orders: List[Order] = []
        best_bid, best_ask = self.best_bid_ask(od)
        if best_bid is None or best_ask is None or qty <= 0:
            return orders

        if urgent >= self.AGGRESSIVE_URGENCY and best_ask <= fair + self.MAX_CROSS_SLIP.get(product, 10):
            take_qty = min(qty, -od.sell_orders.get(best_ask, 0))
            if take_qty > 0:
                orders.append(Order(product, best_ask, take_qty))
                qty -= take_qty

        if qty > 0:
            px = min(best_bid + 1, int(math.floor(fair)))
            orders.append(Order(product, px, qty))

        return orders

    def sell_towards(self, product: str, od: OrderDepth, qty: int, fair: float, urgent: float) -> List[Order]:
        orders: List[Order] = []
        best_bid, best_ask = self.best_bid_ask(od)
        if best_bid is None or best_ask is None or qty <= 0:
            return orders

        if urgent >= self.AGGRESSIVE_URGENCY and best_bid >= fair - self.MAX_CROSS_SLIP.get(product, 10):
            take_qty = min(qty, od.buy_orders.get(best_bid, 0))
            if take_qty > 0:
                orders.append(Order(product, best_bid, -take_qty))
                qty -= take_qty

        if qty > 0:
            px = max(best_ask - 1, int(math.ceil(fair)))
            orders.append(Order(product, px, -qty))

        return orders

    def trade_towards_target(
        self,
        product: str,
        od: OrderDepth,
        current_pos: int,
        target_pos: int,
        fair: float,
        limit: int,
    ) -> List[Order]:
        target_pos = max(-limit, min(limit, target_pos))
        urgent = self.urgency(current_pos, target_pos, limit)

        if target_pos > current_pos:
            qty = min(target_pos - current_pos, limit - current_pos)
            return self.buy_towards(product, od, qty, fair, urgent)

        if target_pos < current_pos:
            qty = min(current_pos - target_pos, limit + current_pos)
            return self.sell_towards(product, od, qty, fair, urgent)

        return []

    # -----------------
    # Main UV routine
    # -----------------

    def trade_uv_visor(self, state: TradingState) -> Dict[str, List[Order]]:
        result: Dict[str, List[Order]] = {p: [] for p in UV_PRODUCTS if p in state.order_depths}

        # RA is mandatory. If missing either leg, do nothing.
        if UV_RED not in state.order_depths or UV_AMBER not in state.order_depths:
            return result

        st = self.data.setdefault("uv_ra_plus_mo", {})

        mids: Dict[str, float] = {}
        for product in UV_PRODUCTS:
            if product not in state.order_depths:
                continue
            mid = self.filtered_mid(state.order_depths[product], self.FILTER_VOL)
            if mid is not None:
                mids[product] = mid

        if UV_RED not in mids or UV_AMBER not in mids:
            return result

        # 1. RA core signal.
        spread_ra = mids[UV_RED] - mids[UV_AMBER]
        trend_raw_ra, trend_score_ra = self.update_pair_state(st, "RA", spread_ra)
        self.update_signal_machine(
            st=st,
            name="RA",
            spread=spread_ra,
            trend_raw=trend_raw_ra,
            trend_score=trend_score_ra,
            entry_raw=self.ENTRY_RAW_RA,
            entry_score=self.ENTRY_SCORE_RA,
            exit_raw=self.EXIT_RAW_RA,
            exit_score=self.EXIT_SCORE_RA,
            trailing_stop=self.TRAILING_STOP_RA,
            active_state_name="LONG_RED_SHORT_AMBER",
        )

        # 2. MO independent overlay signal, only if both legs exist.
        if UV_MAGENTA in mids and UV_ORANGE in mids:
            spread_mo = mids[UV_MAGENTA] - mids[UV_ORANGE]
            trend_raw_mo, trend_score_mo = self.update_pair_state(st, "MO", spread_mo)
            self.update_signal_machine(
                st=st,
                name="MO",
                spread=spread_mo,
                trend_raw=trend_raw_mo,
                trend_score=trend_score_mo,
                entry_raw=self.ENTRY_RAW_MO,
                entry_score=self.ENTRY_SCORE_MO,
                exit_raw=self.EXIT_RAW_MO,
                exit_score=self.EXIT_SCORE_MO,
                trailing_stop=self.TRAILING_STOP_MO,
                active_state_name="LONG_MAGENTA_SHORT_ORANGE",
            )

        # 3. Build independent targets.
        targets = {p: 0 for p in UV_PRODUCTS}

        if st.get("state_RA") == "LONG_RED_SHORT_AMBER":
            targets[UV_RED] = self.TARGET_RED
            targets[UV_AMBER] = self.TARGET_AMBER

        if st.get("state_MO") == "LONG_MAGENTA_SHORT_ORANGE":
            targets[UV_MAGENTA] = self.TARGET_MAGENTA
            targets[UV_ORANGE] = self.TARGET_ORANGE

        # 4. Execute towards targets. If book is bad, suppress opening/increasing
        # exposure but still allow reductions/flattening.
        for product in UV_PRODUCTS:
            if product not in state.order_depths or product not in mids:
                continue

            od = state.order_depths[product]
            pos = state.position.get(product, 0)
            target = targets[product]

            if not self.book_ok(product, od) and abs(target) > abs(pos):
                target = pos

            orders = self.trade_towards_target(
                product=product,
                od=od,
                current_pos=pos,
                target_pos=target,
                fair=mids[product],
                limit=self.LIMITS[product],
            )
            if orders:
                result.setdefault(product, []).extend(orders)

        return result