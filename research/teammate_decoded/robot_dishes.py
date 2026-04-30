import json



PRODUCT = "ROBOT_DISHES"
POSITION_LIMIT = 10
QUOTE_SIZE = 5
EDGE = 3
LAG1_FADE = 0.22
TREND_THRESHOLD = 8

# Regime switch: only use MA-MM when recent absolute returns are small
# (oscillating regime). Otherwise fall back to lag-1 fade for safety.
REGIME_WINDOW = 30
MR_REGIME_MAX_ABS_RETURN = 4
MA_WINDOW = 10
MIN_HISTORY = 5


def best_bid_ask(order_depth):
    bid = max(order_depth.buy_orders) if order_depth.buy_orders else None
    ask = min(order_depth.sell_orders) if order_depth.sell_orders else None
    return bid, ask


def load_state(raw):
    if not raw:
        return {}
    try:
        loaded = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def update_history(history, mid, max_size):
    history = list(history)
    history.append(mid)
    if len(history) > max_size:
        history = history[-max_size:]
    return history


def is_mr_regime(history):
    if len(history) < REGIME_WINDOW:
        return False
    recent = history[-REGIME_WINDOW:]
    abs_returns = [abs(recent[i] - recent[i - 1]) for i in range(1, len(recent))]
    avg = sum(abs_returns) / len(abs_returns)
    return avg <= MR_REGIME_MAX_ABS_RETURN


def fair_from_ma(history):
    if len(history) < MIN_HISTORY:
        return None
    window = history[-MA_WINDOW:]
    return sum(window) / len(window)


def fair_from_lag1(mid, last_mid):
    last_return = mid - last_mid
    if abs(last_return) > TREND_THRESHOLD:
        return None
    return mid - LAG1_FADE * last_return


def quote_orders(fair, position):
    buy_size = min(QUOTE_SIZE, POSITION_LIMIT - position)
    sell_size = min(QUOTE_SIZE, POSITION_LIMIT + position)

    orders = []
    if buy_size > 0:
        orders.append(Order(PRODUCT, int(fair) - EDGE, buy_size))
    if sell_size > 0:
        orders.append(Order(PRODUCT, int(fair) + EDGE, -sell_size))
    return orders


class Trader:
    def run(self, state: TradingState):
        orders = {}
        td = load_state(state.traderData)

        depth = state.order_depths.get(PRODUCT)
        if depth is not None:
            bid, ask = best_bid_ask(depth)
            if bid is not None and ask is not None:
                mid = (bid + ask) / 2
                history = td.get("history", [])
                history = update_history(history, mid, REGIME_WINDOW)
                td["history"] = history

                fair = None
                if is_mr_regime(history):
                    fair = fair_from_ma(history)
                else:
                    last_mid = td.get("last_mid")
                    if last_mid is not None:
                        fair = fair_from_lag1(mid, last_mid)

                if fair is not None:
                    position = state.position.get(PRODUCT, 0)
                    orders[PRODUCT] = quote_orders(fair, position)
                td["last_mid"] = mid

        conversions = 0
        trader_data = json.dumps(td)
        logger.flush(state, orders, conversions, trader_data)
        return orders, conversions, trader_data