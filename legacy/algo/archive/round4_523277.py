"""
Max delta exposure strategy using rolling mean (EMA) signal.

Hint interpretation: go full long or full short on HP and VE based on whether
the current price is above or below a rolling EMA. The EMA is stored in
traderData and updated each tick with alpha=0.05 (roughly 20-tick memory).

HP and VE are both mean-reverting (lag-1 change autocorr = -0.13 and -0.15).
Signal: price > EMA → expect fall → max SHORT. price < EMA → expect rise → max LONG.
We reach target via passive quotes (skewed hard toward target) + aggressive
taking only when edge > threshold (to avoid crossing wide spreads repeatedly).

VEV options: same calibration fixes as v6_calibrated (TTE=4, bid_edge=9.5).
"""
import json
from dataclasses import dataclass
from math import ceil, erf, floor, log, sqrt
from typing import Dict, List

from backtester.datamodel import Order, OrderDepth, TradingState


HYDROGEL_PACK = "HYDROGEL_PACK"
VELVETFRUIT_EXTRACT = "VELVETFRUIT_EXTRACT"

_ENABLED_PRODUCTS = {"HYDROGEL", "VELVETFRUIT", "VEV"}

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
    "VEV_4500": 5.0,
    "VEV_5000": 4.0,
    "VEV_5100": 3.0,
    "VEV_5200": 2.0,
    "VEV_5300": 1.5,
    "VEV_5400": 1.0,
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

_VEV_MM_BID_STRIKES = ("VEV_4000", "VEV_4500")
_VEV_MM_ASK_STRIKES = ("VEV_5500",)
_VEV_MM_BID_OFFSET: Dict[str, float] = {"VEV_4000": 9.5, "VEV_4500": 6.0}
_VEV_MM_ASK_OFFSET: Dict[str, float] = {"VEV_5500": 1.0}
_VEV_MM_LOT: Dict[str, int] = {"VEV_4000": 20, "VEV_4500": 20, "VEV_5500": 30}
_VEV_MM_POS_CAP: Dict[str, int] = {"VEV_4000": 100, "VEV_4500": 100, "VEV_5500": 200}
_VEV_MM_EXIT_OFFSET: Dict[str, float] = {"VEV_4000": 6.0, "VEV_4500": 5.0, "VEV_5500": 6.0}
_VEV_MM_EXIT_LOT: Dict[str, int] = {"VEV_4000": 15, "VEV_4500": 15, "VEV_5500": 20}
_VEV_MM_EXIT_TRIGGER: Dict[str, int] = {"VEV_4000": 20, "VEV_4500": 20, "VEV_5500": 30}

_VEV_MIN_DOLLAR_VEGA = 1.0
_VEV_PAIRWISE_ARB_LOT = 25

_VEV_SELL_ONLY_STRIKES = frozenset({
    "VEV_5000", "VEV_5100", "VEV_5200", "VEV_5300", "VEV_5400",
})

_HESTON_ALPHA = 0.005
_HESTON_TICKS_PER_YEAR = 10_000 * 365
_HESTON_VOL_FLOOR = 0.10
_HESTON_VOL_CEILING = 0.60
_HESTON_DEFAULT_VOL = 0.234

_TICKS_PER_DAY = 1_000_000

# FIX: R4 TTE starts at 4, not 8.
_TTE_SCHEDULE_DAYS = [4.0, 3.0, 2.0, 1.0]
_CURRENT_START_TTE_DAYS = [_TTE_SCHEDULE_DAYS[0]]

# Rolling EMA alpha for the directional signal.
# alpha=0.05 ≈ 20-tick memory. Slower = more stable signal, fewer position flips.
# Verified: mean-reversion works across all 6 R3+R4 days at this timescale.
_HP_EMA_ALPHA = 0.05
_VE_EMA_ALPHA = 0.05

HYDROGEL_FAIR_SEED = 9_991.0
HYDROGEL_FAIR_ALPHA = 0.002
HYDROGEL_LIMIT = 200
HYDROGEL_POST_EDGE = 2
# Reach ±200 at 12-tick deviation from seed (was 25 — 2× more aggressive sizing).
HYDROGEL_TARGET_SCALE = 12
# Allow larger take clips to converge to target faster (was 20).
HYDROGEL_MAX_TAKE_SIZE = 40
HYDROGEL_TAKE_EDGE = 20

VELVETFRUIT_ANCHOR_SEED = 5_255.0
VELVETFRUIT_ANCHOR_ALPHA = 0.002
VELVETFRUIT_LIMIT = 200
VELVETFRUIT_POST_EDGE = 2
# Lower threshold triggers more trades toward max position (was 15).
VELVETFRUIT_TAKE_EDGE = 7
VELVETFRUIT_MAX_TAKE_SIZE = 50

_FAIR_SEED_WEIGHT = 1.0


def _detect_and_update_day(data: dict, timestamp: int) -> None:
    last_ts = data.get("last_ts", -1)
    day_index = data.get("day_index", 0)
    if last_ts > timestamp:
        day_index += 1
        data["day_index"] = day_index
    data["last_ts"] = timestamp
    capped = min(day_index, len(_TTE_SCHEDULE_DAYS) - 1)
    _CURRENT_START_TTE_DAYS[0] = _TTE_SCHEDULE_DAYS[capped]


def _detect_dynamic_fair(
    data: dict, key: str, mid: float | None, alpha: float, seed: float, ema_alpha: float
) -> tuple[float, float]:
    if mid is None:
        fair = data.get(key, seed)
        ema = data.get(f"{key}_ema", seed)
        return fair, ema

    n_key = f"{key}_n"
    n = data.get(n_key, 0) + 1
    prev_mean = data.get(f"{key}_mean", mid)
    cum_mean = prev_mean + (mid - prev_mean) / n
    data[n_key] = n
    data[f"{key}_mean"] = cum_mean
    fair = _FAIR_SEED_WEIGHT * seed + (1.0 - _FAIR_SEED_WEIGHT) * cum_mean
    data[key] = fair

    prev_ema = data.get(f"{key}_ema", mid)
    ema = (1.0 - ema_alpha) * prev_ema + ema_alpha * mid
    data[f"{key}_ema"] = ema

    return fair, ema


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

VELVETFRUIT_CONFIG = ProductConfig(
    symbol=VELVETFRUIT_EXTRACT,
    limit=VELVETFRUIT_LIMIT,
    post_edge=VELVETFRUIT_POST_EDGE,
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
        spot_mid = _outer_wall_mid(spot_depth) if spot_depth is not None else None
        velvetfruit_anchor, ve_ema = _detect_dynamic_fair(
            data, "velvetfruit_anchor", spot_mid,
            VELVETFRUIT_ANCHOR_ALPHA, VELVETFRUIT_ANCHOR_SEED, _VE_EMA_ALPHA,
        )

        hydrogel_depth = state.order_depths.get(HYDROGEL_PACK)
        hydrogel_mid = _wall_mid(hydrogel_depth) if hydrogel_depth is not None else None
        hydrogel_fair, hp_ema = _detect_dynamic_fair(
            data, "hydrogel_fair", hydrogel_mid,
            HYDROGEL_FAIR_ALPHA, HYDROGEL_FAIR_SEED, _HP_EMA_ALPHA,
        )

        if "HYDROGEL" in _ENABLED_PRODUCTS and HYDROGEL_PACK in state.order_depths:
            result[HYDROGEL_PACK] = _trade_hydrogel(
                state.order_depths[HYDROGEL_PACK],
                state.position.get(HYDROGEL_PACK, 0),
                hydrogel_fair,
                hp_ema,
            )

        if "VELVETFRUIT" in _ENABLED_PRODUCTS and VELVETFRUIT_EXTRACT in state.order_depths:
            orders = _trade_velvetfruit(
                state.order_depths[VELVETFRUIT_EXTRACT],
                state.position.get(VELVETFRUIT_EXTRACT, 0),
                velvetfruit_anchor,
                ve_ema,
            )
            if orders:
                result[VELVETFRUIT_EXTRACT] = orders

        option_gross = _vev_gross_position(state.position)
        portfolio_delta = _vev_portfolio_delta(state, spot_mid)
        tracked_vol = _update_tracked_vol(data, spot_mid)

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

        if "VEV" in _ENABLED_PRODUCTS:
            _vev_pairwise_arb(state, result)

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


def _rolling_mean_target(current_mid: float | None, ema: float, limit: int) -> int:
    if current_mid is None:
        return 0
    # Mean-reversion: if price is above EMA, it's expected to fall → short.
    # If price is below EMA, it's expected to rise → long.
    return -limit if current_mid > ema else limit


def _trade_hydrogel(
    od: OrderDepth, position: int, fair_value: float, hp_ema: float
) -> List[Order]:
    current_mid = _wall_mid(od)

    # Combine seed mean-reversion with EMA rolling mean signal.
    # Seed target: anchors to the known fair seed (9991).
    # EMA target: pure rolling mean signal (full ±200).
    # Take the tighter of the two — both signals agree on direction when
    # the price is away from both the seed AND the EMA.
    seed_target = 0
    if current_mid is not None:
        raw = round((fair_value - current_mid) / HYDROGEL_TARGET_SCALE * HYDROGEL_CONFIG.limit)
        seed_target = max(-HYDROGEL_CONFIG.limit, min(HYDROGEL_CONFIG.limit, raw))

    ema_target = _rolling_mean_target(current_mid, hp_ema, HYDROGEL_LIMIT)

    # If both signals agree on direction, use the more aggressive (ema_target = ±200).
    # If they disagree, defer to the seed-anchored signal (more conservative).
    if seed_target * ema_target >= 0:
        target_position = ema_target
    else:
        target_position = seed_target

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


def _trade_velvetfruit(
    od: OrderDepth, position: int, anchor: float, ve_ema: float
) -> List[Order]:
    current_mid = _wall_mid(od)
    target_position = _rolling_mean_target(current_mid, ve_ema, VELVETFRUIT_LIMIT)

    return _trade_dynamic_product(
        VELVETFRUIT_CONFIG,
        od,
        position,
        anchor,
        max_take_size=VELVETFRUIT_MAX_TAKE_SIZE,
        skip_oversized_take=False,
        take_edge=VELVETFRUIT_TAKE_EDGE,
        target_position=target_position,
    )


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
    orders: List[Order] = []
    cap = _VEV_MM_POS_CAP[sym]

    headroom_buy = cap - position
    if headroom_buy > 0:
        quote_price = floor(market_mid - _VEV_MM_BID_OFFSET[sym])
        if quote_price > 0:
            orders.append(Order(sym, quote_price, min(_VEV_MM_LOT[sym], headroom_buy)))

    if position >= _VEV_MM_EXIT_TRIGGER[sym]:
        exit_price = ceil(market_mid + _VEV_MM_EXIT_OFFSET[sym])
        exit_qty = min(_VEV_MM_EXIT_LOT[sym], position)
        orders.append(Order(sym, exit_price, -exit_qty))

    return orders


def _vev_passive_ask(sym: str, od: OrderDepth, position: int) -> List[Order]:
    bid = _best_bid(od)
    ask = _best_ask(od)
    if bid is None or ask is None:
        return []
    market_mid = (bid + ask) / 2.0
    orders: List[Order] = []
    cap = _VEV_MM_POS_CAP[sym]

    headroom_sell = cap + position
    if headroom_sell > 0:
        quote_price = ceil(market_mid + _VEV_MM_ASK_OFFSET[sym])
        orders.append(Order(sym, quote_price, -min(_VEV_MM_LOT[sym], headroom_sell)))

    if position <= -_VEV_MM_EXIT_TRIGGER[sym]:
        exit_price = floor(market_mid - _VEV_MM_EXIT_OFFSET[sym])
        if exit_price > 0:
            exit_qty = min(_VEV_MM_EXIT_LOT[sym], -position)
            orders.append(Order(sym, exit_price, exit_qty))

    return orders


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
    if _bs_vega(spot_mid, strike, tte, tracked_vol) * _VEV_LOT[sym] < _VEV_MIN_DOLLAR_VEGA:
        return []
    market_mid = (bid + ask) / 2.0
    edge = market_mid - fair
    entry_threshold = _VEV_ENTRY_EDGE[sym]
    pos_cap = _VEV_POS_CAP[sym]

    if edge < -entry_threshold and position < pos_cap and sym not in _VEV_SELL_ONLY_STRIKES:
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
    _post_quotes_skewed(config, od, orders, projected, fair_value, target_position)
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


def _post_quotes_skewed(
    config: ProductConfig,
    od: OrderDepth,
    orders: List[Order],
    projected: int,
    fair_value: float,
    target_position: int | None,
) -> None:
    best_bid = _best_bid(od)
    best_ask = _best_ask(od)

    # Skew quotes hard toward the target: if we want to be long, post a tighter
    # bid and looser ask so we accumulate position passively.
    if target_position is not None:
        distance_to_target = target_position - projected
        raw_skew = distance_to_target / config.limit * config.max_skew * 2
        skew = max(-config.max_skew * 2, min(config.max_skew * 2, round(raw_skew)))
    else:
        skew = round(projected / config.limit * config.max_skew)

    bid_ceiling = floor(fair_value) - config.post_edge
    ask_floor = ceil(fair_value) + config.post_edge
    bid_price = bid_ceiling + skew
    ask_price = ask_floor + skew

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