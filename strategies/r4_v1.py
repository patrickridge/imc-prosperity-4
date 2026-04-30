from backtester.datamodel import Order, OrderDepth, TradingState
from strategies.logger import Logger
import json

logger = Logger()


HYDROGEL = "HYDROGEL_PACK"
VELVETFRUIT = "VELVETFRUIT_EXTRACT"
VOUCHERS = [f"VEV_{k}" for k in (4000, 4500, 5000, 5100, 5200, 5300, 5400, 5500, 6000, 6500)]

POSITION_LIMITS = {
    HYDROGEL: 200,
    VELVETFRUIT: 200,
    **{v: 300 for v in VOUCHERS},
}

ROLLING_WINDOW = 200
DEVIATION_THRESHOLD = 1.5
MAX_TARGET_FRAC = 0.9


def best_bid_ask(depth: OrderDepth):
    best_ask = min(depth.sell_orders.keys()) if depth.sell_orders else None
    best_bid = max(depth.buy_orders.keys()) if depth.buy_orders else None
    return best_bid, best_ask


def mean_and_std(values):
    n = len(values)
    if n == 0:
        return None, None
    mean = sum(values) / n
    variance = sum((v - mean) ** 2 for v in values) / n
    return mean, variance ** 0.5


def signal_strength(current_mid, rolling_mean, rolling_std):
    if rolling_std is None or rolling_std == 0:
        return 0.0
    return (rolling_mean - current_mid) / rolling_std


def target_position(symbol, signal):
    limit = POSITION_LIMITS[symbol]
    if signal >= DEVIATION_THRESHOLD:
        return int(limit * MAX_TARGET_FRAC)
    if signal <= -DEVIATION_THRESHOLD:
        return -int(limit * MAX_TARGET_FRAC)
    return 0


def take_to_target(symbol, depth, current, target):
    orders = []
    diff = target - current
    if diff > 0 and depth.sell_orders:
        for price in sorted(depth.sell_orders.keys()):
            qty = min(diff, -depth.sell_orders[price])
            if qty > 0:
                orders.append(Order(symbol, price, qty))
                diff -= qty
            if diff <= 0:
                break
    elif diff < 0 and depth.buy_orders:
        for price in sorted(depth.buy_orders.keys(), reverse=True):
            qty = min(-diff, depth.buy_orders[price])
            if qty > 0:
                orders.append(Order(symbol, price, -qty))
                diff += qty
            if diff >= 0:
                break
    return orders


def market_make_around(symbol, depth, position, fair_value, edge=1):
    best_bid, best_ask = best_bid_ask(depth)
    if best_bid is None or best_ask is None:
        return []
    limit = POSITION_LIMITS[symbol]
    orders = []

    bid_price = min(best_bid + 1, int(fair_value - edge))
    ask_price = max(best_ask - 1, int(fair_value + edge))

    buy_qty = limit - position
    sell_qty = limit + position

    if buy_qty > 0 and bid_price < fair_value:
        orders.append(Order(symbol, bid_price, buy_qty))
    if sell_qty > 0 and ask_price > fair_value:
        orders.append(Order(symbol, ask_price, -sell_qty))

    return orders


def parse_state(trader_data):
    if not trader_data:
        return {"mids": {}}
    try:
        return json.loads(trader_data)
    except Exception:
        return {"mids": {}}


def update_history(history, mid):
    history.append(mid)
    if len(history) > ROLLING_WINDOW * 2:
        history[:] = history[-ROLLING_WINDOW:]
    return history


def trade_symbol(symbol, state, memory):
    depth = state.order_depths.get(symbol)
    if depth is None:
        return []

    best_bid, best_ask = best_bid_ask(depth)
    if best_bid is None or best_ask is None:
        return []

    mid = (best_bid + best_ask) / 2
    history = memory["mids"].setdefault(symbol, [])
    update_history(history, mid)

    if len(history) < ROLLING_WINDOW:
        return []

    rolling_mean, rolling_std = mean_and_std(history[-ROLLING_WINDOW:])
    signal = signal_strength(mid, rolling_mean, rolling_std)
    position = (state.position or {}).get(symbol, 0)
    target = target_position(symbol, signal)

    take_orders = take_to_target(symbol, depth, position, target)
    mm_orders = market_make_around(symbol, depth, position, rolling_mean)

    return take_orders + mm_orders


class Trader:
    def run(self, state: TradingState):
        memory = parse_state(state.traderData)
        orders = {}

        for symbol in [HYDROGEL, VELVETFRUIT] + VOUCHERS:
            symbol_orders = trade_symbol(symbol, state, memory)
            if symbol_orders:
                orders[symbol] = symbol_orders

        new_data = json.dumps(memory)
        logger.flush(state, orders, 0, new_data)
        return orders, 0, new_data
