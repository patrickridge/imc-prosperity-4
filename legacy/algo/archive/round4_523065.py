"""
Hydrogel-only strategy extracted from 522219.py for isolated investigation.

Logic: mean-reversion to a fixed fair value (10000). Target position is
proportional to deviation from fair — reach ±200 at 40-tick deviation.
Takes aggressively when ask/bid is 20 ticks through fair. Posts passive
quotes skewed by inventory with post_edge=3 and max_skew=6.

Tune: HYDROGEL_FAIR_VALUE, HYDROGEL_TARGET_SCALE, HYDROGEL_MAX_TAKE_SIZE,
      HYDROGEL_TAKE_EDGE, HYDROGEL_POST_EDGE.
"""
from dataclasses import dataclass
from math import ceil, floor
from typing import Dict, List, Tuple

from backtester.datamodel import Order, OrderDepth, TradingState


HYDROGEL_PACK = "HYDROGEL_PACK"

HYDROGEL_FAIR_VALUE = 10_000.0
HYDROGEL_LIMIT = 200
HYDROGEL_POST_EDGE = 3
HYDROGEL_TAKE_EDGE = 20
# Reach ±200 at FAIR ± (HYDROGEL_TARGET_SCALE) ticks.
# 40 = conservative. Try 25 or 12 for more aggressive sizing.
HYDROGEL_TARGET_SCALE = 40
# Max contracts taken per price level per tick.
# 10 = conservative. Try 20 or 40 for faster convergence to target.
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


class Trader:
    def run(
        self, state: TradingState
    ) -> Tuple[Dict[str, List[Order]], int, str]:
        result: Dict[str, List[Order]] = {}

        if HYDROGEL_PACK in state.order_depths:
            orders = _trade_hydrogel(
                state.order_depths[HYDROGEL_PACK],
                state.position.get(HYDROGEL_PACK, 0),
            )
            if orders:
                result[HYDROGEL_PACK] = orders

        return result, 0, ""


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