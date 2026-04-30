"""
Hydrogel-only extraction from r4_v6_directional.py.

Signal: EMA rolling mean (alpha=0.05). If current mid > EMA → max SHORT (-200).
If current mid < EMA → max LONG (+200). Both signals (EMA + seed 9991) must
agree on direction; if they conflict, the seed-anchored target wins.

Reaches target via: (1) passive quotes skewed hard toward target,
(2) taking only when ask/bid is 20+ ticks through fair.
"""
import json
from dataclasses import dataclass
from math import ceil, floor
from typing import Dict, List, Tuple

from backtester.datamodel import Order, OrderDepth, TradingState


HYDROGEL_PACK = "HYDROGEL_PACK"

HYDROGEL_FAIR_SEED = 9_991.0
HYDROGEL_LIMIT = 200
HYDROGEL_POST_EDGE = 2
HYDROGEL_TAKE_EDGE = 20
HYDROGEL_TARGET_SCALE = 12
HYDROGEL_MAX_TAKE_SIZE = 40

_HP_EMA_ALPHA = 0.05
_FAIR_SEED_WEIGHT = 1.0
HYDROGEL_FAIR_ALPHA = 0.002


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
    ) -> Tuple[Dict[str, List[Order]], int, str]:
        data = _load_data(state.traderData)
        result: Dict[str, List[Order]] = {}

        if HYDROGEL_PACK in state.order_depths:
            od = state.order_depths[HYDROGEL_PACK]
            hydrogel_mid = _wall_mid(od)
            hydrogel_fair, hp_ema = _detect_fair_and_ema(
                data, hydrogel_mid,
            )
            orders = _trade_hydrogel(
                od,
                state.position.get(HYDROGEL_PACK, 0),
                hydrogel_fair,
                hp_ema,
            )
            if orders:
                result[HYDROGEL_PACK] = orders

        return result, 0, json.dumps(data, separators=(",", ":"))


def _load_data(raw: str) -> dict:
    if not raw:
        return {}
    try:
        loaded = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _detect_fair_and_ema(data: dict, mid: float | None) -> Tuple[float, float]:
    seed = HYDROGEL_FAIR_SEED

    if mid is None:
        return data.get("fair", seed), data.get("ema", seed)

    n = data.get("n", 0) + 1
    prev_mean = data.get("mean", mid)
    cum_mean = prev_mean + (mid - prev_mean) / n
    data["n"] = n
    data["mean"] = cum_mean
    fair = _FAIR_SEED_WEIGHT * seed + (1.0 - _FAIR_SEED_WEIGHT) * cum_mean
    data["fair"] = fair

    prev_ema = data.get("ema", mid)
    ema = (1.0 - _HP_EMA_ALPHA) * prev_ema + _HP_EMA_ALPHA * mid
    data["ema"] = ema

    return fair, ema


def _rolling_mean_target(current_mid: float | None, ema: float, limit: int) -> int:
    if current_mid is None:
        return 0
    return -limit if current_mid > ema else limit


def _trade_hydrogel(
    od: OrderDepth, position: int, fair_value: float, hp_ema: float,
) -> List[Order]:
    current_mid = _wall_mid(od)

    seed_target = 0
    if current_mid is not None:
        raw = round((fair_value - current_mid) / HYDROGEL_TARGET_SCALE * HYDROGEL_CONFIG.limit)
        seed_target = max(-HYDROGEL_CONFIG.limit, min(HYDROGEL_CONFIG.limit, raw))

    ema_target = _rolling_mean_target(current_mid, hp_ema, HYDROGEL_LIMIT)

    if seed_target * ema_target >= 0:
        target_position = ema_target
    else:
        target_position = seed_target

    return _trade_dynamic_product(
        HYDROGEL_CONFIG, od, position, fair_value,
        max_take_size=HYDROGEL_MAX_TAKE_SIZE,
        take_edge=HYDROGEL_TAKE_EDGE,
        target_position=target_position,
    )


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
    _post_quotes_skewed(
        config, od, orders, projected,
        buy_taken, sell_taken, buy_cap, sell_cap, fair_value, target_position,
    )
    return orders


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
        available = min(-od.sell_orders[ask_price], max_take_size or 9999)
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
        available = min(od.buy_orders[bid_price], max_take_size or 9999)
        qty = min(available, sell_cap - sell_taken, projected - target_floor)
        if qty > 0:
            orders.append(Order(config.symbol, bid_price, -qty))
            projected -= qty
            sell_taken += qty
    return sell_taken, projected


def _clear_at_fair_value(
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