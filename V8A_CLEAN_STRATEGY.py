"""
V8A Strategy - CLEAN CODE (No Logger, No Combining)
Snackpack + Galaxy/Oxygen Trading
"""

from datamodel import Order, TradingState, OrderDepth

# ============================================================================
# SNACKPACK MODULE - Per-Product Spread Optimization
# ============================================================================

SNACKPACK_PRODUCTS = [
    "SNACKPACK_CHOCOLATE",
    "SNACKPACK_VANILLA",
    "SNACKPACK_PISTACHIO",
    "SNACKPACK_STRAWBERRY",
]

SNACKPACK_LIMITS = {
    "SNACKPACK_CHOCOLATE": 10,
    "SNACKPACK_VANILLA": 10,
    "SNACKPACK_PISTACHIO": 10,
    "SNACKPACK_STRAWBERRY": 10,
}

# Per-product edges: high-volume (8), low-volume (2)
SNACKPACK_EDGES = {
    'SNACKPACK_VANILLA': 8,           # Liquid - wider spread
    'SNACKPACK_STRAWBERRY': 8,        # Liquid - wider spread
    'SNACKPACK_CHOCOLATE': 2,         # Tight spread - scalping
    'SNACKPACK_PISTACHIO': 2,         # Tight spread - scalping
}

SNACKPACK_CONFIG = {
    'POSITION_LIMIT': 10,
    'QUOTE_SIZE': 5,
    'OBI_SKEW': 1.2,
    'INVENTORY_PENALTY': 0.8,
}


def snackpack_edge_for(product):
    """Get spread edge for product."""
    return SNACKPACK_EDGES.get(product, 4)


def snackpack_best_bid_ask(order_depth):
    """Extract best bid and ask from order depth."""
    bid = max(order_depth.buy_orders) if order_depth.buy_orders else None
    ask = min(order_depth.sell_orders) if order_depth.sell_orders else None
    return bid, ask


def snackpack_order_book_imbalance(order_depth, bid, ask):
    """Calculate order book imbalance (buy vs sell volume)."""
    bid_volume = order_depth.buy_orders[bid]
    ask_volume = abs(order_depth.sell_orders[ask])
    total = bid_volume + ask_volume
    if total == 0:
        return 0.0
    return (bid_volume - ask_volume) / total


def snackpack_fair_value(bid, ask, obi, position):
    """
    Calculate fair value with:
    - Order book imbalance skew
    - Inventory penalty
    """
    mid = (bid + ask) / 2
    spread = ask - bid
    skew = SNACKPACK_CONFIG['OBI_SKEW'] * obi * (spread / 2)
    inventory_adjust = -SNACKPACK_CONFIG['INVENTORY_PENALTY'] * position
    return mid + skew + inventory_adjust


def snackpack_quote_orders(product, fair, position):
    """Generate buy/sell orders around fair value."""
    limit = SNACKPACK_CONFIG['POSITION_LIMIT']
    quote_size = SNACKPACK_CONFIG['QUOTE_SIZE']
    edge = snackpack_edge_for(product)
    
    buy_size = min(quote_size, limit - position)
    sell_size = min(quote_size, limit + position)

    orders = []
    if buy_size > 0:
        orders.append(Order(product, int(fair - edge), buy_size))
    if sell_size > 0:
        orders.append(Order(product, int(fair + edge), -sell_size))
    return orders


# ============================================================================
# GALAXY/OXYGEN MODULE - Multi-Product Regime Trading
# ============================================================================

GALAXY_PRODUCTS = {
    "BLACK": "GALAXY_SOUNDS_BLACK_HOLES",
    "GARLIC": "OXYGEN_SHAKE_GARLIC",
    "SOLAR_FLAMES": "GALAXY_SOUNDS_SOLAR_FLAMES",
    "DARK_MATTER": "GALAXY_SOUNDS_DARK_MATTER",
}

GALAXY_LIMITS = {
    "GALAXY_SOUNDS_BLACK_HOLES": 10,
    "OXYGEN_SHAKE_GARLIC": 10,
    "GALAXY_SOUNDS_SOLAR_FLAMES": 10,
    "GALAXY_SOUNDS_DARK_MATTER": 10,
}

GALAXY_TARGETS = {
    "GALAXY_SOUNDS_BLACK_HOLES": 10,   # Always-on
    "OXYGEN_SHAKE_GARLIC": 10,         # Always-on
}


def galaxy_cross_to_target(order_depth, position, target, limit, product):
    """
    Cross the spread to reach target position.
    Buy on the ask side, sell on the bid side.
    """
    orders = []
    gap = target - position
    
    if gap == 0:
        return orders
    
    if gap > 0:  # Need to buy
        if not order_depth.sell_orders:
            return orders
        best_ask = min(order_depth.sell_orders.keys())
        ask_avail = abs(int(order_depth.sell_orders[best_ask]))
        qty = min(gap, limit - position, ask_avail, 10)  # Max 10 per order
        if qty > 0:
            orders.append(Order(product, best_ask, qty))
        return orders
    
    # Need to sell
    if not order_depth.buy_orders:
        return orders
    best_bid = max(order_depth.buy_orders.keys())
    bid_avail = int(order_depth.buy_orders[best_bid])
    qty = min(-gap, limit + position, bid_avail, 10)
    if qty > 0:
        orders.append(Order(product, best_bid, -qty))
    return orders


# ============================================================================
# MAIN TRADER CLASS
# ============================================================================

class Trader:
    """V8A: Snackpack (per-product edges) + Galaxy/Oxygen (regime trades)."""
    
    def run(self, state: TradingState):
        orders = {}
        
        # ---- SNACKPACK: Per-product spread trades ----
        for product in SNACKPACK_PRODUCTS:
            order_depth = state.order_depths.get(product)
            if order_depth is None:
                continue
            
            bid, ask = snackpack_best_bid_ask(order_depth)
            if bid is None or ask is None:
                continue
            
            position = state.position.get(product, 0)
            obi = snackpack_order_book_imbalance(order_depth, bid, ask)
            fair = snackpack_fair_value(bid, ask, obi, position)
            orders[product] = snackpack_quote_orders(product, fair, position)
        
        # ---- GALAXY/OXYGEN: Position targeting ----
        for name, product in GALAXY_PRODUCTS.items():
            if product not in GALAXY_TARGETS:
                continue
            
            order_depth = state.order_depths.get(product)
            if order_depth is None:
                continue
            
            position = state.position.get(product, 0)
            target = GALAXY_TARGETS[product]
            limit = GALAXY_LIMITS[product]
            
            cross_orders = galaxy_cross_to_target(
                order_depth, position, target, limit, product
            )
            if cross_orders:
                orders[product] = cross_orders
        
        # No conversions, no trader data
        conversions = 0
        trader_data = ""
        
        return orders, conversions, trader_data


# ============================================================================
# ENTRY POINT
# ============================================================================

def run_trader(state: TradingState):
    """Execute trading logic."""
    trader = Trader()
    return trader.run(state)
