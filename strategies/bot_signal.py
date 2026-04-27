from datamodel import Order, TradingState

VE = "VELVETFRUIT_EXTRACT"
VE_LIMIT = 200
CLIP_SIZE = 20

SMART_BUYERS = {"Mark 67"}
DUMB_BOTS = {"Mark 49", "Mark 22"}


def _signal(market_trades):
    net = 0
    for trade in market_trades.get(VE, []):
        if trade.buyer in SMART_BUYERS:
            net += trade.quantity
        if trade.seller in SMART_BUYERS:
            net -= trade.quantity
        if trade.buyer in DUMB_BOTS:
            net -= trade.quantity
        if trade.seller in DUMB_BOTS:
            net += trade.quantity
    if net > 0:
        return 1
    if net < 0:
        return -1
    return 0


class Trader:
    def run(self, state: TradingState):
        result = {}
        od = state.order_depths.get(VE)
        if od is None:
            return result, 0, ""

        bid = max(od.buy_orders) if od.buy_orders else None
        ask = min(od.sell_orders) if od.sell_orders else None
        if bid is None or ask is None:
            return result, 0, ""

        sig = _signal(state.market_trades)
        position = state.position.get(VE, 0)
        orders = []

        if sig > 0 and position < VE_LIMIT:
            qty = min(CLIP_SIZE, abs(od.sell_orders[ask]), VE_LIMIT - position)
            if qty > 0:
                orders.append(Order(VE, ask, qty))

        elif sig < 0 and position > -VE_LIMIT:
            qty = min(CLIP_SIZE, od.buy_orders[bid], VE_LIMIT + position)
            if qty > 0:
                orders.append(Order(VE, bid, -qty))

        if orders:
            result[VE] = orders
        return result, 0, ""
