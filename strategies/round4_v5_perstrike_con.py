import json
from dataclasses import dataclass
from math import ceil, erf, floor, log, sqrt
from typing import Dict, List, Tuple

from backtester.datamodel import Order, OrderDepth, TradingState


HYDROGEL_PACK = "HYDROGEL_PACK"
VELVETFRUIT_EXTRACT = "VELVETFRUIT_EXTRACT"

# ---------------------------------------------------------------------------
# HYDROGEL — exact 522219.py logic (fixed fair value, no EMA)
# ---------------------------------------------------------------------------

HYDROGEL_FAIR_VALUE = 10_000.0
HYDROGEL_LIMIT = 200
HYDROGEL_POST_EDGE = 3
HYDROGEL_TAKE_EDGE = 20
HYDROGEL_TARGET_SCALE = 40
HYDROGEL_MAX_TAKE_SIZE = 10


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

# ---------------------------------------------------------------------------
# VELVETFRUIT — r4_v6_directional EMA rolling mean + passive quoting
# ---------------------------------------------------------------------------

VELVETFRUIT_ANCHOR_SEED = 5_255.0
VELVETFRUIT_LIMIT = 200
VELVETFRUIT_POST_EDGE = 2
VELVETFRUIT_TAKE_EDGE = 7
VELVETFRUIT_MAX_TAKE_SIZE = 50
_VE_EMA_ALPHA = 0.05

VELVETFRUIT_CONFIG = ProductConfig(
    symbol=VELVETFRUIT_EXTRACT,
    limit=VELVETFRUIT_LIMIT,
    post_edge=VELVETFRUIT_POST_EDGE,
    max_skew=3,
    quote_size=40,
)

# ---------------------------------------------------------------------------
# VEV options — r4_v6_directional with TTE fix and bid_edge=9.5
# ---------------------------------------------------------------------------

_VEV_ACTIVE_SYMBOLS = (
    "VEV_4000", "VEV_4500", "VEV_5000", "VEV_5100",
    "VEV_5200", "VEV_5300", "VEV_5400", "VEV_5500",
)
_VEV_STRIKES: Dict[str, float] = {
    "VEV_4000": 4000.0, "VEV_4500": 4500.0, "VEV_5000": 5000.0,
    "VEV_5100": 5100.0, "VEV_5200": 5200.0, "VEV_5300": 5300.0,
    "VEV_5400": 5400.0, "VEV_5500": 5500.0,
}
_VEV_PRIOR_IV: Dict[str, float] = {
    "VEV_4000": 0.234, "VEV_4500": 0.234, "VEV_5000": 0.234,
    "VEV_5100": 0.232, "VEV_5200": 0.234, "VEV_5300": 0.237,
    "VEV_5400": 0.222, "VEV_5500": 0.241,
}
_VEV_ENTRY_EDGE: Dict[str, float] = {
    "VEV_4000": 3.0, "VEV_4500": 5.0, "VEV_5000": 4.0, "VEV_5100": 3.0,
    "VEV_5200": 2.0, "VEV_5300": 1.5, "VEV_5400": 1.0, "VEV_5500": 0.4,
}
# 538568 friend bumped middle-strike caps + lots; gained +1,410 live.
_VEV_POS_CAP: Dict[str, int] = {
    "VEV_4000": 100, "VEV_4500": 100, "VEV_5000": 150, "VEV_5100": 150,
    "VEV_5200": 175, "VEV_5300": 175, "VEV_5400": 225, "VEV_5500": 200,
}
_VEV_LOT: Dict[str, int] = {
    "VEV_4000": 20, "VEV_4500": 20, "VEV_5000": 25, "VEV_5100": 25,
    "VEV_5200": 30, "VEV_5300": 30, "VEV_5400": 45, "VEV_5500": 40,
}
_VEV_LIMIT = 300
_VEV_GROSS_CAP = 1_500
_VEV_PORTFOLIO_DELTA_CAP = 1_500.0

# 538568 made VEV_4000 two-sided (bid AND ask) — gained +219 live by farming
# Mark 14/Mark 38 in both directions instead of one-sided take.
# VEV_4500 stays disabled (still -44 live in 538568, structural bleed).
_VEV_MM_BID_STRIKES: Tuple[str, ...] = ("VEV_4000",)
_VEV_MM_ASK_STRIKES: Tuple[str, ...] = ("VEV_4000", "VEV_5500")
_VEV_MM_BID_OFFSET: Dict[str, float] = {"VEV_4000": 9.5, "VEV_4500": 6.0}
_VEV_MM_ASK_OFFSET: Dict[str, float] = {"VEV_4000": 9.5, "VEV_5500": 1.0}
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

# Per-strike smile shape, baked from the static prior table.
# Heston gives a single ATM vol; the smile is the dispersion across strikes.
# offset[sym] = prior_iv[sym] - mean(prior_iv)  -> additive smile correction.
_VEV_SMILE_ATM = sum(_VEV_PRIOR_IV.values()) / len(_VEV_PRIOR_IV)
_VEV_SMILE_OFFSET: Dict[str, float] = {
    sym: iv - _VEV_SMILE_ATM for sym, iv in _VEV_PRIOR_IV.items()
}

# Per-strike smile strength. Each strike's offset is multiplied by its own
# strength, so a strike whose live IV matches the R3 prior (5300) can stay
# at 0 while a strike whose R3 prior is consistently underpriced vs ATM
# (5100, 5400) can push strength much higher. Default 5.0 = uniform smile.
_SMILE_STRENGTH_PER_STRIKE: Dict[str, float] = {
    "VEV_4000": 5.0, "VEV_4500": 5.0, "VEV_5000": 5.0, "VEV_5100": 10.0,
    "VEV_5200": 5.0, "VEV_5300": 5.0, "VEV_5400": 10.0, "VEV_5500": 5.0,
}

_TICKS_PER_DAY = 1_000_000
_TTE_SCHEDULE_DAYS = [4.0, 3.0, 2.0, 1.0]
_CURRENT_START_TTE_DAYS = [_TTE_SCHEDULE_DAYS[0]]


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------

class Trader:
    def run(
        self, state: TradingState
    ) -> Tuple[Dict[str, List[Order]], int, str]:
        data = _load_data(state.traderData)
        _detect_and_update_day(data, state.timestamp)
        result: Dict[str, List[Order]] = {}

        # HP — 522219 logic, no traderData needed
        if HYDROGEL_PACK in state.order_depths:
            orders = _trade_hydrogel(
                state.order_depths[HYDROGEL_PACK],
                state.position.get(HYDROGEL_PACK, 0),
            )
            if orders:
                result[HYDROGEL_PACK] = orders

        # VE — directional EMA signal
        spot_depth = state.order_depths.get(VELVETFRUIT_EXTRACT)
        spot_mid = _outer_wall_mid(spot_depth) if spot_depth is not None else None
        ve_anchor, ve_ema = _detect_ve_anchor_and_ema(data, spot_mid)

        if VELVETFRUIT_EXTRACT in state.order_depths:
            orders = _trade_velvetfruit(
                state.order_depths[VELVETFRUIT_EXTRACT],
                state.position.get(VELVETFRUIT_EXTRACT, 0),
                ve_anchor,
                ve_ema,
            )
            if orders:
                result[VELVETFRUIT_EXTRACT] = orders

        # VEV — directional with TTE fix and bid_edge=9.5
        tracked_vol = _update_tracked_vol(data, spot_mid)
        option_gross = _vev_gross_position(state.position)
        portfolio_delta = _vev_portfolio_delta(state, spot_mid)

        if spot_mid is not None:
            for sym in _VEV_ACTIVE_SYMBOLS:
                depth = state.order_depths.get(sym)
                if depth is None:
                    continue
                orders = _trade_vev(
                    sym, depth,
                    state.position.get(sym, 0),
                    spot_mid, state.timestamp,
                    option_gross, portfolio_delta, tracked_vol,
                )
                if orders:
                    result[sym] = orders

            _vev_pairwise_arb(state, result)

        return result, 0, json.dumps(data, separators=(",", ":"))


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _load_data(raw: str) -> dict:
    if not raw:
        return {}
    try:
        loaded = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _detect_and_update_day(data: dict, timestamp: int) -> None:
    last_ts = data.get("last_ts", -1)
    day_index = data.get("day_index", 0)
    if last_ts > timestamp:
        day_index += 1
        data["day_index"] = day_index
    data["last_ts"] = timestamp
    capped = min(day_index, len(_TTE_SCHEDULE_DAYS) - 1)
    _CURRENT_START_TTE_DAYS[0] = _TTE_SCHEDULE_DAYS[capped]


def _detect_ve_anchor_and_ema(
    data: dict, mid: float | None
) -> Tuple[float, float]:
    seed = VELVETFRUIT_ANCHOR_SEED
    if mid is None:
        return data.get("ve_anchor", seed), data.get("ve_ema", seed)

    n = data.get("ve_n", 0) + 1
    cum_mean = data.get("ve_mean", mid) + (mid - data.get("ve_mean", mid)) / n
    data["ve_n"] = n
    data["ve_mean"] = cum_mean
    data["ve_anchor"] = seed  # pure seed weight=1.0

    prev_ema = data.get("ve_ema", mid)
    ema = (1.0 - _VE_EMA_ALPHA) * prev_ema + _VE_EMA_ALPHA * mid
    data["ve_ema"] = ema

    return seed, ema


# ---------------------------------------------------------------------------
# Order book helpers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# HYDROGEL trading — 522219.py verbatim
# ---------------------------------------------------------------------------

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
    return _trade_hp(
        HYDROGEL_CONFIG, od, position, HYDROGEL_FAIR_VALUE,
        max_take_size=HYDROGEL_MAX_TAKE_SIZE,
        take_edge=HYDROGEL_TAKE_EDGE,
        target_position=target_position,
    )


def _trade_hp(
    config: ProductConfig, od: OrderDepth, position: int, fair_value: float,
    max_take_size: int | None, take_edge: int = 0, target_position: int | None = None,
) -> List[Order]:
    orders: List[Order] = []
    buy_cap = config.limit - position
    sell_cap = config.limit + position
    buy_taken, projected = _take_cheap_asks(
        config, od, orders, position, fair_value, take_edge, max_take_size, target_position, buy_cap,
    )
    sell_taken, projected = _take_rich_bids(
        config, od, orders, projected, fair_value, take_edge, max_take_size, target_position, sell_cap,
    )
    projected, buy_taken, sell_taken = _clear_at_fair(
        config, od, orders, projected, buy_taken, sell_taken, buy_cap, sell_cap, fair_value,
    )
    _post_quotes(config, od, orders, projected, buy_taken, sell_taken, buy_cap, sell_cap, fair_value)
    return orders


# ---------------------------------------------------------------------------
# VELVETFRUIT trading — r4_v6_directional EMA signal
# ---------------------------------------------------------------------------

def _trade_velvetfruit(
    od: OrderDepth, position: int, anchor: float, ve_ema: float,
) -> List[Order]:
    current_mid = _wall_mid(od)
    if current_mid is None:
        target_position = 0
    else:
        target_position = -VELVETFRUIT_LIMIT if current_mid > ve_ema else VELVETFRUIT_LIMIT

    orders: List[Order] = []
    buy_cap = VELVETFRUIT_CONFIG.limit - position
    sell_cap = VELVETFRUIT_CONFIG.limit + position
    buy_taken, projected = _take_cheap_asks(
        VELVETFRUIT_CONFIG, od, orders, position, anchor,
        VELVETFRUIT_TAKE_EDGE, VELVETFRUIT_MAX_TAKE_SIZE, target_position, buy_cap,
    )
    sell_taken, projected = _take_rich_bids(
        VELVETFRUIT_CONFIG, od, orders, projected, anchor,
        VELVETFRUIT_TAKE_EDGE, VELVETFRUIT_MAX_TAKE_SIZE, target_position, sell_cap,
    )
    projected, buy_taken, sell_taken = _clear_at_fair(
        VELVETFRUIT_CONFIG, od, orders, projected, buy_taken, sell_taken, buy_cap, sell_cap, anchor,
    )
    _post_quotes_skewed(
        VELVETFRUIT_CONFIG, od, orders, projected,
        buy_taken, sell_taken, buy_cap, sell_cap, anchor, target_position,
    )
    return orders


# ---------------------------------------------------------------------------
# Shared take / clear helpers
# ---------------------------------------------------------------------------

def _take_cheap_asks(
    config, od, orders, projected, fair_value,
    take_edge, max_take_size, target_position, buy_cap,
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
    config, od, orders, projected, fair_value,
    take_edge, max_take_size, target_position, sell_cap,
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


def _clear_at_fair(
    config, od, orders, projected,
    buy_taken, sell_taken, buy_cap, sell_cap, fair_value,
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
    config, od, orders, projected,
    buy_taken, sell_taken, buy_cap, sell_cap, fair_value,
) -> None:
    best_bid = _best_bid(od)
    best_ask = _best_ask(od)
    skew = round(projected / config.limit * config.max_skew)

    bid_price = floor(fair_value) - config.post_edge - skew
    ask_price = ceil(fair_value) + config.post_edge - skew

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


def _post_quotes_skewed(
    config, od, orders, projected,
    buy_taken, sell_taken, buy_cap, sell_cap, fair_value, target_position,
) -> None:
    best_bid = _best_bid(od)
    best_ask = _best_ask(od)

    if target_position is not None:
        distance = target_position - projected
        raw_skew = distance / config.limit * config.max_skew * 2
        skew = max(-config.max_skew * 2, min(config.max_skew * 2, round(raw_skew)))
    else:
        skew = round(projected / config.limit * config.max_skew)

    bid_price = floor(fair_value) - config.post_edge + skew
    ask_price = ceil(fair_value) + config.post_edge + skew

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


# ---------------------------------------------------------------------------
# Black-Scholes helpers
# ---------------------------------------------------------------------------

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


def _bs_vega(spot: float, strike: float, tte_years: float, vol: float) -> float:
    from math import exp, pi
    if tte_years <= 0.0 or spot <= 0.0 or strike <= 0.0:
        return 0.0
    scaled_vol = max(vol, 0.05) * sqrt(tte_years)
    if scaled_vol <= 0.0:
        return 0.0
    d1 = (log(spot / strike) + 0.5 * vol * vol * tte_years) / scaled_vol
    return spot * sqrt(tte_years) * exp(-0.5 * d1 * d1) / sqrt(2 * pi)


def _vev_tte_years(timestamp: int) -> float:
    fraction = max(0.0, min(1.0, timestamp / _TICKS_PER_DAY))
    return max(0.5, _CURRENT_START_TTE_DAYS[0] - fraction) / 365.0


def _vev_delta(sym: str, spot_mid: float, timestamp: int) -> float:
    return _bs_delta(spot_mid, _VEV_STRIKES[sym], _vev_tte_years(timestamp), _VEV_PRIOR_IV[sym])


# ---------------------------------------------------------------------------
# VEV position / portfolio tracking
# ---------------------------------------------------------------------------

def _vev_gross_position(position: Dict[str, int]) -> int:
    return sum(abs(position.get(sym, 0)) for sym in _VEV_ACTIVE_SYMBOLS)


def _vev_portfolio_delta(state: TradingState, spot_mid: float | None) -> float:
    if spot_mid is None:
        return float(state.position.get(VELVETFRUIT_EXTRACT, 0))
    total = float(state.position.get(VELVETFRUIT_EXTRACT, 0))
    for sym in _VEV_ACTIVE_SYMBOLS:
        total += state.position.get(sym, 0) * _vev_delta(sym, spot_mid, state.timestamp)
    return total


_IV_HARD_FLOOR = 0.05


def _iv_for_strike(sym: str, tracked_vol: float) -> float:
    # tracked_vol is the live Heston ATM vol (already clamped to [0.10, 0.60]).
    # Add the static smile offset scaled by _SMILE_STRENGTH so each strike gets
    # its own IV. Use only a hard safety floor here — re-clamping to the Heston
    # floor would erase any negative offset (e.g. VEV_5400 = -0.012).
    smile = _VEV_SMILE_OFFSET[sym] * _SMILE_STRENGTH_PER_STRIKE[sym]
    return max(_IV_HARD_FLOOR, tracked_vol + smile)


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
    return min(sqrt(max(realized_var, _HESTON_VOL_FLOOR ** 2)), _HESTON_VOL_CEILING)


# ---------------------------------------------------------------------------
# VEV trading
# ---------------------------------------------------------------------------

def _trade_vev(
    sym: str, od: OrderDepth, position: int,
    spot_mid: float, timestamp: int,
    option_gross: int, portfolio_delta: float, tracked_vol: float,
) -> List[Order]:
    is_bid_mm = sym in _VEV_MM_BID_STRIKES
    is_ask_mm = sym in _VEV_MM_ASK_STRIKES
    if is_bid_mm or is_ask_mm:
        orders: List[Order] = []
        if is_bid_mm:
            orders.extend(_vev_passive_bid(sym, od, position))
        if is_ask_mm:
            orders.extend(_vev_passive_ask(sym, od, position))
        return orders
    return _vev_mean_revert(sym, od, position, spot_mid, timestamp, option_gross, tracked_vol)


def _vev_passive_bid(sym: str, od: OrderDepth, position: int) -> List[Order]:
    bid = _best_bid(od)
    ask = _best_ask(od)
    if bid is None or ask is None:
        return []
    market_mid = (bid + ask) / 2.0
    orders: List[Order] = []
    cap = _VEV_MM_POS_CAP[sym]

    if cap - position > 0:
        quote_price = floor(market_mid - _VEV_MM_BID_OFFSET[sym])
        if quote_price > 0:
            orders.append(Order(sym, quote_price, min(_VEV_MM_LOT[sym], cap - position)))

    if position >= _VEV_MM_EXIT_TRIGGER[sym]:
        exit_price = ceil(market_mid + _VEV_MM_EXIT_OFFSET[sym])
        orders.append(Order(sym, exit_price, -min(_VEV_MM_EXIT_LOT[sym], position)))

    return orders


def _vev_passive_ask(sym: str, od: OrderDepth, position: int) -> List[Order]:
    bid = _best_bid(od)
    ask = _best_ask(od)
    if bid is None or ask is None:
        return []
    market_mid = (bid + ask) / 2.0
    orders: List[Order] = []
    cap = _VEV_MM_POS_CAP[sym]

    if cap + position > 0:
        quote_price = ceil(market_mid + _VEV_MM_ASK_OFFSET[sym])
        orders.append(Order(sym, quote_price, -min(_VEV_MM_LOT[sym], cap + position)))

    if position <= -_VEV_MM_EXIT_TRIGGER[sym]:
        exit_price = floor(market_mid - _VEV_MM_EXIT_OFFSET[sym])
        if exit_price > 0:
            orders.append(Order(sym, exit_price, min(_VEV_MM_EXIT_LOT[sym], -position)))

    return orders


def _vev_mean_revert(
    sym: str, od: OrderDepth, position: int,
    spot_mid: float, timestamp: int, option_gross: int, tracked_vol: float,
) -> List[Order]:
    bid = _best_bid(od)
    ask = _best_ask(od)
    if bid is None or ask is None:
        return []
    tte = _vev_tte_years(timestamp)
    strike = _VEV_STRIKES[sym]
    iv = _iv_for_strike(sym, tracked_vol)
    fair = _bs_call(spot_mid, strike, tte, iv)
    if _bs_vega(spot_mid, strike, tte, iv) * _VEV_LOT[sym] < _VEV_MIN_DOLLAR_VEGA:
        return []
    market_mid = (bid + ask) / 2.0
    edge = market_mid - fair
    pos_cap = _VEV_POS_CAP[sym]

    if edge < -_VEV_ENTRY_EDGE[sym] and position < pos_cap and sym not in _VEV_SELL_ONLY_STRIKES:
        if option_gross >= _VEV_GROSS_CAP:
            return []
        qty = min(_VEV_LOT[sym], abs(od.sell_orders[ask]), pos_cap - position)
        return [Order(sym, ask, qty)] if qty > 0 else []

    if edge > _VEV_ENTRY_EDGE[sym] and position > -pos_cap:
        if option_gross >= _VEV_GROSS_CAP:
            return []
        qty = min(_VEV_LOT[sym], od.buy_orders[bid], pos_cap + position)
        return [Order(sym, bid, -qty)] if qty > 0 else []

    return []


# ---------------------------------------------------------------------------
# Pairwise no-arb sweep
# ---------------------------------------------------------------------------

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
            lo, hi = syms[i], syms[j]
            if _VEV_STRIKES[lo] > _VEV_STRIKES[hi]:
                lo, hi = hi, lo
            strike_diff = _VEV_STRIKES[hi] - _VEV_STRIKES[lo]

            if lo in bids and hi in asks:
                bp, bv = bids[lo]
                ap, av = asks[hi]
                if bp - ap > strike_diff:
                    qty = min(bv, av, _VEV_PAIRWISE_ARB_LOT,
                              _arb_cap(result, lo, "sell", state.position.get(lo, 0)),
                              _arb_cap(result, hi, "buy", state.position.get(hi, 0)))
                    if qty > 0:
                        result.setdefault(lo, []).append(Order(lo, bp, -qty))
                        result.setdefault(hi, []).append(Order(hi, ap, qty))

            if hi in bids and lo in asks:
                bp, bv = bids[hi]
                ap, av = asks[lo]
                if bp > ap:
                    qty = min(bv, av, _VEV_PAIRWISE_ARB_LOT,
                              _arb_cap(result, hi, "sell", state.position.get(hi, 0)),
                              _arb_cap(result, lo, "buy", state.position.get(lo, 0)))
                    if qty > 0:
                        result.setdefault(hi, []).append(Order(hi, bp, -qty))
                        result.setdefault(lo, []).append(Order(lo, ap, qty))


def _arb_cap(result: Dict[str, List[Order]], sym: str, side: str, position: int) -> int:
    used = sum(
        (o.quantity if side == "buy" and o.quantity > 0 else
         -o.quantity if side == "sell" and o.quantity < 0 else 0)
        for o in result.get(sym, [])
    )
    if side == "buy":
        return max(0, _VEV_LIMIT - position - used)
    return max(0, _VEV_LIMIT + position - used)