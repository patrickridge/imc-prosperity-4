"""MICROCHIP coverage — OBI-skewed market making on all 5 products.

H5b finding (CIRCLE leads SQUARE/TRIANGLE/OVAL at lags 50-200, corr ~0.05)
is too weak to trade directly — backtested at -80k net. MICROCHIPs have
moderate spreads (mm_score ~50-60) so simple MM works better.
"""
from backtester.datamodel import Order, TradingState
from strategies.logger import Logger

logger = Logger()

PRODUCTS = [
    "MICROCHIP_CIRCLE",
    "MICROCHIP_OVAL",
    "MICROCHIP_SQUARE",
    "MICROCHIP_RECTANGLE",
    "MICROCHIP_TRIANGLE",
]
POSITION_LIMIT = 10
QUOTE_SIZE = 5
OBI_SKEW = 1.0
INVENTORY_PENALTY = 0.5
EDGE = 2


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
            depth = state.order_depths.get(product)
            if depth is None:
                continue
            bid, ask = best_bid_ask(depth)
            if bid is None or ask is None:
                continue

            position = state.position.get(product, 0)
            obi = order_book_imbalance(depth, bid, ask)
            fair = fair_value(bid, ask, obi, position)
            orders[product] = quote_orders(product, fair, position)

        conversions = 0
        trader_data = state.traderData or ""
        logger.flush(state, orders, conversions, trader_data)
        return orders, conversions, trader_data
