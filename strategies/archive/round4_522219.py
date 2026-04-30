import json
from dataclasses import dataclass
from math import ceil, erf, floor, log, sqrt
from typing import Dict, List, NamedTuple, Tuple

from backtester.datamodel import Order, OrderDepth, TradingState


HYDROGEL_PACK = "HYDROGEL_PACK"
VELVETFRUIT_EXTRACT = "VELVETFRUIT_EXTRACT"


_SQRT_2 = sqrt(2.0)
_BS_HALF_VARIANCE = 0.5


_IV_MIN_EXTRINSIC = 0.02
_IV_BISECT_ITERS = 40
_IV_BISECT_LOW = 0.001
_IV_MIN_VOL = 0.05
_IV_MAX_VOL = 3.0
_SMILE_MIN_POINTS = 4


@dataclass(frozen=True)
class VevSymbolConfig:
    strike: float
    prior_iv: float
    bid_edge: float
    exit_edge: float
    exit_position: int
    lots: int
    max_overpricing: float


_VEV_CONFIG: Dict[str, VevSymbolConfig] = {
    "VEV_4000": VevSymbolConfig(
        strike=4000.0, prior_iv=0.828,
        bid_edge=9.5, exit_edge=12.0, exit_position=80,
        lots=20, max_overpricing=0.0,
    ),
    "VEV_5200": VevSymbolConfig(
        strike=5200.0, prior_iv=0.268,
        bid_edge=0.05, exit_edge=2.5, exit_position=100,
        lots=20, max_overpricing=6.0,
    ),
    "VEV_5300": VevSymbolConfig(
        strike=5300.0, prior_iv=0.279,
        bid_edge=0.05, exit_edge=1.5, exit_position=100,
        lots=20, max_overpricing=3.0,
    ),
    "VEV_5400": VevSymbolConfig(
        strike=5400.0, prior_iv=0.252,
        bid_edge=0.05, exit_edge=1.4, exit_position=160,
        lots=30, max_overpricing=1.5,
    ),
    "VEV_5500": VevSymbolConfig(
        strike=5500.0, prior_iv=0.271,
        bid_edge=0.05, exit_edge=1.4, exit_position=160,
        lots=30, max_overpricing=1.5,
    ),
}

_VEV_ACTIVE_SYMBOLS = (
    "VEV_4000", "VEV_5200", "VEV_5300", "VEV_5400", "VEV_5500",
)

# VEV_5200 and VEV_5300 bid one tick above best bid instead of using bid_edge
_VEV_PENNY_BID_SYMBOLS = ("VEV_5200", "VEV_5300")

# Smile input: symbols used for IV curve fitting
_VEV_SMILE_INPUT_SYMBOLS = (
    "VEV_5000", "VEV_5100", "VEV_5200", "VEV_5300", "VEV_5400", "VEV_5500",
)

# Smile target: symbols whose fair values come from the fitted smile
_VEV_SMILE_TARGET_SYMBOLS = ("VEV_5200", "VEV_5300", "VEV_5400")

# Strikes and prior IVs for smile-only symbols (not in _VEV_CONFIG)
_VEV_SMILE_ONLY_STRIKES: Dict[str, float] = {
    "VEV_5000": 5000.0,
    "VEV_5100": 5100.0,
}
_VEV_SMILE_ONLY_PRIOR_IV: Dict[str, float] = {
    "VEV_5000": 0.258,
    "VEV_5100": 0.262,
}

_VEV_LIMIT = 300
_VEV_GROSS_CAP = 800
_VEV_PORTFOLIO_DELTA_CAP = 1_000.0
_VEV_INV_SKEW = 0.9
_VEV_SMILE_BLEND = 0.7
_VEV_4000_EXTRINSIC_CAP = 4.0
_ROUND3_START_TTE_DAYS = 5.0
_TICKS_PER_DAY = 1_000_000
_DAYS_PER_YEAR = 365.0
_TTE_CALIBRATION_VOL = 0.20
_TTE_CALIBRATION_STRIKE = 5300.0
_TTE_SEARCH_MIN_DAYS = 3
_TTE_SEARCH_MAX_DAYS = 10
_GAUSS_ELIM_ZERO_TOL = 1e-12


HYDROGEL_FAIR_VALUE = 10_000.0
HYDROGEL_LIMIT = 200
HYDROGEL_POST_EDGE = 3
HYDROGEL_TAKE_EDGE = 20
HYDROGEL_TARGET_SCALE = 40
HYDROGEL_MAX_TAKE_SIZE = 10


VELVETFRUIT_LIMIT = 200
VELVETFRUIT_ANCHOR = 5_255.0
VELVETFRUIT_ENTRY_EDGE = 12.0
VELVETFRUIT_CLIP = 60


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
    max_skew=6,
    quote_size=40,
)


class SmilePoint(NamedTuple):
    symbol: str
    moneyness: float
    implied_vol: float


def _vev_strike(sym: str) -> float:
    if sym in _VEV_CONFIG:
        return _VEV_CONFIG[sym].strike
    return _VEV_SMILE_ONLY_STRIKES[sym]


def _vev_prior_iv(sym: str) -> float:
    if sym in _VEV_CONFIG:
        return _VEV_CONFIG[sym].prior_iv
    return _VEV_SMILE_ONLY_PRIOR_IV[sym]


# Rolling-mean overlay on velvetfruit. When spot deviates >2 stddev from
# its rolling mean, take a small same-direction voucher position betting
# on reversion. Capped at 50 contracts/voucher and 5 fills/tick to keep
# execution cost low.

_ROLLING_WINDOW = 300
_ZSCORE_TRIGGER = 2.0
_OVERLAY_MAX_POSITION = 50
_OVERLAY_MAX_TAKE_PER_TICK = 5


def _update_history(data: dict, mid: float) -> List[float]:
    history = data.get("vfe_mids", [])
    history.append(mid)
    if len(history) > _ROLLING_WINDOW * 2:
        history = history[-_ROLLING_WINDOW:]
    data["vfe_mids"] = history
    return history


def _rolling_mean_signal(history: List[float]) -> int:
    if len(history) < _ROLLING_WINDOW:
        return 0
    window = history[-_ROLLING_WINDOW:]
    mean = sum(window) / len(window)
    variance = sum((v - mean) ** 2 for v in window) / len(window)
    if variance < 1e-9:
        return 0
    std = sqrt(variance)
    z = (mean - history[-1]) / std
    if z >= _ZSCORE_TRIGGER:
        return 1
    if z <= -_ZSCORE_TRIGGER:
        return -1
    return 0


def _take_top_level(
    sym: str, depth: OrderDepth, current: int, target: int,
) -> List[Order]:
    diff = target - current
    if diff > 0 and depth.sell_orders:
        best_ask = min(depth.sell_orders.keys())
        available = -depth.sell_orders[best_ask]
        qty = min(diff, available, _OVERLAY_MAX_TAKE_PER_TICK)
        if qty > 0:
            return [Order(sym, best_ask, qty)]
    if diff < 0 and depth.buy_orders:
        best_bid = max(depth.buy_orders.keys())
        available = depth.buy_orders[best_bid]
        qty = min(-diff, available, _OVERLAY_MAX_TAKE_PER_TICK)
        if qty > 0:
            return [Order(sym, best_bid, -qty)]
    return []


def _apply_overlay(
    result: Dict[str, List[Order]],
    state: TradingState,
    signal: int,
) -> None:
    if signal == 0:
        return
    target = signal * _OVERLAY_MAX_POSITION
    for sym in _VEV_ACTIVE_SYMBOLS:
        # Skip wide-spread strikes where take cost dominates the signal.
        if sym == "VEV_4000":
            continue
        depth = state.order_depths.get(sym)
        if depth is None:
            continue
        position = state.position.get(sym, 0)
        if signal > 0 and position >= target:
            continue
        if signal < 0 and position <= target:
            continue
        orders = _take_top_level(sym, depth, position, target)
        if orders:
            result.setdefault(sym, []).extend(orders)


class Trader:
    def run(
        self, state: TradingState
    ) -> Tuple[Dict[str, List[Order]], int, str]:
        data = _load_data(state.traderData)
        result: Dict[str, List[Order]] = {}
        spot_mid = _spot_mid(state)
        start_tte = _resolve_start_tte(data, state, spot_mid)

        _add_orders(result, HYDROGEL_PACK, state, _trade_hydrogel)
        _add_orders(result, VELVETFRUIT_EXTRACT, state, _trade_velvetfruit)
        _trade_all_vev(result, state, spot_mid, start_tte)

        if spot_mid is not None:
            history = _update_history(data, spot_mid)
            signal = _rolling_mean_signal(history)
            _apply_overlay(result, state, signal)

        return result, 0, json.dumps(data, separators=(",", ":"))


def _spot_mid(state: TradingState) -> float | None:
    spot_depth = state.order_depths.get(VELVETFRUIT_EXTRACT)
    if spot_depth is None:
        return None
    return _wall_mid(spot_depth)


def _add_orders(
    result: Dict[str, List[Order]],
    symbol: str,
    state: TradingState,
    trade_fn,
) -> None:
    if symbol not in state.order_depths:
        return
    orders = trade_fn(
        state.order_depths[symbol],
        state.position.get(symbol, 0),
    )
    if orders:
        result[symbol] = orders


def _trade_all_vev(
    result: Dict[str, List[Order]],
    state: TradingState,
    spot_mid: float | None,
    start_tte: float,
) -> None:
    if spot_mid is None:
        return
    option_gross = _vev_gross_position(state.position)
    portfolio_delta = _vev_portfolio_delta(state, spot_mid, start_tte)
    live_fairs = _vev_live_fairs(state, spot_mid, start_tte)
    for sym in _VEV_ACTIVE_SYMBOLS:
        depth = state.order_depths.get(sym)
        if depth is None:
            continue
        orders = _trade_vev(
            sym, depth,
            state.position.get(sym, 0),
            spot_mid, state.timestamp, start_tte,
            option_gross, portfolio_delta, live_fairs,
        )
        if orders:
            result[sym] = orders


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
    return _BS_HALF_VARIANCE * (1.0 + erf(x / _SQRT_2))


def _bs_d1(
    spot: float, strike: float, tte_years: float,
    vol: float, scaled_vol: float,
) -> float:
    return (log(spot / strike) + _BS_HALF_VARIANCE * vol * vol * tte_years) / scaled_vol


def _bs_call(spot: float, strike: float, tte_years: float, vol: float) -> float:
    if tte_years <= 0.0:
        return max(spot - strike, 0.0)
    scaled_vol = max(vol, _IV_MIN_VOL) * sqrt(tte_years)
    if scaled_vol <= 0.0 or spot <= 0.0 or strike <= 0.0:
        return max(spot - strike, 0.0)
    d1 = _bs_d1(spot, strike, tte_years, vol, scaled_vol)
    d2 = d1 - scaled_vol
    return spot * _normal_cdf(d1) - strike * _normal_cdf(d2)


def _bs_delta(spot: float, strike: float, tte_years: float, vol: float) -> float:
    if tte_years <= 0.0:
        return 1.0 if spot > strike else 0.0
    scaled_vol = max(vol, _IV_MIN_VOL) * sqrt(tte_years)
    if scaled_vol <= 0.0 or spot <= 0.0 or strike <= 0.0:
        return 1.0 if spot > strike else 0.0
    d1 = _bs_d1(spot, strike, tte_years, vol, scaled_vol)
    return _normal_cdf(d1)


def _estimate_start_tte_days(
    spot: float, option_mid: float, strike: float, vol: float,
) -> float:
    best_tte = _ROUND3_START_TTE_DAYS
    best_err = float("inf")
    for candidate_days in range(_TTE_SEARCH_MIN_DAYS, _TTE_SEARCH_MAX_DAYS):
        model = _bs_call(spot, strike, candidate_days / _DAYS_PER_YEAR, vol)
        err = abs(model - option_mid)
        if err < best_err:
            best_err = err
            best_tte = float(candidate_days)
    return best_tte


def _resolve_start_tte(
    data: dict, state: TradingState, spot_mid: float | None,
) -> float:
    if "start_tte" in data:
        return data["start_tte"]
    if spot_mid is None:
        return _ROUND3_START_TTE_DAYS
    vev5300_od = state.order_depths.get("VEV_5300")
    vev5300_mid = _wall_mid(vev5300_od) if vev5300_od else None
    if vev5300_mid is None:
        return _ROUND3_START_TTE_DAYS
    data["start_tte"] = _estimate_start_tte_days(
        spot_mid, vev5300_mid, _TTE_CALIBRATION_STRIKE, _TTE_CALIBRATION_VOL,
    )
    return data["start_tte"]


def _vev_tte_years(timestamp: int, start_tte: float) -> float:
    day_fraction = max(0.0, min(1.0, timestamp / _TICKS_PER_DAY))
    return (start_tte - day_fraction) / _DAYS_PER_YEAR


def _vev_fair(
    sym: str, spot_mid: float, timestamp: int, start_tte: float,
) -> float:
    return _bs_call(
        spot_mid, _vev_strike(sym),
        _vev_tte_years(timestamp, start_tte),
        _vev_prior_iv(sym),
    )


def _vev_delta(
    sym: str, spot_mid: float, timestamp: int, start_tte: float,
) -> float:
    return _bs_delta(
        spot_mid, _vev_strike(sym),
        _vev_tte_years(timestamp, start_tte),
        _vev_prior_iv(sym),
    )


def _vev_gross_position(position: Dict[str, int]) -> int:
    return sum(abs(position.get(sym, 0)) for sym in _VEV_ACTIVE_SYMBOLS)


def _vev_portfolio_delta(
    state: TradingState, spot_mid: float | None, start_tte: float,
) -> float:
    if spot_mid is None:
        return float(state.position.get(VELVETFRUIT_EXTRACT, 0))
    total = float(state.position.get(VELVETFRUIT_EXTRACT, 0))
    for sym in _VEV_ACTIVE_SYMBOLS:
        pos = state.position.get(sym, 0)
        total += pos * _vev_delta(sym, spot_mid, state.timestamp, start_tte)
    return total


def _vev_implied_vol(
    market_price: float, spot_mid: float, strike: float, tte_years: float,
) -> float | None:
    intrinsic = max(spot_mid - strike, 0.0)
    if tte_years <= 0.0 or market_price <= intrinsic + _IV_MIN_EXTRINSIC:
        return None
    low = _IV_BISECT_LOW
    high = _IV_MAX_VOL
    for _ in range(_IV_BISECT_ITERS):
        mid = (low + high) / 2.0
        if _bs_call(spot_mid, strike, tte_years, mid) < market_price:
            low = mid
        else:
            high = mid
    return (low + high) / 2.0


def _vev_quadratic_fit(
    xs: List[float], ys: List[float],
) -> Tuple[float, float, float] | None:
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
        if abs(divisor) < _GAUSS_ELIM_ZERO_TOL:
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


def _vev_quadratic_value(
    coefficients: Tuple[float, float, float], x: float,
) -> float:
    a, b, c = coefficients
    return a + b * x + c * x * x


def _moneyness(strike: float, spot_mid: float, tte_years: float) -> float:
    return log(strike / spot_mid) / sqrt(tte_years)


def _vev_live_fairs(
    state: TradingState, spot_mid: float, start_tte: float,
) -> Dict[str, float]:
    tte_years = _vev_tte_years(state.timestamp, start_tte)
    smile_points = _collect_smile_points(state, spot_mid, tte_years)
    if len(smile_points) < _SMILE_MIN_POINTS:
        return {}
    coefficients = _vev_quadratic_fit(
        [p.moneyness for p in smile_points],
        [p.implied_vol for p in smile_points],
    )
    if coefficients is None:
        return {}
    return _evaluate_smile_fairs(coefficients, spot_mid, tte_years)


def _collect_smile_points(
    state: TradingState, spot_mid: float, tte_years: float,
) -> List[SmilePoint]:
    points: List[SmilePoint] = []
    for sym in _VEV_SMILE_INPUT_SYMBOLS:
        od = state.order_depths.get(sym)
        mid = _wall_mid(od) if od is not None else None
        if mid is None:
            continue
        iv = _vev_implied_vol(mid, spot_mid, _vev_strike(sym), tte_years)
        if iv is None:
            continue
        m = _moneyness(_vev_strike(sym), spot_mid, tte_years)
        points.append(SmilePoint(sym, m, iv))
    return points


def _evaluate_smile_fairs(
    coefficients: Tuple[float, float, float],
    spot_mid: float,
    tte_years: float,
) -> Dict[str, float]:
    fitted: Dict[str, float] = {}
    for sym in _VEV_SMILE_TARGET_SYMBOLS:
        m = _moneyness(_vev_strike(sym), spot_mid, tte_years)
        fit_iv = max(_IV_MIN_VOL, _vev_quadratic_value(coefficients, m))
        blended_iv = (
            _VEV_SMILE_BLEND * fit_iv
            + (1.0 - _VEV_SMILE_BLEND) * _vev_prior_iv(sym)
        )
        fitted[sym] = _bs_call(
            spot_mid, _vev_strike(sym), tte_years, blended_iv,
        )
    return fitted


def _vev_adjusted_fair(fair: float, position: int) -> float:
    return fair - _VEV_INV_SKEW * position / _VEV_LIMIT


def _vev_intrinsic(sym: str, spot_mid: float) -> float:
    return max(spot_mid - _vev_strike(sym), 0.0)


def _vev_is_overpriced(
    sym: str, market_mid: float, adjusted_fair: float, spot_mid: float,
) -> bool:
    if sym == "VEV_4000":
        extrinsic = market_mid - _vev_intrinsic(sym, spot_mid)
        return extrinsic > _VEV_4000_EXTRINSIC_CAP
    cfg = _VEV_CONFIG[sym]
    return market_mid - adjusted_fair > cfg.max_overpricing


def _trade_hydrogel(od: OrderDepth, position: int) -> List[Order]:
    current_mid = _wall_mid(od)
    target_position = 0
    if current_mid is not None:
        raw_target = round(
            (HYDROGEL_FAIR_VALUE - current_mid)
            / HYDROGEL_TARGET_SCALE * HYDROGEL_CONFIG.limit
        )
        target_position = max(
            -HYDROGEL_CONFIG.limit, min(HYDROGEL_CONFIG.limit, raw_target),
        )

    return _trade_dynamic_product(
        HYDROGEL_CONFIG, od, position, HYDROGEL_FAIR_VALUE,
        max_take_size=HYDROGEL_MAX_TAKE_SIZE,
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
    start_tte: float,
    option_gross: int,
    portfolio_delta: float,
    live_fairs: Dict[str, float],
) -> List[Order]:
    bid = _best_bid(od)
    ask = _best_ask(od)
    if bid is None or ask is None:
        return []
    cfg = _VEV_CONFIG[sym]
    fair = live_fairs.get(sym, _vev_fair(sym, spot_mid, timestamp, start_tte))
    adjusted_fair = _vev_adjusted_fair(fair, position)
    market_mid = (bid + ask) / 2.0

    if _vev_is_overpriced(sym, market_mid, adjusted_fair, spot_mid):
        return []

    exit_orders = _vev_try_exit(sym, bid, od.buy_orders[bid], position, adjusted_fair, cfg)
    if exit_orders:
        return exit_orders

    return _vev_passive_bid(
        sym, bid, position, spot_mid, timestamp, start_tte,
        market_mid, option_gross, portfolio_delta, cfg,
    )


def _vev_try_exit(
    sym: str,
    bid: int,
    bid_qty: int,
    position: int,
    adjusted_fair: float,
    cfg: VevSymbolConfig,
) -> List[Order]:
    if position < cfg.exit_position:
        return []
    if bid - adjusted_fair < cfg.exit_edge:
        return []
    exit_qty = min(cfg.lots, position, bid_qty)
    if exit_qty > 0:
        return [Order(sym, bid, -exit_qty)]
    return []


def _vev_buy_cap(
    sym: str,
    position: int,
    spot_mid: float,
    timestamp: int,
    start_tte: float,
    option_gross: int,
    portfolio_delta: float,
) -> int:
    if option_gross >= _VEV_GROSS_CAP:
        return 0
    cap = _VEV_LIMIT - position
    if cap <= 0:
        return 0
    option_delta = _vev_delta(sym, spot_mid, timestamp, start_tte)
    if option_delta > 0.0:
        delta_room = _VEV_PORTFOLIO_DELTA_CAP - portfolio_delta
        cap = min(cap, max(0, floor(delta_room / option_delta)))
    return cap


def _vev_passive_bid(
    sym: str,
    bid: int,
    position: int,
    spot_mid: float,
    timestamp: int,
    start_tte: float,
    market_mid: float,
    option_gross: int,
    portfolio_delta: float,
    cfg: VevSymbolConfig,
) -> List[Order]:
    buy_cap = _vev_buy_cap(
        sym, position, spot_mid, timestamp, start_tte,
        option_gross, portfolio_delta,
    )
    if buy_cap <= 0:
        return []
    qty = min(cfg.lots, buy_cap)

    if sym in _VEV_PENNY_BID_SYMBOLS:
        return [Order(sym, bid + 1, qty)]

    bid_price = floor(market_mid - cfg.bid_edge)
    if bid_price < 0:
        return []
    return [Order(sym, bid_price, qty)]


def _trade_dynamic_product(
    config: ProductConfig,
    od: OrderDepth,
    position: int,
    fair_value: float,
    max_take_size: int | None,
    take_edge: int = 0,
    target_position: int | None = None,
) -> List[Order]:
    orders: List[Order] = []
    buy_cap = config.limit - position
    sell_cap = config.limit + position

    buy_taken, projected = _take_cheap_asks(
        config, od, orders, position,
        fair_value, take_edge, max_take_size, target_position, buy_cap,
    )
    sell_taken, projected = _take_rich_bids(
        config, od, orders, projected,
        fair_value, take_edge, max_take_size, target_position, sell_cap,
    )
    projected, buy_taken, sell_taken = _clear_at_fair_value(
        config, od, orders, projected,
        buy_taken, sell_taken, buy_cap, sell_cap, fair_value,
    )
    _post_quotes(
        config, od, orders, projected,
        buy_taken, sell_taken, buy_cap, sell_cap, fair_value,
    )
    return orders


def _take_cheap_asks(
    config: ProductConfig,
    od: OrderDepth,
    orders: List[Order],
    projected: int,
    fair_value: float,
    take_edge: int,
    max_take_size: int | None,
    target_position: int | None,
    buy_cap: int,
) -> Tuple[int, int]:
    buy_taken = 0
    target_cap = config.limit if target_position is None else target_position
    for ask_price in sorted(od.sell_orders):
        if ask_price >= fair_value - take_edge:
            break
        if target_position is not None and projected >= target_position:
            break
        if buy_taken >= buy_cap:
            break
        available = -od.sell_orders[ask_price]
        if max_take_size is not None:
            available = min(available, max_take_size)
        qty = min(available, buy_cap - buy_taken, target_cap - projected)
        if qty > 0:
            orders.append(Order(config.symbol, ask_price, qty))
            projected += qty
            buy_taken += qty
    return buy_taken, projected


def _take_rich_bids(
    config: ProductConfig,
    od: OrderDepth,
    orders: List[Order],
    projected: int,
    fair_value: float,
    take_edge: int,
    max_take_size: int | None,
    target_position: int | None,
    sell_cap: int,
) -> Tuple[int, int]:
    sell_taken = 0
    target_floor = -config.limit if target_position is None else target_position
    for bid_price in sorted(od.buy_orders, reverse=True):
        if bid_price <= fair_value + take_edge:
            break
        if target_position is not None and projected <= target_position:
            break
        if sell_taken >= sell_cap:
            break
        available = od.buy_orders[bid_price]
        if max_take_size is not None:
            available = min(available, max_take_size)
        qty = min(available, sell_cap - sell_taken, projected - target_floor)
        if qty > 0:
            orders.append(Order(config.symbol, bid_price, -qty))
            projected -= qty
            sell_taken += qty
    return sell_taken, projected


def _clear_at_fair_value(
    config: ProductConfig,
    od: OrderDepth,
    orders: List[Order],
    projected: int,
    buy_taken: int,
    sell_taken: int,
    buy_cap: int,
    sell_cap: int,
    fair_value: float,
) -> Tuple[int, int, int]:
    fair_ceil = ceil(fair_value)
    fair_floor = floor(fair_value)

    if projected > 0 and fair_ceil in od.buy_orders:
        qty = min(projected, od.buy_orders[fair_ceil], sell_cap - sell_taken)
        if qty > 0:
            orders.append(Order(config.symbol, fair_ceil, -qty))
            projected -= qty
            sell_taken += qty

    if projected < 0 and fair_floor in od.sell_orders:
        qty = min(-projected, -od.sell_orders[fair_floor], buy_cap - buy_taken)
        if qty > 0:
            orders.append(Order(config.symbol, fair_floor, qty))
            projected += qty
            buy_taken += qty

    return projected, buy_taken, sell_taken


def _post_quotes(
    config: ProductConfig,
    od: OrderDepth,
    orders: List[Order],
    projected: int,
    buy_taken: int,
    sell_taken: int,
    buy_cap: int,
    sell_cap: int,
    fair_value: float,
) -> None:
    if config.quote_size <= 0:
        return

    best_bid = _best_bid(od)
    best_ask = _best_ask(od)
    skew = round(projected / config.limit * config.max_skew)

    base_bid = floor(fair_value) - config.post_edge
    base_ask = ceil(fair_value) + config.post_edge
    bid_price = base_bid - skew
    ask_price = base_ask - skew

    if best_ask is not None:
        bid_price = min(bid_price, best_ask - 1)
    if best_bid is not None:
        ask_price = max(ask_price, best_bid + 1)
    if bid_price >= ask_price:
        bid_price = min(bid_price, floor(fair_value) - 1)
        ask_price = max(ask_price, bid_price + 1)

    buy_qty = min(config.quote_size, buy_cap - buy_taken)
    if buy_qty > 0:
        orders.append(Order(config.symbol, bid_price, buy_qty))

    sell_qty = min(config.quote_size, sell_cap - sell_taken)
    if sell_qty > 0:
        orders.append(Order(config.symbol, ask_price, -sell_qty))