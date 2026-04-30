import json
from dataclasses import dataclass
from math import ceil, erf, floor, log, sqrt
from typing import Dict, List, Tuple

from backtester.datamodel import Order, OrderDepth, TradingState


HYDROGEL_PACK = "HYDROGEL_PACK"
VELVETFRUIT_EXTRACT = "VELVETFRUIT_EXTRACT"

# Product gate for diagnostic isolation. Set to {"HYDROGEL", "VELVETFRUIT", "VEV"}
# for the full strategy, or any subset to isolate a single product.
_ENABLED_PRODUCTS = {"HYDROGEL"}

_VEV_ACTIVE_SYMBOLS = (
    "VEV_4000",
    "VEV_4500",
    "VEV_5000",
    "VEV_5100",
    "VEV_5200",
    "VEV_5300",
    "VEV_5400",
    "VEV_5500",
)
_VEV_STRIKES: Dict[str, float] = {
    "VEV_4000": 4000.0,
    "VEV_4500": 4500.0,
    "VEV_5000": 5000.0,
    "VEV_5100": 5100.0,
    "VEV_5200": 5200.0,
    "VEV_5300": 5300.0,
    "VEV_5400": 5400.0,
    "VEV_5500": 5500.0,
}
_VEV_PRIOR_IV: Dict[str, float] = {
    "VEV_4000": 0.234,
    "VEV_4500": 0.234,
    "VEV_5000": 0.234,
    "VEV_5100": 0.232,
    "VEV_5200": 0.234,
    "VEV_5300": 0.237,
    "VEV_5400": 0.222,
    "VEV_5500": 0.241,
}
_VEV_ENTRY_EDGE: Dict[str, float] = {
    "VEV_4000": 3.0,
    "VEV_4500": 3.0,
    "VEV_5000": 2.0,
    "VEV_5100": 1.5,
    "VEV_5200": 1.0,
    "VEV_5300": 0.7,
    "VEV_5400": 0.5,
    "VEV_5500": 0.4,
}
_VEV_POS_CAP: Dict[str, int] = {
    "VEV_4000": 100,
    "VEV_4500": 100,
    "VEV_5000": 150,
    "VEV_5100": 150,
    "VEV_5200": 150,
    "VEV_5300": 150,
    "VEV_5400": 200,
    "VEV_5500": 200,
}
_VEV_LOT: Dict[str, int] = {
    "VEV_4000": 20,
    "VEV_4500": 20,
    "VEV_5000": 25,
    "VEV_5100": 25,
    "VEV_5200": 25,
    "VEV_5300": 25,
    "VEV_5400": 40,
    "VEV_5500": 40,
}
_VEV_LIMIT = 300
_VEV_GROSS_CAP = 1_500
_VEV_PORTFOLIO_DELTA_CAP = 1_500.0

_VEV_MM_BID_STRIKES = ("VEV_4000",)
_VEV_MM_ASK_STRIKES = ("VEV_5500",)
_VEV_MM_BID_OFFSET: Dict[str, float] = {"VEV_4000": 8.0}
_VEV_MM_ASK_OFFSET: Dict[str, float] = {"VEV_5500": 1.0}
_VEV_MM_LOT: Dict[str, int] = {"VEV_4000": 20, "VEV_5500": 30}
_VEV_MM_POS_CAP: Dict[str, int] = {"VEV_4000": 100, "VEV_5500": 200}

# Friend's two key safeties (port from working +16.7k submission):
_VEV_MIN_DOLLAR_VEGA = 1.0   # skip mean-revert when vega*lot < $1 (low conviction)
_VEV_PAIRWISE_ARB_LOT = 25   # max size per arb leg

_HESTON_ALPHA = 0.005
_HESTON_TICKS_PER_YEAR = 10_000 * 365
_HESTON_VOL_FLOOR = 0.10
_HESTON_VOL_CEILING = 0.60
_HESTON_DEFAULT_VOL = 0.234

_TICKS_PER_DAY = 1_000_000

# Round 3 TTE schedule: each backtest "day" advances expiry by 1 day.
# Index 0 = first day seen, etc. Cap at 1 day floor for late days.
_TTE_SCHEDULE_DAYS = [8.0, 7.0, 6.0, 5.0, 4.0, 3.0, 2.0, 1.0]

# Mutable holder so _vev_tte_years can pick up the current day's TTE.
_CURRENT_START_TTE_DAYS = [_TTE_SCHEDULE_DAYS[0]]


def _detect_and_update_day(data: dict, timestamp: int) -> None:
    last_ts = data.get("last_ts", -1)
    day_index = data.get("day_index", 0)
    if last_ts > timestamp:
        day_index += 1
        data["day_index"] = day_index
    data["last_ts"] = timestamp
    capped = min(day_index, len(_TTE_SCHEDULE_DAYS) - 1)
    _CURRENT_START_TTE_DAYS[0] = _TTE_SCHEDULE_DAYS[capped]

HYDROGEL_FAIR_SEED = 9_991.0
HYDROGEL_FAIR_ALPHA = 0.002
HYDROGEL_LIMIT = 200
HYDROGEL_POST_EDGE = 2
HYDROGEL_TAKE_EDGE = 20
HYDROGEL_TARGET_SCALE = 40
HYDROGEL_MAX_TAKE_SIZE = 10

VELVETFRUIT_ANCHOR_SEED = 5_255.0
VELVETFRUIT_ANCHOR_ALPHA = 0.002
VELVETFRUIT_LIMIT = 200
VELVETFRUIT_ENTRY_EDGE = 10.0
VELVETFRUIT_CLIP = 20


# TODO(Kieran): pick the seed-vs-detected weight.
# Friend's hardcoded values won by creating a bias offset (mean ~9979 vs seed 9991
# = permanent +60 long that captured drift). Pure cumulative-mean detection LOST
# that alpha and dropped HYDROGEL from +11k -> -5.7k on IMC.
#
#   weight = 1.0  -> pure friend's seed (proven to work, but no adaptation)
#   weight = 0.95 -> mostly seed, slowly drifts if seed is far from observed mean
#   weight = 0.5  -> equal blend
#   weight = 0.0  -> pure cumulative mean (proven to lose)
_FAIR_SEED_WEIGHT = 1.0  # pure seed: revert to friend's proven 9991/5255 baseline


def _detect_dynamic_fair(
    data: dict, key: str, mid: float | None, alpha: float, seed: float
) -> float:
    if mid is None:
        return data.get(key, seed)
    n_key = f"{key}_n"
    n = data.get(n_key, 0) + 1
    prev_mean = data.get(f"{key}_mean", mid)
    cum_mean = prev_mean + (mid - prev_mean) / n
    data[n_key] = n
    data[f"{key}_mean"] = cum_mean
    fair = _FAIR_SEED_WEIGHT * seed + (1.0 - _FAIR_SEED_WEIGHT) * cum_mean
    data[key] = fair
    return fair


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
        _detect_and_update_day(data, state.timestamp)
        result: Dict[str, List[Order]] = {}
        spot_depth = state.order_depths.get(VELVETFRUIT_EXTRACT)
        # Outer-wall mid = (min_buy + max_sell) / 2. More stable than top-of-book
        # because it's anchored on the deepest resting orders, not penny-jumpers.
        # Friend uses this for VEV pricing and it cuts VEV losses ~80%.
        spot_mid = _outer_wall_mid(spot_depth) if spot_depth is not None else None
        velvetfruit_anchor = _detect_dynamic_fair(
            data, "velvetfruit_anchor", spot_mid, VELVETFRUIT_ANCHOR_ALPHA, VELVETFRUIT_ANCHOR_SEED
        )

        hydrogel_depth = state.order_depths.get(HYDROGEL_PACK)
        hydrogel_mid = _wall_mid(hydrogel_depth) if hydrogel_depth is not None else None
        hydrogel_fair = _detect_dynamic_fair(
            data, "hydrogel_fair", hydrogel_mid, HYDROGEL_FAIR_ALPHA, HYDROGEL_FAIR_SEED
        )

        if "HYDROGEL" in _ENABLED_PRODUCTS and HYDROGEL_PACK in state.order_depths:
            result[HYDROGEL_PACK] = _trade_hydrogel(
                state.order_depths[HYDROGEL_PACK],
                state.position.get(HYDROGEL_PACK, 0),
                hydrogel_fair,
            )

        if "VELVETFRUIT" in _ENABLED_PRODUCTS and VELVETFRUIT_EXTRACT in state.order_depths:
            orders = _trade_velvetfruit(
                state.order_depths[VELVETFRUIT_EXTRACT],
                state.position.get(VELVETFRUIT_EXTRACT, 0),
                velvetfruit_anchor,
            )
            if orders:
                result[VELVETFRUIT_EXTRACT] = orders

        option_gross = _vev_gross_position(state.position)
        portfolio_delta = _vev_portfolio_delta(state, spot_mid)
        tracked_vol = _update_tracked_vol(data, spot_mid)

        # Pairwise no-arb sweep — risk-free profit when bid(low_K) - ask(high_K) > strike_diff.
        # This is friend's day-2 PnL bump. Runs BEFORE per-strike strategies so arb wins use up capacity first.
        if "VEV" in _ENABLED_PRODUCTS:
            _vev_pairwise_arb(state, result)

        if "VEV" in _ENABLED_PRODUCTS and spot_mid is not None:
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
                    tracked_vol,
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


def _outer_wall_mid(od: OrderDepth) -> float | None:
    if not od.buy_orders or not od.sell_orders:
        return None
    return (min(od.buy_orders) + max(od.sell_orders)) / 2.0


def _bs_vega(spot: float, strike: float, tte_years: float, vol: float) -> float:
    from math import exp, pi
    if tte_years <= 0.0 or spot <= 0.0 or strike <= 0.0:
        return 0.0
    scaled_vol = max(vol, 0.05) * sqrt(tte_years)
    if scaled_vol <= 0.0:
        return 0.0
    d1 = (log(spot / strike) + 0.5 * vol * vol * tte_years) / scaled_vol
    return spot * sqrt(tte_years) * exp(-0.5 * d1 * d1) / sqrt(2 * pi)


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
    return max(0.5, _CURRENT_START_TTE_DAYS[0] - fraction) / 365.0


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


def _vev_gross_position(position: Dict[str, int]) -> int:
    return sum(abs(position.get(sym, 0)) for sym in _VEV_ACTIVE_SYMBOLS)


def _vev_portfolio_delta(state: TradingState, spot_mid: float | None) -> float:
    if spot_mid is None:
        return float(state.position.get(VELVETFRUIT_EXTRACT, 0))
    total = float(state.position.get(VELVETFRUIT_EXTRACT, 0))
    for sym in _VEV_ACTIVE_SYMBOLS:
        total += state.position.get(sym, 0) * _vev_delta(sym, spot_mid, state.timestamp)
    return total


def _trade_hydrogel(od: OrderDepth, position: int, fair_value: float) -> List[Order]:
    current_mid = _wall_mid(od)
    target_position = 0
    if current_mid is not None:
        raw_target = round(
            (fair_value - current_mid) / HYDROGEL_TARGET_SCALE * HYDROGEL_CONFIG.limit
        )
        target_position = max(-HYDROGEL_CONFIG.limit, min(HYDROGEL_CONFIG.limit, raw_target))

    return _trade_dynamic_product(
        HYDROGEL_CONFIG,
        od,
        position,
        fair_value,
        max_take_size=HYDROGEL_MAX_TAKE_SIZE,
        skip_oversized_take=False,
        take_edge=HYDROGEL_TAKE_EDGE,
        target_position=target_position,
    )


def _trade_velvetfruit(od: OrderDepth, position: int, anchor: float) -> List[Order]:
    bid = _best_bid(od)
    ask = _best_ask(od)
    if bid is None or ask is None:
        return []
    mid = (bid + ask) / 2.0
    orders: List[Order] = []

    if mid < anchor - VELVETFRUIT_ENTRY_EDGE and position < VELVETFRUIT_LIMIT:
        ask_qty = abs(od.sell_orders[ask])
        qty = min(VELVETFRUIT_CLIP, ask_qty, VELVETFRUIT_LIMIT - position)
        if qty > 0:
            orders.append(Order(VELVETFRUIT_EXTRACT, ask, qty))
    elif mid > anchor + VELVETFRUIT_ENTRY_EDGE and position > -VELVETFRUIT_LIMIT:
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
    tracked_vol: float,
) -> List[Order]:
    if sym in _VEV_MM_BID_STRIKES:
        return _vev_passive_bid(sym, od, position)
    if sym in _VEV_MM_ASK_STRIKES:
        return _vev_passive_ask(sym, od, position)
    return _vev_mean_revert(sym, od, position, spot_mid, timestamp, option_gross, tracked_vol)


def _vev_passive_bid(sym: str, od: OrderDepth, position: int) -> List[Order]:
    bid = _best_bid(od)
    ask = _best_ask(od)
    if bid is None or ask is None:
        return []
    market_mid = (bid + ask) / 2.0
    cap = _VEV_MM_POS_CAP[sym]
    headroom = cap - position
    if headroom <= 0:
        return []
    quote_price = floor(market_mid - _VEV_MM_BID_OFFSET[sym])
    if quote_price <= 0:
        return []
    return [Order(sym, quote_price, min(_VEV_MM_LOT[sym], headroom))]


def _vev_passive_ask(sym: str, od: OrderDepth, position: int) -> List[Order]:
    bid = _best_bid(od)
    ask = _best_ask(od)
    if bid is None or ask is None:
        return []
    market_mid = (bid + ask) / 2.0
    cap = _VEV_MM_POS_CAP[sym]
    headroom = cap + position
    if headroom <= 0:
        return []
    quote_price = ceil(market_mid + _VEV_MM_ASK_OFFSET[sym])
    return [Order(sym, quote_price, -min(_VEV_MM_LOT[sym], headroom))]


def _vev_mean_revert(
    sym: str,
    od: OrderDepth,
    position: int,
    spot_mid: float,
    timestamp: int,
    option_gross: int,
    tracked_vol: float,
) -> List[Order]:
    bid = _best_bid(od)
    ask = _best_ask(od)
    if bid is None or ask is None:
        return []
    tte = _vev_tte_years(timestamp)
    strike = _VEV_STRIKES[sym]
    fair = _bs_call(spot_mid, strike, tte, tracked_vol)
    # Skip when vega exposure is tiny — IV signal is too noisy to bet on.
    if _bs_vega(spot_mid, strike, tte, tracked_vol) * _VEV_LOT[sym] < _VEV_MIN_DOLLAR_VEGA:
        return []
    market_mid = (bid + ask) / 2.0
    edge = market_mid - fair
    entry_threshold = _VEV_ENTRY_EDGE[sym]
    pos_cap = _VEV_POS_CAP[sym]

    if edge < -entry_threshold and position < pos_cap:
        return _vev_buy(sym, ask, od.sell_orders[ask], position, pos_cap, option_gross)
    if edge > entry_threshold and position > -pos_cap:
        return _vev_sell(sym, bid, od.buy_orders[bid], position, pos_cap, option_gross)
    return []


def _update_tracked_vol(data: dict, spot_mid: float | None) -> float:
    last_spot = data.get("last_spot")
    realized_var = data.get("realized_var", _HESTON_DEFAULT_VOL ** 2)
    if spot_mid is not None and last_spot is not None and last_spot > 0:
        log_ret = log(spot_mid / last_spot)
        instant_var_annual = log_ret * log_ret * _HESTON_TICKS_PER_YEAR
        realized_var = _HESTON_ALPHA * instant_var_annual + (1 - _HESTON_ALPHA) * realized_var
    if spot_mid is not None:
        data["last_spot"] = spot_mid
    data["realized_var"] = realized_var
    tracked_vol = sqrt(max(realized_var, _HESTON_VOL_FLOOR ** 2))
    return min(tracked_vol, _HESTON_VOL_CEILING)


def _vev_buy(sym, ask, ask_qty, position, pos_cap, option_gross) -> List[Order]:
    if option_gross >= _VEV_GROSS_CAP:
        return []
    headroom = pos_cap - position
    qty = min(_VEV_LOT[sym], abs(ask_qty), headroom)
    if qty <= 0:
        return []
    return [Order(sym, ask, qty)]


def _vev_sell(sym, bid, bid_qty, position, pos_cap, option_gross) -> List[Order]:
    if option_gross >= _VEV_GROSS_CAP:
        return []
    headroom = pos_cap + position
    qty = min(_VEV_LOT[sym], bid_qty, headroom)
    if qty <= 0:
        return []
    return [Order(sym, bid, -qty)]


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


def _vev_pairwise_arb(state: TradingState, result: Dict[str, List[Order]]) -> None:
    """Risk-free no-arb sweep over all VEV strike pairs.

    For two strikes K_lo < K_hi, the no-arb bound says:
        C(K_lo) - C(K_hi) <= K_hi - K_lo
    So if bid(K_lo) - ask(K_hi) > strike_diff, we sell the low strike + buy the high strike
    and lock in the difference. Symmetrically: if bid(K_hi) > ask(K_lo) we sell high, buy low.
    """
    bids: Dict[str, tuple] = {}
    asks: Dict[str, tuple] = {}
    for sym in _VEV_ACTIVE_SYMBOLS:
        od = state.order_depths.get(sym)
        if od is None:
            continue
        b = _best_bid(od)
        a = _best_ask(od)
        if b is not None:
            bids[sym] = (b, od.buy_orders[b])
        if a is not None:
            asks[sym] = (a, abs(od.sell_orders[a]))

    syms = list(_VEV_ACTIVE_SYMBOLS)
    for i in range(len(syms)):
        for j in range(i + 1, len(syms)):
            a_sym, b_sym = syms[i], syms[j]
            if _VEV_STRIKES[a_sym] > _VEV_STRIKES[b_sym]:
                a_sym, b_sym = b_sym, a_sym
            k_lo = _VEV_STRIKES[a_sym]
            k_hi = _VEV_STRIKES[b_sym]
            strike_diff = k_hi - k_lo

            if a_sym in bids and b_sym in asks:
                bid_p, bid_v = bids[a_sym]
                ask_p, ask_v = asks[b_sym]
                if bid_p - ask_p > strike_diff:
                    qty = min(bid_v, ask_v, _VEV_PAIRWISE_ARB_LOT)
                    qty = min(qty, _arb_capacity(result, a_sym, "sell", state.position.get(a_sym, 0)))
                    qty = min(qty, _arb_capacity(result, b_sym, "buy", state.position.get(b_sym, 0)))
                    if qty > 0:
                        result.setdefault(a_sym, []).append(Order(a_sym, bid_p, -qty))
                        result.setdefault(b_sym, []).append(Order(b_sym, ask_p, qty))

            if b_sym in bids and a_sym in asks:
                bid_p, bid_v = bids[b_sym]
                ask_p, ask_v = asks[a_sym]
                if bid_p > ask_p:
                    qty = min(bid_v, ask_v, _VEV_PAIRWISE_ARB_LOT)
                    qty = min(qty, _arb_capacity(result, b_sym, "sell", state.position.get(b_sym, 0)))
                    qty = min(qty, _arb_capacity(result, a_sym, "buy", state.position.get(a_sym, 0)))
                    if qty > 0:
                        result.setdefault(b_sym, []).append(Order(b_sym, bid_p, -qty))
                        result.setdefault(a_sym, []).append(Order(a_sym, ask_p, qty))


def _arb_capacity(result: Dict[str, List[Order]], sym: str, side: str, position: int) -> int:
    used = 0
    for order in result.get(sym, []):
        if side == "buy" and order.quantity > 0:
            used += order.quantity
        elif side == "sell" and order.quantity < 0:
            used += -order.quantity
    if side == "buy":
        return max(0, _VEV_LIMIT - position - used)
    return max(0, _VEV_LIMIT + position - used)
