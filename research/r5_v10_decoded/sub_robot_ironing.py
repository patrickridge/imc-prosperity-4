import json

IRONING = "ROBOT_IRONING"
LAUNDRY = "ROBOT_LAUNDRY"
POSITION_LIMIT = 10
QUOTE_SIZE = 5
EDGE = 2
INVENTORY_PENALTY = 0.5
BASKET_WINDOW = 100
MIN_HISTORY = 10


def mid_price(order_depth):
    if not order_depth.buy_orders or not order_depth.sell_orders:
        return None
    return (max(order_depth.buy_orders) + min(order_depth.sell_orders)) / 2


class Trader:
    def run(self, state: TradingState):
        td = {}
        if state.traderData:
            try:
                td = json.loads(state.traderData)
            except json.JSONDecodeError:
                td = {}

        basket_hist = td.get("bh", [])
        orders = {}

        ironing_od = state.order_depths.get(IRONING)
        laundry_od = state.order_depths.get(LAUNDRY)
        ironing_mid = mid_price(ironing_od) if ironing_od else None
        laundry_mid = mid_price(laundry_od) if laundry_od else None

        if ironing_mid is not None and laundry_mid is not None:
            basket_hist.append(ironing_mid + laundry_mid)
            if len(basket_hist) > BASKET_WINDOW:
                basket_hist = basket_hist[-BASKET_WINDOW:]

            if len(basket_hist) >= MIN_HISTORY:
                basket_ma = sum(basket_hist) / len(basket_hist)
                fair = basket_ma - laundry_mid

                position = state.position.get(IRONING, 0)
                fair -= INVENTORY_PENALTY * position

                buy_size = min(QUOTE_SIZE, POSITION_LIMIT - position)
                sell_size = min(QUOTE_SIZE, POSITION_LIMIT + position)

                ironing_orders = []
                if buy_size > 0:
                    ironing_orders.append(Order(IRONING, int(fair - EDGE), buy_size))
                if sell_size > 0:
                    ironing_orders.append(Order(IRONING, int(fair + EDGE), -sell_size))
                if ironing_orders:
                    orders[IRONING] = ironing_orders

        td["bh"] = basket_hist
        return orders, 0, json.dumps(td, separators=(",", ":"))
