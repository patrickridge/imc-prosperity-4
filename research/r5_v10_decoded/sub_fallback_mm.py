"""Multi-product fallback market-maker for R5.

Quotes a basket of 'unclaimed' R5 products with simple OBI-skewed MM.
Covers UV_VISORs, TRANSLATORs, SLEEP_PODs, the rest of OXYGEN_SHAKEs and
GALAXY_SOUNDs, and 4 ROBOTs (excluding DISHES which has its own strategy).

Skips products that other strategies own:
  - SNACKPACKs (r5_snackpack_mm.py)
  - ROBOT_DISHES (r5_robot_dishes_mr.py)
  - PEBBLES (pebbles.py)
  - PANEL_1X4 / PANEL_2X2 (r5_panel_spread.py)
  - MICROCHIPs (Kaushal researching)
  - GALAXY_SOUNDS_BLACK_HOLES, OXYGEN_SHAKE_GARLIC (Kaushal researching)
"""


PRODUCTS = [
    # UV_VISOR_RED/AMBER/MAGENTA/ORANGE owned by uv_visor.py.
    # YELLOW deliberately not traded there (was unstable historically), kept here.
    "TRANSLATOR_ASTRO_BLACK",
    "TRANSLATOR_ECLIPSE_CHARCOAL", "TRANSLATOR_GRAPHITE_MIST",
    "TRANSLATOR_VOID_BLUE",
    "SLEEP_POD_SUEDE", "SLEEP_POD_POLYESTER",
    "SLEEP_POD_NYLON", "SLEEP_POD_COTTON",
        "ROBOT_VACUUMING", "ROBOT_MOPPING", "ROBOT_LAUNDRY", "ROBOT_IRONING",
    "PANEL_2X4", "PANEL_4X4",
]
POSITION_LIMIT = 10
QUOTE_SIZE = 5
# Tuned via research/round5_fallback_sweep.py — best of 36 combos.
# Backtest +152,959 across 3 days (was +118,531 untuned).
OBI_SKEW = 1.2
INVENTORY_PENALTY = 0.5
EDGE = 3


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