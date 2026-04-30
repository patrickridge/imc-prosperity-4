

PRODUCTS = [
    "SNACKPACK_CHOCOLATE",
    "SNACKPACK_VANILLA",
    "SNACKPACK_PISTACHIO",
    "SNACKPACK_STRAWBERRY",
    ]
POSITION_LIMIT = 10
QUOTE_SIZE = 5
OBI_SKEW = 1.2
INVENTORY_PENALTY = 0.8
EDGE = 8


def best_bid_ask(order_depth):
    bid = max(order_depth.buy_orders) if order_depth.buy_orders else None
    ask = min(order_depth.sell_orders) if order_depth.sell_orders else None
    return bid, ask


def order_book_imbalance(order_depth, bid, ask):
    bid_volume = order_depth.buy_orders[bid]
    ask_volume = abs(order_depth.sell_orders[ask])
    total = bid_volume + ask_volume
    if total == 0:
        return 0.0
    return (bid_volume - ask_volume) / total


def fair_value(bid, ask, obi, position):
    mid = (bid + ask) / 2
    spread = ask - bid
    skew = OBI_SKEW * obi * (spread / 2)
    inventory_adjust = -INVENTORY_PENALTY * position
    return mid + skew + inventory_adjust


def quote_orders(product, fair, position):
    buy_size = min(QUOTE_SIZE, POSITION_LIMIT - position)
    sell_size = min(QUOTE_SIZE, POSITION_LIMIT + position)

    orders = []
    if buy_size > 0:
        orders.append(Order(product, int(fair - EDGE), buy_size))
    if sell_size > 0:
        orders.append(Order(product, int(fair + EDGE), -sell_size))
    return orders


class Trader:
    def run(self, state: TradingState):
        orders = {}

        for product in PRODUCTS:
            order_depth = state.order_depths.get(product)
            if order_depth is None:
                continue

            bid, ask = best_bid_ask(order_depth)
            if bid is None or ask is None:
                continue

            position = state.position.get(product, 0)
            obi = order_book_imbalance(order_depth, bid, ask)
            fair = fair_value(bid, ask, obi, position)
            orders[product] = quote_orders(product, fair, position)

        conversions = 0
        trader_data = state.traderData or ""
        logger.flush(state, orders, conversions, trader_data)
        return orders, conversions, trader_data