from backtester.datamodel import Order, OrderDepth, TradingState
from strategies.logger import Logger

logger = Logger()

FAIR_VALUE_EMERALDS = 10_000
POSITION_LIMIT = 80
TAKE_EDGE = 1.0
QUOTE_OFFSET = 4
INV_SKEW = 0.08


def best_bid_ask(order_depth: OrderDepth):
    best_bid = max(order_depth.buy_orders.keys()) if order_depth.buy_orders else None
    best_ask = min(order_depth.sell_orders.keys()) if order_depth.sell_orders else None
    return best_bid, best_ask


def wall_mid(order_depth: OrderDepth):
    bids = sorted(order_depth.buy_orders.keys())
    asks = sorted(order_depth.sell_orders.keys())
    if len(bids) >= 2 and len(asks) >= 2:
        return (bids[0] + asks[-1]) / 2
    if bids and asks:
        return (bids[-1] + asks[0]) / 2
    return None


def take_orders(product, order_depth, fair_value, position):
    orders = []

    for ask_price in sorted(order_depth.sell_orders.keys()):
        if ask_price > fair_value - TAKE_EDGE:
            break
        ask_vol = abs(order_depth.sell_orders[ask_price])
        buy_qty = min(ask_vol, POSITION_LIMIT - position)
        if buy_qty > 0:
            orders.append(Order(product, ask_price, buy_qty))
            position += buy_qty

    for bid_price in sorted(order_depth.buy_orders.keys(), reverse=True):
        if bid_price < fair_value + TAKE_EDGE:
            break
        bid_vol = order_depth.buy_orders[bid_price]
        sell_qty = min(bid_vol, POSITION_LIMIT + position)
        if sell_qty > 0:
            orders.append(Order(product, bid_price, -sell_qty))
            position -= sell_qty

    return orders, position


def make_orders(product, order_depth, fair_value, position):
    orders = []
    best_bid, best_ask = best_bid_ask(order_depth)
    if best_bid is None or best_ask is None:
        return orders

    buy_price = min(int(fair_value) - QUOTE_OFFSET, best_bid + 1)
    sell_price = max(int(fair_value) + QUOTE_OFFSET, best_ask - 1)

    buy_qty = POSITION_LIMIT - position
    sell_qty = POSITION_LIMIT + position

    if buy_qty > 0:
        orders.append(Order(product, buy_price, buy_qty))
    if sell_qty > 0:
        orders.append(Order(product, sell_price, -sell_qty))

    return orders


class Trader:
    def run(self, state: TradingState):
        orders = {}

        for product, order_depth in state.order_depths.items():
            position = state.position.get(product, 0)

            if product == "EMERALDS":
                fv = FAIR_VALUE_EMERALDS
            else:
                fv = wall_mid(order_depth)
                if fv is None:
                    orders[product] = []
                    continue

            adj_fv = fv + (-position * INV_SKEW)

            taken, position = take_orders(product, order_depth, adj_fv, position)
            made = make_orders(product, order_depth, adj_fv, position)
            orders[product] = taken + made

            logger.print(f"{product}: fv={fv:.1f} adj={adj_fv:.1f} pos={position}")

        conversions = 0
        trader_data = state.traderData or ""
        logger.flush(state, orders, conversions, trader_data)
        return orders, conversions, trader_data
