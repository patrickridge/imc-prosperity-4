import json
from typing import Dict, List, Tuple

from backtester.datamodel import Order, OrderDepth, TradingState


# ---------------------------------------------------------------------------
# Round 5 v4 — universal OBI-MM with per-product Avellaneda-Stoikov edges.
#
# Teammate's strategy used a flat EDGE=2 across all products, leaving SNACKPACK
# (wide-spread / low-vol) and bleeders (tight-spread / low-vol with adverse
# selection) under-edged. v4 replaces the flat EDGE with per-product values
# derived from σ × √holding + adverse-selection term, bounded by spread/2 - 1.
#
# Calibrated from R5 days 2-3 historical: σ_per_tick × √100 × 0.5 + ln(1+γ/k)/γ.
# ---------------------------------------------------------------------------

POSITION_LIMIT = 10
QUOTE_SIZE = 5
OBI_SKEW = 1.2
INVENTORY_PENALTY = 0.6


_EDGE_BY_PRODUCT: Dict[str, int] = {
    "GALAXY_SOUNDS_BLACK_HOLES": 6, "GALAXY_SOUNDS_DARK_MATTER": 6,
    "GALAXY_SOUNDS_PLANETARY_RINGS": 6, "GALAXY_SOUNDS_SOLAR_FLAMES": 6,
    "GALAXY_SOUNDS_SOLAR_WINDS": 6,
    "MICROCHIP_CIRCLE": 3, "MICROCHIP_OVAL": 3, "MICROCHIP_RECTANGLE": 3,
    "MICROCHIP_SQUARE": 4, "MICROCHIP_TRIANGLE": 4,
    "OXYGEN_SHAKE_CHOCOLATE": 5, "OXYGEN_SHAKE_EVENING_BREATH": 5,
    "OXYGEN_SHAKE_GARLIC": 6, "OXYGEN_SHAKE_MINT": 6,
    "OXYGEN_SHAKE_MORNING_BREATH": 6,
    "PANEL_1X2": 4, "PANEL_1X4": 4, "PANEL_2X2": 4, "PANEL_2X4": 4, "PANEL_4X4": 4,
    "PEBBLES_L": 6, "PEBBLES_M": 6, "PEBBLES_S": 5,
    "PEBBLES_XL": 8, "PEBBLES_XS": 4,
    "ROBOT_DISHES": 2, "ROBOT_IRONING": 2, "ROBOT_LAUNDRY": 3,
    "ROBOT_MOPPING": 3, "ROBOT_VACUUMING": 2,
    "SLEEP_POD_COTTON": 4, "SLEEP_POD_LAMB_WOOL": 4, "SLEEP_POD_NYLON": 3,
    "SLEEP_POD_POLYESTER": 4, "SLEEP_POD_SUEDE": 4,
    "SNACKPACK_CHOCOLATE": 8, "SNACKPACK_PISTACHIO": 7, "SNACKPACK_RASPBERRY": 8,
    "SNACKPACK_STRAWBERRY": 8, "SNACKPACK_VANILLA": 8,
    "TRANSLATOR_ASTRO_BLACK": 4, "TRANSLATOR_ECLIPSE_CHARCOAL": 4,
    "TRANSLATOR_GRAPHITE_MIST": 4, "TRANSLATOR_SPACE_GRAY": 4,
    "TRANSLATOR_VOID_BLUE": 4,
    "UV_VISOR_AMBER": 4, "UV_VISOR_MAGENTA": 6, "UV_VISOR_ORANGE": 6,
    "UV_VISOR_RED": 6, "UV_VISOR_YELLOW": 6,
}


class Trader:
    def run(
        self, state: TradingState
    ) -> Tuple[Dict[str, List[Order]], int, str]:
        result: Dict[str, List[Order]] = {}
        for product in _EDGE_BY_PRODUCT:
            depth = state.order_depths.get(product)
            if depth is None:
                continue
            orders = _quote_product(product, depth, state.position.get(product, 0))
            if orders:
                result[product] = orders
        return result, 0, state.traderData or ""


def _quote_product(product: str, depth: OrderDepth, position: int) -> List[Order]:
    if not depth.buy_orders or not depth.sell_orders:
        return []
    bid = max(depth.buy_orders)
    ask = min(depth.sell_orders)
    obi = _order_book_imbalance(depth, bid, ask)
    fair = _fair_value(bid, ask, obi, position)
    edge = _EDGE_BY_PRODUCT[product]
    return _post_quotes(product, fair, edge, position)


def _order_book_imbalance(depth: OrderDepth, bid: int, ask: int) -> float:
    bid_volume = depth.buy_orders[bid]
    ask_volume = abs(depth.sell_orders[ask])
    total = bid_volume + ask_volume
    if total == 0:
        return 0.0
    return (bid_volume - ask_volume) / total


def _fair_value(bid: int, ask: int, obi: float, position: int) -> float:
    mid = (bid + ask) / 2.0
    spread = ask - bid
    skew = OBI_SKEW * obi * (spread / 2.0)
    return mid + skew - INVENTORY_PENALTY * position


def _post_quotes(product: str, fair: float, edge: int, position: int) -> List[Order]:
    buy_size = min(QUOTE_SIZE, POSITION_LIMIT - position)
    sell_size = min(QUOTE_SIZE, POSITION_LIMIT + position)
    orders: List[Order] = []
    if buy_size > 0:
        orders.append(Order(product, int(fair - edge), buy_size))
    if sell_size > 0:
        orders.append(Order(product, int(fair + edge), -sell_size))
    return orders
