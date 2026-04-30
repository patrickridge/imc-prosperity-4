"""
Round 3 Voucher Strategy: Market Making on Wide Spreads.

Key insights:
1. Butterfly arbs visible in order book but illiquid (Magritte: not just standard calls).
2. Main profit source: bid-ask spread scalping on products with wide spreads.
3. VEV_4000 (wide 20-tick spreads) is the profit engine.
4. Inventory management: cap position, unwind when full.

Strategy:
- Quote inside bid-ask on wide-spread products
- Accumulate inventory on profitable legs
- Unwind when position limit reached
- No directional bets, pure market making
"""

from backtester.datamodel import Order, OrderDepth, TradingState
from strategies.logger import Logger

logger = Logger()

class VoucherMM:
    def __init__(self):
        self.max_position_per_leg = 30
        self.min_spread_to_trade = 2
        self.inventory_target = 0

    def quote_inside_spread(self, voucher: str, ob: OrderDepth, current_position: int) -> list:
        """Place bid and ask quotes inside the market spread."""
        if not ob.buy_orders or not ob.sell_orders:
            return []

        best_bid = max(ob.buy_orders.keys())
        best_ask = min(ob.sell_orders.keys())
        spread = best_ask - best_bid

        if spread < self.min_spread_to_trade:
            return []

        orders = []
        mid = (best_bid + best_ask) / 2

        # BID SIDE: place above market bid to get filled
        if current_position < self.max_position_per_leg:
            bid_price = int(best_bid + 1)
            if bid_price < mid:
                bid_qty = min(5, self.max_position_per_leg - current_position)
                orders.append(Order(voucher, bid_price, bid_qty))

        # ASK SIDE: place below market ask to get filled
        if current_position > -self.max_position_per_leg:
            ask_price = int(best_ask - 1)
            if ask_price > mid:
                ask_qty = min(5, self.max_position_per_leg + current_position)
                orders.append(Order(voucher, ask_price, -ask_qty))

        return orders

    def unwind_excess_position(self, voucher: str, ob: OrderDepth, current_position: int) -> list:
        """Forcefully close position if at max."""
        if not ob.buy_orders or not ob.sell_orders:
            return []

        best_bid = max(ob.buy_orders.keys())
        best_ask = min(ob.sell_orders.keys())

        orders = []

        # Close long position
        if current_position > self.max_position_per_leg:
            orders.append(Order(voucher, best_bid, -current_position))

        # Close short position
        elif current_position < -self.max_position_per_leg:
            orders.append(Order(voucher, best_ask, -current_position))

        return orders

    def trade_voucher(self, voucher: str, state: TradingState) -> list:
        """Main decision for one voucher."""
        if voucher not in state.order_depths:
            return []

        ob = state.order_depths[voucher]
        current_position = state.position.get(voucher, 0)

        # Unwind if over limit
        if abs(current_position) > self.max_position_per_leg:
            return self.unwind_excess_position(voucher, ob, current_position)

        # Otherwise, quote inside spread
        return self.quote_inside_spread(voucher, ob, current_position)

class Trader:
    def __init__(self):
        self.mm = VoucherMM()
        self.target_vouchers = [
            'VEV_4000', 'VEV_4500', 'VEV_5000', 'VEV_5100',
            'VEV_5200', 'VEV_5300', 'VEV_5400', 'VEV_5500'
        ]

    def run(self, state: TradingState):
        orders = {}

        for voucher in self.target_vouchers:
            voucher_orders = self.mm.trade_voucher(voucher, state)
            if voucher_orders:
                orders[voucher] = voucher_orders

        conversions = 0
        trader_data = state.traderData or ""
        logger.flush(state, orders, conversions, trader_data)
        return orders, conversions, trader_data
