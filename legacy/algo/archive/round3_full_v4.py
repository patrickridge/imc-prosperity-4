import json
from dataclasses import dataclass
from math import ceil, erf, floor, log, sqrt
from typing import Dict, List, Tuple

from backtester.datamodel import Order, OrderDepth, TradingState


HYDROGEL_PACK = "HYDROGEL_PACK"
VELVETFRUIT_EXTRACT = "VELVETFRUIT_EXTRACT"

_VEV_ACTIVE_SYMBOLS = ("VEV_4000", "VEV_5200", "VEV_5300", "VEV_5400")
_VEV_SMILE_INPUT_SYMBOLS = (
    "VEV_5000",
    "VEV_5100",
    "VEV_5200",
    "VEV_5300",
    "VEV_5400",
    "VEV_5500",
)
_VEV_SMILE_TARGET_SYMBOLS = ("VEV_5200", "VEV_5300", "VEV_5400")

_VEV_BID_EDGES: Dict[str, float] = {
    "VEV_4000": 8.0,
    "VEV_5200": 0.05,
    "VEV_5300": 0.05,
    "VEV_5400": 0.05,
}
_VEV_STRIKES: Dict[str, float] = {
    "VEV_4000": 4000.0,
    "VEV_5000": 5000.0,
    "VEV_5100": 5100.0,
    "VEV_5200": 5200.0,
    "VEV_5300": 5300.0,
    "VEV_5400": 5400.0,
    "VEV_5500": 5500.0,
}

_VEV_PRIOR_IV_CORRECTED: Dict[str, float] = {
    "VEV_4000": 0.828,
    "VEV_5000": 0.2220,
    "VEV_5100": 0.2230,
    "VEV_5200": 0.2260,
    "VEV_5300": 0.2260,
    "VEV_5400": 0.2240,
    "VEV_5500": 0.2265,
}

_VEV_EXIT_EDGES: Dict[str, float] = {
    "VEV_4000": 12.0,
    "VEV_5200": 2.5,
    "VEV_5300": 1.5,
    "VEV_5400": 1.4,
}
_VEV_EXIT_POSITIONS: Dict[str, int] = {
    "VEV_4000": 80,
    "VEV_5200": 100,
    "VEV_5300": 100,
    "VEV_5400": 160,
}
_VEV_LIMIT = 200
_VEV_QTY = 20
_VEV_LOTS: Dict[str, int] = {
    "VEV_4000": 20,
    "VEV_5200": 20,
    "VEV_5300": 20,
    "VEV_5400": 30,
}
_VEV_GROSS_CAP = 800
_VEV_PORTFOLIO_DELTA_CAP = 1_000.0
_VEV_INV_SKEW = 0.9
_VEV_SMILE_BLEND = 0.7
_VEV_4000_EXTRINSIC_CAP = 4.0
_VEV_SMILE_RICHNESS_CAP: Dict[str, float] = {
    "VEV_5200": 6.0,
    "VEV_5300": 3.0,
    "VEV_5400": 1.5,
}

_TICKS_PER_DAY = 1_000_000
_ROUND3_TTE_DAYS = 5.0

HYDROGEL_FAIR_VALUE = 9992.0
HYDROGEL_LIMIT = 200
HYDROGEL_POST_EDGE = 2
HYDROGEL_TAKE_EDGE = 39
HYDROGEL_TARGET_SCALE = 50
HYDROGEL_MAX_TAKE_SIZE = 15

VELVETFRUIT_ANCHOR = 5_255.0
VELVETFRUIT_LIMIT = 200
VELVETFRUIT_ENTRY_EDGE = 12.0
VELVETFRUIT_CLIP = 50


@dataclass(frozen=True)
class ProductConfig:
    symbol: str
    limit: int
    post_edge: int
    max_skew: int
    quote_size: int


HYDROGEL_CONFIG = ProductConfig(
    symbol=HYDROGEL_PACK,
    limit=HYDROGEL_LIMIT,
    post_edge=HYDROGEL_POST_EDGE,
    max_skew=3,
    quote_size=40,
)


class Trader:
    def run(
        self, state: TradingState
    ) -> tuple[Dict[str, List[Order]], int, str]:
        data = _load_data(state.traderData)
        result: Dict[str, List[Order]] = {}
        spot_depth = state.order_depths.get(VELVETFRUIT_EXTRACT)
        spot_mid = _wall_mid(spot_depth) if spot_depth is not None else None

        if HYDROGEL_PACK in state.order_depths:
            result[HYDROGEL_PACK] = _trade_hydrogel(
                state.order_depths[HYDROGEL_PACK],
                state.position.get(HYDROGEL_PACK, 0),
            )

        if VELVETFRUIT_EXTRACT in state.order_depths:
            orders = _trade_velvetfruit(
                state.order_depths[VELVETFRUIT_EXTRACT],
                state.position.get(VELVETFRUIT_EXTRACT, 0),
            )
            if orders:
                result[VELVETFRUIT_EXTRACT] = orders

        option_gross = _vev_gross_position(state.position)
        portfolio_delta = _vev_portfolio_delta(state, spot_mid)
        live_fairs = _vev_live_fairs(state, spot_mid) if spot_mid is not None else {}
        if spot_mid is not None:
            for sym in _VEV_ACTIVE_SYMBOLS:
                depth = state.order_depths.get(sym)
                if depth is None:
                    continue
                orders = _trade_vev(
                    sym,
                    depth,
                    state.position.get(sym, 0),
                    spot_mid,
                    state.timestamp,
                    option_gross,
                    portfolio_delta,
                    live_fairs,
                    _VEV_BID_EDGES[sym],
                )
                if orders:
                    result[sym] = orders

        return result, 0, json.dumps(data, separators=(",", ":"))


def _load_data(raw: str) -> dict:
    if not raw:
        return {}
    try:
        loaded = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _best_bid(od: OrderDepth) -> int | None:
    return max(od.buy_orders) if od.buy_orders else None


def _best_ask(od: OrderDepth) -> int | None:
    return min(od.sell_orders) if od.sell_orders else None


def _wall_mid(od: OrderDepth) -> float | None:
    bid = _best_bid(od)
    ask = _best_ask(od)
    if bid is None or ask is None:
        return None
    return (bid + ask) / 2.0


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
    return max(0.5, _ROUND3_TTE_DAYS - fraction) / 365.0


def _vev_fair(sym: str, spot_mid: float, timestamp: int) -> float:
    return _bs_call(
        spot_mid,
        _VEV_STRIKES[sym],
        _vev_tte_years(timestamp),
        _VEV_PRIOR_IV_CORRECTED[sym],
    )


def _vev_delta(sym: str, spot_mid: float, timestamp: int) -> float:
    return _bs_delta(
        spot_mid,
        _VEV_STRIKES[sym],
        _vev_tte_years(timestamp),
        _VEV_PRIOR_IV_CORRECTED[sym],
    )


def _vev_gross_position(position: Dict[str, int]) -> int:
    return sum(abs(position.get(sym, 0)) for sym in _VEV_ACTIVE_SYMBOLS)


def _vev_portfolio_delta(state: TradingState, spot_mid: float | None) -> float:
    if spot_mid is None:
        return float(state.position.get(VELVETFRUIT_EXTRACT, 0))
    total = float(state.position.get(VELVETFRUIT_EXTRACT, 0))
    for sym in _VEV_ACTIVE_SYMBOLS:
        total += state.position.get(sym, 0) * _vev_delta(sym, spot_mid, state.timestamp)
    return total


def _vev_implied_vol(
    market_price: float,
    spot_mid: float,
    strike: float,
    tte_years: float,
) -> float | None:
    intrinsic = max(spot_mid - strike, 0.0)
    if tte_years <= 0.0 or market_price <= intrinsic + 0.02:
        return None
    low = 0.001
    high = 3.0
    for _ in range(40):
        mid = (low + high) / 2.0
        if _bs_call(spot_mid, strike, tte_years, mid) < market_price:
            low = mid
        else:
            high = mid
    return (low + high) / 2.0


def _vev_quadratic_fit(xs: List[float], ys: List[float]) -> Tuple[float, float, float] | None:
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


def _vev_quadratic_value(coefficients: Tuple[float, float, float], x: float) -> float:
    a, b, c = coefficients
    return a + b * x + c * x * x


def _vev_live_fairs(state: TradingState, spot_mid: float) -> Dict[str, float]:
    tte_years = _vev_tte_years(state.timestamp)
    smile_points: List[Tuple[str, float, float]] = []
    for sym in _VEV_SMILE_INPUT_SYMBOLS:
        od = state.order_depths.get(sym)
        mid = _wall_mid(od) if od is not None else None
        if mid is None:
            continue
        iv = _vev_implied_vol(mid, spot_mid, _VEV_STRIKES[sym], tte_years)
        if iv is None:
            continue
        scaled_moneyness = log(_VEV_STRIKES[sym] / spot_mid) / sqrt(tte_years)
        smile_points.append((sym, scaled_moneyness, iv))
    if len(smile_points) < 4:
        return {}
    coefficients = _vev_quadratic_fit(
        [point[1] for point in smile_points],
        [point[2] for point in smile_points],
    )
    if coefficients is None:
        return {}
    fitted: Dict[str, float] = {}
    for sym in _VEV_SMILE_TARGET_SYMBOLS:
        scaled_moneyness = log(_VEV_STRIKES[sym] / spot_mid) / sqrt(tte_years)
        fit_iv = max(0.05, _vev_quadratic_value(coefficients, scaled_moneyness))
        blended_iv = (
            _VEV_SMILE_BLEND * fit_iv
            + (1.0 - _VEV_SMILE_BLEND) * _VEV_PRIOR_IV_CORRECTED[sym]
        )
        fitted[sym] = _bs_call(spot_mid, _VEV_STRIKES[sym], tte_years, blended_iv)
    return fitted


def _vev_adjusted_fair(fair: float, position: int) -> float:
    return fair - _VEV_INV_SKEW * position / _VEV_LIMIT


def _vev_intrinsic(sym: str, spot_mid: float) -> float:
    return max(spot_mid - _VEV_STRIKES[sym], 0.0)


def _trade_hydrogel(od: OrderDepth, position: int) -> List[Order]:
    current_mid = _wall_mid(od)
    target_position = 0
    if current_mid is not None:
        raw_target = round(
            (HYDROGEL_FAIR_VALUE - current_mid) / HYDROGEL_TARGET_SCALE * HYDROGEL_CONFIG.limit
        )
        target_position = max(-HYDROGEL_CONFIG.limit, min(HYDROGEL_CONFIG.limit, raw_target))

    return _trade_dynamic_product(
        HYDROGEL_CONFIG,
        od,
        position,
        HYDROGEL_FAIR_VALUE,
        max_take_size=HYDROGEL_MAX_TAKE_SIZE,
        skip_oversized_take=False,
        take_edge=HYDROGEL_TAKE_EDGE,
        target_position=target_position,
    )


def _trade_velvetfruit(od: OrderDepth, position: int) -> List[Order]:
    bid = _best_bid(od)
    ask = _best_ask(od)
    if bid is None or ask is None:
        return []
    mid = (bid + ask) / 2.0
    orders: List[Order] = []

    if mid < VELVETFRUIT_ANCHOR - VELVETFRUIT_ENTRY_EDGE and position < VELVETFRUIT_LIMIT:
        ask_qty = abs(od.sell_orders[ask])
        qty = min(VELVETFRUIT_CLIP, ask_qty, VELVETFRUIT_LIMIT - position)
        if qty > 0:
            orders.append(Order(VELVETFRUIT_EXTRACT, ask, qty))
    elif mid > VELVETFRUIT_ANCHOR + VELVETFRUIT_ENTRY_EDGE and position > -VELVETFRUIT_LIMIT:
        bid_qty = od.buy_orders[bid]
        qty = min(VELVETFRUIT_CLIP, bid_qty, VELVETFRUIT_LIMIT + position)
        if qty > 0:
            orders.append(Order(VELVETFRUIT_EXTRACT, bid, -qty))

    return orders


def _trade_vev(
    sym: str,
    od: OrderDepth,
    position: int,
    spot_mid: float,
    timestamp: int,
    option_gross: int,
    portfolio_delta: float,
    live_fairs: Dict[str, float],
    bid_edge: float,
) -> List[Order]:
    bid = _best_bid(od)
    ask = _best_ask(od)
    if bid is None or ask is None:
        return []
    fair = live_fairs.get(sym, _vev_fair(sym, spot_mid, timestamp))
    adjusted_fair = _vev_adjusted_fair(fair, position)
    market_mid = (bid + ask) / 2.0

    if sym == "VEV_4000":
        intrinsic = _vev_intrinsic(sym, spot_mid)
        if market_mid - intrinsic > _VEV_4000_EXTRINSIC_CAP:
            return []
    elif market_mid - adjusted_fair > _VEV_SMILE_RICHNESS_CAP[sym]:
        return []

    if position >= _VEV_EXIT_POSITIONS[sym] and bid - adjusted_fair >= _VEV_EXIT_EDGES[sym]:
        bid_qty = od.buy_orders[bid]
        exit_qty = min(_VEV_LOTS[sym], position, bid_qty)
        if exit_qty > 0:
            return [Order(sym, bid, -exit_qty)]

    if option_gross >= _VEV_GROSS_CAP:
        return []

    buy_cap = _VEV_LIMIT - position
    if buy_cap <= 0:
        return []

    option_delta = _vev_delta(sym, spot_mid, timestamp)
    delta_room = _VEV_PORTFOLIO_DELTA_CAP - portfolio_delta
    if option_delta > 0.0:
        buy_cap = min(buy_cap, max(0, floor(delta_room / option_delta)))
    if buy_cap <= 0:
        return []

    model_quote = floor(market_mid - bid_edge)
    if model_quote <= 0:
        return []
    return [Order(sym, model_quote, min(_VEV_LOTS[sym], buy_cap))]


def _trade_dynamic_product(
    config: ProductConfig,
    od: OrderDepth,
    position: int,
    fair_value: float,
    max_take_size: int | None,
    skip_oversized_take: bool,
    take_edge: int = 0,
    target_position: int | None = None,
) -> List[Order]:
    orders: List[Order] = []
    projected = position
    target = target_position

    for ask_price in sorted(od.sell_orders):
        if ask_price >= fair_value - take_edge:
            break
        if target is not None and projected >= target:
            break
        ask_qty = -od.sell_orders[ask_price]
        if skip_oversized_take and max_take_size is not None and ask_qty > max_take_size:
            continue
        if max_take_size is not None:
            ask_qty = min(ask_qty, max_take_size)
        target_cap = config.limit if target is None else target
        qty = min(ask_qty, config.limit - projected, target_cap - projected)
        if qty > 0:
            orders.append(Order(config.symbol, ask_price, qty))
            projected += qty

    for bid_price in sorted(od.buy_orders, reverse=True):
        if bid_price <= fair_value + take_edge:
            break
        if target is not None and projected <= target:
            break
        bid_qty = od.buy_orders[bid_price]
        if skip_oversized_take and max_take_size is not None and bid_qty > max_take_size:
            continue
        if max_take_size is not None:
            bid_qty = min(bid_qty, max_take_size)
        target_floor = -config.limit if target is None else target
        qty = min(bid_qty, config.limit + projected, projected - target_floor)
        if qty > 0:
            orders.append(Order(config.symbol, bid_price, -qty))
            projected -= qty

    projected = _clear_inventory(config, od, orders, projected, fair_value)
    _post_quotes(config, od, orders, projected, fair_value)
    return orders


def _clear_inventory(
    config: ProductConfig,
    od: OrderDepth,
    orders: List[Order],
    projected: int,
    fair_value: float,
) -> int:
    fair_bid = floor(fair_value)
    fair_ask = ceil(fair_value)

    if projected > 0 and fair_ask in od.buy_orders:
        qty = min(projected, od.buy_orders[fair_ask], config.limit + projected)
        if qty > 0:
            orders.append(Order(config.symbol, fair_ask, -qty))
            projected -= qty

    if projected < 0 and fair_bid in od.sell_orders:
        qty = min(-projected, -od.sell_orders[fair_bid], config.limit - projected)
        if qty > 0:
            orders.append(Order(config.symbol, fair_bid, qty))
            projected += qty

    return projected


def _post_quotes(
    config: ProductConfig,
    od: OrderDepth,
    orders: List[Order],
    projected: int,
    fair_value: float,
) -> None:
    best_bid = _best_bid(od)
    best_ask = _best_ask(od)
    skew = round(projected / config.limit * config.max_skew)

    bid_ceiling = floor(fair_value) - config.post_edge
    ask_floor = ceil(fair_value) + config.post_edge
    bid_price = bid_ceiling - skew
    ask_price = ask_floor - skew

    if best_ask is not None:
        bid_price = min(bid_price, best_ask - 1)
    if best_bid is not None:
        ask_price = max(ask_price, best_bid + 1)
    if bid_price >= ask_price:
        bid_price = min(bid_price, floor(fair_value) - 1)
        ask_price = max(ask_price, bid_price + 1)

    buy_qty = min(config.quote_size, config.limit - projected)
    if buy_qty > 0:
        orders.append(Order(config.symbol, bid_price, buy_qty))

    sell_qty = min(config.quote_size, config.limit + projected)
    if sell_qty > 0:
        orders.append(Order(config.symbol, ask_price, -sell_qty))
