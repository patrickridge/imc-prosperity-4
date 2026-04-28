import json

from backtester.datamodel import Order, TradingState
from strategies.logger import Logger

logger = Logger()

PRODUCT = "ROBOT_DISHES"
POSITION_LIMIT = 10
WINDOW = 15
QUOTE_SIZE = 5
EDGE = 3
MIN_HISTORY = 5


def best_bid_ask(order_depth):
    bid = max(order_depth.buy_orders) if order_depth.buy_orders else None
    ask = min(order_depth.sell_orders) if order_depth.sell_orders else None
    return bid, ask


def load_state(raw):
    if not raw:
        return {"history": []}
    try:
        loaded = json.loads(raw)
    except json.JSONDecodeError:
        return {"history": []}
    if not isinstance(loaded, dict):
        return {"history": []}
    return loaded


def update_history(history, mid):
    history = list(history)
    history.append(mid)
    if len(history) > WINDOW:
        history = history[-WINDOW:]
    return history


def moving_average(history):
    if len(history) < MIN_HISTORY:
        return None
    return sum(history) / len(history)


def quote_orders(fair, position):
    buy_size = min(QUOTE_SIZE, POSITION_LIMIT - position)
    sell_size = min(QUOTE_SIZE, POSITION_LIMIT + position)

    orders = []
    if buy_size > 0:
        orders.append(Order(PRODUCT, int(fair) - EDGE, buy_size))
    if sell_size > 0:
        orders.append(Order(PRODUCT, int(fair) + EDGE, -sell_size))
    return orders


class Trader:
    def run(self, state: TradingState):
        orders = {}
        td = load_state(state.traderData)

        depth = state.order_depths.get(PRODUCT)
        if depth is not None:
            bid, ask = best_bid_ask(depth)
            if bid is not None and ask is not None:
                mid = (bid + ask) / 2
                td["history"] = update_history(td.get("history", []), mid)
                fair = moving_average(td["history"])

                if fair is not None:
                    position = state.position.get(PRODUCT, 0)
                    orders[PRODUCT] = quote_orders(fair, position)

        conversions = 0
        trader_data = json.dumps(td)
        logger.flush(state, orders, conversions, trader_data)
        return orders, conversions, trader_data
