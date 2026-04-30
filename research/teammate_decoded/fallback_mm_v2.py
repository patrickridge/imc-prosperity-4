


PRODUCTS = [
    "UV_VISOR_YELLOW",
    "TRANSLATOR_SPACE_GRAY", "TRANSLATOR_ASTRO_BLACK",
    "TRANSLATOR_ECLIPSE_CHARCOAL", "TRANSLATOR_GRAPHITE_MIST",
    "TRANSLATOR_VOID_BLUE",
    "SLEEP_POD_SUEDE", "SLEEP_POD_LAMB_WOOL", "SLEEP_POD_POLYESTER",
    "SLEEP_POD_NYLON", "SLEEP_POD_COTTON",
    "OXYGEN_SHAKE_MORNING_BREATH", "OXYGEN_SHAKE_MINT",
    "ROBOT_VACUUMING", "ROBOT_MOPPING", "ROBOT_LAUNDRY", "ROBOT_IRONING",
    "PANEL_1X2", "PANEL_2X4", "PANEL_4X4",
]

# Per-product POSITION_LIMIT — halve on live bleeders to cap adverse-selection drawdown.
DEFAULT_POSITION_LIMIT = 10
PER_PRODUCT_LIMIT = {
    "UV_VISOR_YELLOW": 5,
    "TRANSLATOR_SPACE_GRAY": 5,
    "SLEEP_POD_LAMB_WOOL": 5,
    "OXYGEN_SHAKE_MORNING_BREATH": 5,
    "OXYGEN_SHAKE_MINT": 5,
    "PANEL_1X2": 5,
}

QUOTE_SIZE = 5

# Per-product EDGE — bleeders get widened quotes (adverse-selection cushion).
DEFAULT_EDGE = 3
PER_PRODUCT_EDGE = {
    "UV_VISOR_YELLOW": 5,
    "TRANSLATOR_SPACE_GRAY": 5,
    "SLEEP_POD_LAMB_WOOL": 5,
    "OXYGEN_SHAKE_MORNING_BREATH": 5,
    "OXYGEN_SHAKE_MINT": 5,
    "PANEL_1X2": 5,
}

OBI_SKEW = 1.2
INVENTORY_PENALTY = 0.5


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
    return mid + skew - INVENTORY_PENALTY * position


def quote_orders(product, fair, position):
    pos_limit = PER_PRODUCT_LIMIT.get(product, DEFAULT_POSITION_LIMIT)
    edge = PER_PRODUCT_EDGE.get(product, DEFAULT_EDGE)

    buy_size = min(QUOTE_SIZE, pos_limit - position)
    sell_size = min(QUOTE_SIZE, pos_limit + position)

    orders = []
    if buy_size > 0:
        orders.append(Order(product, int(fair - edge), buy_size))
    if sell_size > 0:
        orders.append(Order(product, int(fair + edge), -sell_size))
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
