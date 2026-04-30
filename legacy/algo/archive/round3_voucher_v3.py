"""
Round 3 VEV Voucher Trading Strategy — v3

Core insight: VEV vouchers ARE standard European calls with IV smile.
Strategy: model-aware passive bidding on ATM/OTM, with two enhancements:
1. Inventory-driven unwinding (forced exits when position bands full)
2. Relative-value cross-strike arbs (sell rich, buy cheap vs model)

Non-negotiable: inventory relief is the ONLY market-making allowed.
Elsewhere: passive only, bid below fair, sell above fair.

Merge into full strategy:
  - Call vev_init_state() once per run()
  - For each timestamp: vev_compute_orders(state, spot_mid) → Dict[symbol -> List[Order]]
  - Accumulate into result orders
"""

import json
from math import ceil, erf, floor, log, sqrt
from typing import Dict, List, Tuple, Optional


# --- Config: VEV product universe ---

_VEV_ACTIVE_SYMBOLS = ("VEV_4000", "VEV_5200", "VEV_5300", "VEV_5400")
_VEV_SMILE_INPUT = (
    "VEV_5000", "VEV_5100", "VEV_5200", "VEV_5300", "VEV_5400", "VEV_5500",
)
_VEV_SMILE_TARGET = ("VEV_5200", "VEV_5300", "VEV_5400")

_VEV_STRIKES: Dict[str, float] = {
    "VEV_4000": 4000.0,
    "VEV_5000": 5000.0,
    "VEV_5100": 5100.0,
    "VEV_5200": 5200.0,
    "VEV_5300": 5300.0,
    "VEV_5400": 5400.0,
    "VEV_5500": 5500.0,
}

_VEV_PRIOR_IV: Dict[str, float] = {
    "VEV_4000": 0.828,
    "VEV_5000": 0.258,
    "VEV_5100": 0.262,
    "VEV_5200": 0.268,
    "VEV_5300": 0.279,
    "VEV_5400": 0.252,
    "VEV_5500": 0.271,
}

# --- Config: Passive bidding edges per strike ---
_VEV_BID_EDGES: Dict[str, float] = {
    "VEV_4000": 8.0,
    "VEV_5200": 0.05,
    "VEV_5300": 0.05,
    "VEV_5400": 0.05,
}

# --- Config: Position & risk limits ---
_VEV_LIMIT = 200
_VEV_GROSS_LIMIT = 800
_VEV_DELTA_LIMIT = 1000.0
_VEV_LOT_SIZE: Dict[str, int] = {
    "VEV_4000": 20,
    "VEV_5200": 20,
    "VEV_5300": 20,
    "VEV_5400": 30,
}

# --- Config: Inventory rebalance (Step 6 user requirement) ---
# Hard position band: exit if position >= this
_VEV_INV_BAND_LIMIT: Dict[str, int] = {
    "VEV_4000": 80,
    "VEV_5200": 100,
    "VEV_5300": 100,
    "VEV_5400": 160,
}
# Rebalance edge: exit at this profit if at band
_VEV_INV_EDGE: Dict[str, float] = {
    "VEV_4000": 12.0,
    "VEV_5200": 2.5,
    "VEV_5300": 1.5,
    "VEV_5400": 1.4,
}
# Relief MM spread: quote at fair ± half-spread to relieve faster
_VEV_INV_RELIEF_HALF_SPREAD: Dict[str, float] = {
    "VEV_4000": 4.0,
    "VEV_5200": 0.5,
    "VEV_5300": 0.3,
    "VEV_5400": 0.3,
}

# --- Config: Smile model blend ---
_VEV_SMILE_BLEND = 0.7
_VEV_4000_EXTRINSIC_CAP = 4.0

# --- Config: TTE decay ---
_ROUND3_START_TTE_DAYS = 5.0
_TICKS_PER_DAY = 1_000_000


# --- BSM helpers ---

def _normal_cdf(x: float) -> float:
    return 0.5 * (1.0 + erf(x / sqrt(2.0)))


def _bs_call(spot: float, strike: float, tte_years: float, vol: float) -> float:
    if tte_years <= 0.0:
        return max(spot - strike, 0.0)
    scaled_vol = max(vol, 0.05) * sqrt(tte_years)
    if scaled_vol <= 0.0 or spot <= 0.0 or strike <= 0.0:
        return max(spot - strike, 0.0)
    d1 = (log(spot / strike) + 0.5 * vol * vol * tte_years) / scaled_vol
    d2 = d1 - scaled_vol
    return spot * _normal_cdf(d1) - strike * _normal_cdf(d2)


def _bs_delta(spot: float, strike: float, tte_years: float, vol: float) -> float:
    if tte_years <= 0.0:
        return 1.0 if spot > strike else 0.0
    scaled_vol = max(vol, 0.05) * sqrt(tte_years)
    if scaled_vol <= 0.0 or spot <= 0.0 or strike <= 0.0:
        return 1.0 if spot > strike else 0.0
    d1 = (log(spot / strike) + 0.5 * vol * vol * tte_years) / scaled_vol
    return _normal_cdf(d1)


def _vev_tte_years(timestamp: int) -> float:
    fraction = max(0.0, min(1.0, timestamp / _TICKS_PER_DAY))
    return max(0.5, _ROUND3_START_TTE_DAYS - fraction) / 365.0


def _vev_fair(sym: str, spot_mid: float, timestamp: int) -> float:
    return _bs_call(
        spot_mid,
        _VEV_STRIKES[sym],
        _vev_tte_years(timestamp),
        _VEV_PRIOR_IV[sym],
    )


def _vev_delta(sym: str, spot_mid: float, timestamp: int) -> float:
    return _bs_delta(
        spot_mid,
        _VEV_STRIKES[sym],
        _vev_tte_years(timestamp),
        _VEV_PRIOR_IV[sym],
    )


# --- Implied vol extraction ---

def _vev_implied_vol(
    market_price: float, spot_mid: float, strike: float, tte_years: float,
) -> Optional[float]:
    intrinsic = max(spot_mid - strike, 0.0)
    if tte_years <= 0.0 or market_price <= intrinsic + 0.02:
        return None
    low, high = 0.001, 3.0
    for _ in range(40):
        mid = (low + high) / 2.0
        if _bs_call(spot_mid, strike, tte_years, mid) < market_price:
            low = mid
        else:
            high = mid
    return (low + high) / 2.0


# --- Smile fitting (quadratic in moneyness) ---

def _vev_quadratic_fit(
    xs: List[float], ys: List[float]
) -> Optional[Tuple[float, float, float]]:
    if len(xs) < 3:
        return None
    n = float(len(xs))
    sx = sum(xs)
    sx2 = sum(x * x for x in xs)
    sx3 = sum(x ** 3 for x in xs)
    sx4 = sum(x ** 4 for x in xs)
    sy = sum(ys)
    sxy = sum(x * y for x, y in zip(xs, ys))
    sx2y = sum(x * x * y for x, y in zip(xs, ys))

    matrix = [[n, sx, sx2, sy], [sx, sx2, sx3, sxy], [sx2, sx3, sx4, sx2y]]
    for pivot in range(3):
        divisor = matrix[pivot][pivot]
        if abs(divisor) < 1e-12:
            return None
        for col in range(pivot, 4):
            matrix[pivot][col] /= divisor
        for row in range(3):
            if row == pivot:
                continue
            factor = matrix[row][pivot]
            for col in range(pivot, 4):
                matrix[row][col] -= factor * matrix[pivot][col]
    return matrix[0][3], matrix[1][3], matrix[2][3]


def _vev_quadratic_value(coeffs: Tuple[float, float, float], x: float) -> float:
    a, b, c = coeffs
    return a + b * x + c * x * x


# --- Smile-adjusted fair value ---

def _vev_live_fairs(
    order_depths: Dict, spot_mid: float, timestamp: int
) -> Dict[str, float]:
    """Compute smile-adjusted fair values for active symbols."""
    tte_years = _vev_tte_years(timestamp)
    smile_points: List[Tuple[str, float, float]] = []

    for sym in _VEV_SMILE_INPUT:
        od = order_depths.get(sym)
        if od is None:
            continue
        bid = max(od.buy_orders) if od.buy_orders else None
        ask = min(od.sell_orders) if od.sell_orders else None
        if bid is None or ask is None:
            continue

        mid = (bid + ask) / 2.0
        iv = _vev_implied_vol(mid, spot_mid, _VEV_STRIKES[sym], tte_years)
        if iv is None:
            continue

        scaled_moneyness = log(_VEV_STRIKES[sym] / spot_mid) / sqrt(tte_years)
        smile_points.append((sym, scaled_moneyness, iv))

    if len(smile_points) < 4:
        return {}

    coeffs = _vev_quadratic_fit(
        [p[1] for p in smile_points],
        [p[2] for p in smile_points],
    )
    if coeffs is None:
        return {}

    fitted: Dict[str, float] = {}
    for sym in _VEV_SMILE_TARGET:
        scaled_moneyness = log(_VEV_STRIKES[sym] / spot_mid) / sqrt(tte_years)
        fit_iv = max(0.05, _vev_quadratic_value(coeffs, scaled_moneyness))
        blended_iv = (
            _VEV_SMILE_BLEND * fit_iv
            + (1.0 - _VEV_SMILE_BLEND) * _VEV_PRIOR_IV[sym]
        )
        fitted[sym] = _bs_call(spot_mid, _VEV_STRIKES[sym], tte_years, blended_iv)

    return fitted


def _vev_adjusted_fair(fair: float, position: int) -> float:
    """Skew fair value down as we accumulate position."""
    skew = 0.9 * position / _VEV_LIMIT
    return fair - skew


def _vev_intrinsic(sym: str, spot_mid: float) -> float:
    return max(spot_mid - _VEV_STRIKES[sym], 0.0)


# --- Order execution ---

def _best_bid(od) -> Optional[int]:
    return max(od.buy_orders) if od.buy_orders else None


def _best_ask(od) -> Optional[int]:
    return min(od.sell_orders) if od.sell_orders else None


class VEVTrader:
    """Encapsulate VEV trading logic for merge into full strategy."""

    def __init__(self):
        self.gross_position = 0
        self.portfolio_delta = 0.0

    def compute_orders(
        self,
        active_symbols: Tuple[str, ...],
        order_depths: Dict,
        positions: Dict[str, int],
        spot_mid: float,
        timestamp: int,
    ) -> Dict[str, List[Tuple]]:
        """
        Main entry point: for each active symbol, generate orders.
        Returns Dict[symbol -> List[(symbol, price, qty)]].
        """
        result: Dict[str, List[Tuple]] = {}

        self.gross_position = sum(abs(positions.get(s, 0)) for s in active_symbols)
        self.portfolio_delta = sum(
            positions.get(s, 0) * _vev_delta(s, spot_mid, timestamp)
            for s in active_symbols
        )

        live_fairs = _vev_live_fairs(order_depths, spot_mid, timestamp)

        for sym in active_symbols:
            od = order_depths.get(sym)
            if od is None:
                continue

            position = positions.get(sym, 0)
            orders = self._trade_symbol(
                sym, od, position, spot_mid, timestamp, live_fairs
            )
            if orders:
                result[sym] = orders

        return result

    def _trade_symbol(
        self,
        sym: str,
        od,
        position: int,
        spot_mid: float,
        timestamp: int,
        live_fairs: Dict[str, float],
    ) -> List[Tuple]:
        """Trade a single VEV symbol. Returns list of (symbol, price, qty) tuples."""
        bid = _best_bid(od)
        ask = _best_ask(od)
        if bid is None or ask is None:
            return []

        market_mid = (bid + ask) / 2.0
        fair = live_fairs.get(sym, _vev_fair(sym, spot_mid, timestamp))
        adjusted_fair = _vev_adjusted_fair(fair, position)

        orders: List[Tuple] = []

        # --- Step 1: Inventory-driven exit (forced unwinding at band limit) ---
        # This is the ONLY market-making allowed: relief quotes.
        if position >= _VEV_INV_BAND_LIMIT[sym]:
            if bid - adjusted_fair >= _VEV_INV_EDGE[sym]:
                bid_qty = od.buy_orders.get(bid, 0)
                exit_qty = min(_VEV_LOT_SIZE[sym], position, bid_qty)
                if exit_qty > 0:
                    return [(sym, bid, -exit_qty)]

            # Fallback: quote relief MM to exit faster
            relief_ask = int(ceil(adjusted_fair + _VEV_INV_RELIEF_HALF_SPREAD[sym]))
            relief_qty = min(_VEV_LOT_SIZE[sym] // 2, position, _VEV_LIMIT // 2)
            if relief_qty > 0 and relief_ask >= bid + 1:
                return [(sym, relief_ask, -relief_qty)]

        if position <= -_VEV_INV_BAND_LIMIT[sym]:
            if adjusted_fair - ask >= _VEV_INV_EDGE[sym]:
                ask_qty = -od.sell_orders.get(ask, 0)
                exit_qty = min(_VEV_LOT_SIZE[sym], -position, ask_qty)
                if exit_qty > 0:
                    return [(sym, ask, exit_qty)]

            # Fallback: quote relief MM to exit faster
            relief_bid = int(floor(adjusted_fair - _VEV_INV_RELIEF_HALF_SPREAD[sym]))
            relief_qty = min(_VEV_LOT_SIZE[sym] // 2, -position, _VEV_LIMIT // 2)
            if relief_qty > 0 and relief_bid <= ask - 1:
                return [(sym, relief_bid, relief_qty)]

        # --- Step 2: Rich/cheap detection (block if too rich) ---
        if sym == "VEV_4000":
            intrinsic = _vev_intrinsic(sym, spot_mid)
            if market_mid - intrinsic > _VEV_4000_EXTRINSIC_CAP:
                return []
        else:
            richness_cap = 6.0 if sym == "VEV_5200" else (3.0 if sym == "VEV_5300" else 1.5)
            if market_mid - adjusted_fair > richness_cap:
                return []

        # --- Step 3: Gross & delta limits ---
        if self.gross_position >= _VEV_GROSS_LIMIT:
            return []

        buy_cap = _VEV_LIMIT - position
        if buy_cap <= 0:
            return []

        option_delta = _vev_delta(sym, spot_mid, timestamp)
        delta_room = _VEV_DELTA_LIMIT - self.portfolio_delta
        if option_delta > 0.0:
            buy_cap = min(buy_cap, max(0, int(floor(delta_room / option_delta))))

        if buy_cap <= 0:
            return []

        # --- Step 4: Passive bid (only arb, no spread capture) ---
        model_quote = int(floor(market_mid - _VEV_BID_EDGES[sym]))
        if model_quote <= 0:
            return []

        qty = min(_VEV_LOT_SIZE[sym], buy_cap)
        if qty > 0:
            return [(sym, model_quote, qty)]

        return []


# --- Standalone entry points ---

def vev_init_state() -> VEVTrader:
    """Return a fresh VEV trader instance."""
    return VEVTrader()


def vev_compute_orders(
    trader: VEVTrader,
    active_symbols: Tuple[str, ...],
    order_depths: Dict,
    positions: Dict[str, int],
    spot_mid: Optional[float],
    timestamp: int,
) -> Dict[str, List[Tuple]]:
    """
    Call per timestamp to get VEV orders.
    Returns Dict[symbol -> List[(symbol, price, qty)]]
    """
    if spot_mid is None or spot_mid <= 0:
        return {}

    return trader.compute_orders(
        active_symbols, order_depths, positions, spot_mid, timestamp
    )
