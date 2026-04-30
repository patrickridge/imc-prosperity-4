"""Immediate:
BLACK_HOLES long
GARLIC long

Fast/medium adaptive:
DARK_MATTER dip/recovery logic
SOLAR_FLAMES faster crash-short logic
PLANETARY_RINGS breakdown short
SOLAR_WINDS breakdown short

Delayed adaptive:
CHOCOLATE delayed long
EVENING_BREATH delayed short"""

import json
from typing import Dict, List, Any, Optional


class Trader:
    """
    Round 5 GALAXY/OXYGEN v9 — fast-adaptive throttle on top of the verified slow-regime module.

    Verified core from backtester:
      - Buy/hold GALAXY_SOUNDS_BLACK_HOLES to +10.
      - Buy/hold OXYGEN_SHAKE_GARLIC to +10.
      - SOLAR_FLAMES crash-follow short added +7.9k over days 2-4.

    v5 overlay:
      - DARK_MATTER dip-buy mean reversion.
        CSV simulation with top-of-book crossing:
        window=1500, slope < -200, target +10
        approx PnL: day2 +1830, day3 +2330, day4 +1880.

    v6 enabled overlay:
      - PLANETARY_RINGS breakdown short.

    Optional overlay left OFF by default:
      - SOLAR_WINDS breakdown short.
    Enable one at a time only after v5 is tested.
    """

    BLACK = "GALAXY_SOUNDS_BLACK_HOLES"
    GARLIC = "OXYGEN_SHAKE_GARLIC"
    SOLAR_FLAMES = "GALAXY_SOUNDS_SOLAR_FLAMES"
    DARK_MATTER = "GALAXY_SOUNDS_DARK_MATTER"
    PLANETARY_RINGS = "GALAXY_SOUNDS_PLANETARY_RINGS"
    SOLAR_WINDS = "GALAXY_SOUNDS_SOLAR_WINDS"
    EVENING = "OXYGEN_SHAKE_EVENING_BREATH"
    CHOCOLATE = "OXYGEN_SHAKE_CHOCOLATE"
    MORNING = "OXYGEN_SHAKE_MORNING_BREATH"
    MINT = "OXYGEN_SHAKE_MINT"

    LIMITS = {
        BLACK: 10,
        GARLIC: 10,
        SOLAR_FLAMES: 10,
        DARK_MATTER: 10,
        PLANETARY_RINGS: 10,
        SOLAR_WINDS: 10,
        EVENING: 10,
        CHOCOLATE: 10,
        MORNING: 10,
        MINT: 10,
    }

    ACTIVE_PRODUCTS = [
        BLACK,
        GARLIC,
        SOLAR_FLAMES,
        DARK_MATTER,
        PLANETARY_RINGS,
        SOLAR_WINDS,
        EVENING,
        CHOCOLATE,
        MORNING,
        MINT,
    ]

    # Always-on verified core.
    ENABLE_BLACK = False
    ENABLE_GARLIC = True
    BLACK_TARGET = 10
    GARLIC_TARGET = 10

    # v9 fast-adaptive SOLAR_FLAMES: faster/stricter breakdown trigger.
    # CSV sim: w=1500, drop<-400 improved versus v8 w=2000/drop<-300.
    ENABLE_SOLAR_FLAMES_CRASH_SHORT = False
    SOLAR_FLAMES_WINDOW = 150
    SOLAR_FLAMES_ENTRY_DROP = -40.0
    SOLAR_FLAMES_TARGET = -10

    ENABLE_DARK_MATTER_DIP_BUY = False
    ENABLE_DARK_MATTER_DELAYED_LONG = False
    ENABLE_DARK_MATTER_DELAYED_SHORT = True
    DARK_MATTER_DELAY_WARMUP = 200
    DARK_MATTER_TARGET = -10
    DARK_MATTER_WINDOW = 150
    DARK_MATTER_ENTRY_DROP = -20.0

    # Optional experimental overlays. Keep False for first v5 test.
    ENABLE_PLANETARY_RINGS_BREAKDOWN_SHORT = True
    PLANETARY_RINGS_WINDOW = 300
    PLANETARY_RINGS_ENTRY_DROP = -15.0
    PLANETARY_RINGS_TARGET = -10

    ENABLE_SOLAR_WINDS_BREAKDOWN_SHORT = False
    SOLAR_WINDS_WINDOW = 500
    SOLAR_WINDS_ENTRY_DROP = -2.5
    SOLAR_WINDS_TARGET = -10

    # Naive GARLIC/EVENING pair hedge stays off; too spread-cost sensitive.
    ENABLE_PAIR = False

    # v8 OXYGEN delayed-regime overlays.
    # These are deliberately time/warmup based rather than high-churn z/pair rules.
    # CSV top-of-book simulation estimates:
    #   CHOCOLATE long after 4000 ticks: +5.34k / +3.58k / +9.38k
    #   EVENING_BREATH short after 3000 ticks: +13.24k / +0.74k / +4.04k
    #   MORNING_BREATH long after 8000 ticks: +3.36k / +7.82k / +2.18k
    ENABLE_CHOCOLATE_DELAYED_LONG = False
    CHOCOLATE_WARMUP = 400
    CHOCOLATE_TARGET = 10

    ENABLE_EVENING_DELAYED_SHORT = True
    EVENING_WARMUP = 300
    EVENING_TARGET = -10

    ENABLE_MORNING_LATE_LONG = False
    ENABLE_MORNING_DELAYED_SHORT = True
    MORNING_WARMUP = 200
    MORNING_TARGET = -10

    ENABLE_MINT_DELAYED_SHORT = True
    MINT_WARMUP = 200
    MINT_TARGET = -10

    MAX_ORDER_SIZE = 10
    HIST_LEN = 1005

    def run(self, state: TradingState):
        data = self.load_state(state.traderData)
        result: Dict[str, List[Order]] = {}

        for product in self.ACTIVE_PRODUCTS:
            self.ensure_product_state(data, product)
            od = state.order_depths.get(product)
            mid = self.mid_price(od) if od is not None else None
            if mid is not None:
                self.update_product_state(data, product, mid)

        targets = self.compute_targets(data)

        for product, target in targets.items():
            od = state.order_depths.get(product)
            if od is None:
                continue
            limit = self.LIMITS[product]
            position = state.position.get(product, 0)
            target = self.clip_int(target, -limit, limit)
            orders = self.cross_to_target(product, od, position, target, limit)
            if orders:
                result[product] = orders

        return result, 0, self.save_state(data)

    def compute_targets(self, data: Dict[str, Any]) -> Dict[str, int]:
        targets = {p: 0 for p in self.ACTIVE_PRODUCTS}

        if self.ENABLE_BLACK:
            targets[self.BLACK] = self.BLACK_TARGET

        if self.ENABLE_GARLIC:
            targets[self.GARLIC] = self.GARLIC_TARGET

        if self.ENABLE_SOLAR_FLAMES_CRASH_SHORT:
            targets[self.SOLAR_FLAMES] = self.slope_threshold_target(
                data,
                self.SOLAR_FLAMES,
                self.SOLAR_FLAMES_WINDOW,
                self.SOLAR_FLAMES_ENTRY_DROP,
                self.SOLAR_FLAMES_TARGET,
                direction="below",
            )

        if self.ENABLE_DARK_MATTER_DELAYED_SHORT:
            targets[self.DARK_MATTER] = self.warmup_target(
                data,
                self.DARK_MATTER,
                self.DARK_MATTER_DELAY_WARMUP,
                self.DARK_MATTER_TARGET,
            )

        if self.ENABLE_PLANETARY_RINGS_BREAKDOWN_SHORT:
            targets[self.PLANETARY_RINGS] = self.slope_threshold_target(
                data,
                self.PLANETARY_RINGS,
                self.PLANETARY_RINGS_WINDOW,
                self.PLANETARY_RINGS_ENTRY_DROP,
                self.PLANETARY_RINGS_TARGET,
                direction="below",
            )

        if self.ENABLE_SOLAR_WINDS_BREAKDOWN_SHORT:
            targets[self.SOLAR_WINDS] = self.slope_threshold_target(
                data,
                self.SOLAR_WINDS,
                self.SOLAR_WINDS_WINDOW,
                self.SOLAR_WINDS_ENTRY_DROP,
                self.SOLAR_WINDS_TARGET,
                direction="below",
            )

        if self.ENABLE_CHOCOLATE_DELAYED_LONG:
            targets[self.CHOCOLATE] = self.warmup_target(
                data,
                self.CHOCOLATE,
                self.CHOCOLATE_WARMUP,
                self.CHOCOLATE_TARGET,
            )

        if self.ENABLE_EVENING_DELAYED_SHORT:
            targets[self.EVENING] = self.warmup_target(
                data,
                self.EVENING,
                self.EVENING_WARMUP,
                self.EVENING_TARGET,
            )

        if self.ENABLE_MORNING_DELAYED_SHORT:
            targets[self.MORNING] = self.warmup_target(
                data,
                self.MORNING,
                self.MORNING_WARMUP,
                self.MORNING_TARGET,
            )

        if self.ENABLE_MINT_DELAYED_SHORT:
            targets[self.MINT] = self.warmup_target(
                data,
                self.MINT,
                self.MINT_WARMUP,
                self.MINT_TARGET,
            )

        for p in list(targets):
            lim = self.LIMITS[p]
            targets[p] = self.clip_int(targets[p], -lim, lim)
        return targets

    def warmup_target(
        self,
        data: Dict[str, Any],
        product: str,
        warmup: int,
        target: int,
    ) -> int:
        hist = data.get("products", {}).get(product, {}).get("mid_hist", [])
        if len(hist) > warmup:
            return target
        return 0

    def slope_threshold_target(
        self,
        data: Dict[str, Any],
        product: str,
        window: int,
        threshold: float,
        target: int,
        direction: str = "below",
    ) -> int:
        hist = data.get("products", {}).get(product, {}).get("mid_hist", [])
        if len(hist) <= window:
            return 0
        slope = hist[-1] - hist[-1 - window]
        if direction == "below" and slope < threshold:
            return target
        if direction == "above" and slope > threshold:
            return target
        return 0

    def cross_to_target(self, product: str, od, position: int, target: int, limit: int) -> List[Order]:
        orders: List[Order] = []
        gap = target - position
        if gap == 0:
            return orders

        if gap > 0:
            if not od.sell_orders:
                return orders
            best_ask = min(od.sell_orders.keys())
            ask_avail = abs(int(od.sell_orders[best_ask]))
            qty = min(gap, limit - position, ask_avail, self.MAX_ORDER_SIZE)
            if qty > 0:
                orders.append(Order(product, best_ask, qty))
            return orders

        if not od.buy_orders:
            return orders
        best_bid = max(od.buy_orders.keys())
        bid_avail = int(od.buy_orders[best_bid])
        qty = min(-gap, limit + position, bid_avail, self.MAX_ORDER_SIZE)
        if qty > 0:
            orders.append(Order(product, best_bid, -qty))
        return orders

    def ensure_product_state(self, data: Dict[str, Any], product: str) -> None:
        data.setdefault("products", {})
        if product not in data["products"]:
            data["products"][product] = {"mid_hist": [], "last_mid": None, "ticks": 0}

    def update_product_state(self, data: Dict[str, Any], product: str, mid: float) -> None:
        st = data["products"][product]
        st["mid_hist"].append(float(mid))
        st["mid_hist"] = st["mid_hist"][-self.HIST_LEN:]
        st["last_mid"] = float(mid)
        st["ticks"] = int(st.get("ticks", 0)) + 1

    def mid_price(self, od) -> Optional[float]:
        if od is None or not od.buy_orders or not od.sell_orders:
            return None
        return (max(od.buy_orders.keys()) + min(od.sell_orders.keys())) / 2.0

    def load_state(self, trader_data: str) -> Dict[str, Any]:
        if not trader_data:
            return {"products": {}}
        try:
            data = json.loads(trader_data)
            if not isinstance(data, dict):
                return {"products": {}}
            data.setdefault("products", {})
            return data
        except Exception:
            return {"products": {}}

    def save_state(self, data: Dict[str, Any]) -> str:
        for st in data.get("products", {}).values():
            st["mid_hist"] = st.get("mid_hist", [])[-self.HIST_LEN:]
        return json.dumps(data, separators=(",", ":"))

    def clip_int(self, x: int, lo: int, hi: int) -> int:
        return int(max(lo, min(hi, int(x))))