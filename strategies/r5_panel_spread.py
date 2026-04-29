"""PANEL_1X4 vs PANEL_2X2 spread mean-reversion strategy.

H3 found these are the only PANEL pair with a sustained mean-reverting spread
(both have area = 4 sq units). Spread mean drifts day-to-day, so we use a
rolling z-score instead of absolute thresholds.

State is persisted in traderData as JSON: rolling history of the spread.
"""
import json

from backtester.datamodel import Order, TradingState
from strategies.logger import Logger

logger = Logger()

PRODUCT_LONG_LEG = "PANEL_1X4"
PRODUCT_SHORT_LEG = "PANEL_2X2"
POSITION_LIMIT = 10
WINDOW = 200
MIN_HISTORY = 30
QUOTE_SIZE = 5


def best_bid_ask(order_depth):
    bid = max(order_depth.buy_orders) if order_depth.buy_orders else None
    ask = min(order_depth.sell_orders) if order_depth.sell_orders else None
    return bid, ask


def load_state(raw):
    if not raw:
        return {"history": []}
    try:
        loaded = json.loads(raw)
    except json.JSONDecodeError:
        return {"history": []}
    return loaded if isinstance(loaded, dict) else {"history": []}


def update_history(history, value):
    history = list(history)
    history.append(value)
    if len(history) > WINDOW:
        history = history[-WINDOW:]
    return history


def rolling_mean_std(history):
    if len(history) < MIN_HISTORY:
        return None, None
    n = len(history)
    mean = sum(history) / n
    var = sum((x - mean) ** 2 for x in history) / n
    std = var ** 0.5
    return mean, std


def z_score(value, mean, std):
    if std is None or std == 0:
        return None
    return (value - mean) / std


# TODO (Patrick): implement the trading decision below.
#
# You have:
#   z         — current z-score of the spread (+ve = wider than typical, -ve = tighter)
#   long_leg_pos  — current position in PANEL_1X4
#   short_leg_pos — current position in PANEL_2X2
#
# Return a target signed position for each leg (-POSITION_LIMIT..+POSITION_LIMIT).
# Spread = PANEL_1X4 - PANEL_2X2, so to "short the spread" you sell 1X4 and buy 2X2.
#
# Decisions to make:
#   1. ENTRY THRESHOLD: at what |z| do you open a position? Tighter (e.g. 1.0)
#      means more trades / more noise; wider (e.g. 2.0) means cleaner signal but
#      fewer fills.
#   2. EXIT THRESHOLD: at what |z| do you close? Mean-reversion strategies
#      typically exit at |z| ~ 0 to 0.5, but holding through zero captures
#      slightly more.
#   3. SIZING: full size at entry, or scale in as z grows? Scaling reduces
#      entry timing risk but lowers PnL when the signal is sharp.
#
# Expected ~5–10 lines.
def decide_target_positions(z, long_leg_pos, short_leg_pos):
    target_long_leg = 0
    target_short_leg = 0
    return target_long_leg, target_short_leg


def orders_to_reach_target(product, current_pos, target_pos, bid, ask):
    delta = target_pos - current_pos
    if delta == 0:
        return []
    if delta > 0:
        return [Order(product, ask, min(delta, QUOTE_SIZE))]
    return [Order(product, bid, max(delta, -QUOTE_SIZE))]


class Trader:
    def run(self, state: TradingState):
        orders = {}
        td = load_state(state.traderData)

        long_depth = state.order_depths.get(PRODUCT_LONG_LEG)
        short_depth = state.order_depths.get(PRODUCT_SHORT_LEG)
        if long_depth and short_depth:
            long_bid, long_ask = best_bid_ask(long_depth)
            short_bid, short_ask = best_bid_ask(short_depth)

            if all(p is not None for p in (long_bid, long_ask, short_bid, short_ask)):
                long_mid = (long_bid + long_ask) / 2
                short_mid = (short_bid + short_ask) / 2
                spread = long_mid - short_mid

                td["history"] = update_history(td.get("history", []), spread)
                mean, std = rolling_mean_std(td["history"])
                z = z_score(spread, mean, std) if mean is not None else None

                if z is not None:
                    long_pos = state.position.get(PRODUCT_LONG_LEG, 0)
                    short_pos = state.position.get(PRODUCT_SHORT_LEG, 0)
                    target_long, target_short = decide_target_positions(
                        z, long_pos, short_pos
                    )
                    long_orders = orders_to_reach_target(
                        PRODUCT_LONG_LEG, long_pos, target_long, long_bid, long_ask
                    )
                    short_orders = orders_to_reach_target(
                        PRODUCT_SHORT_LEG, short_pos, target_short, short_bid, short_ask
                    )
                    if long_orders:
                        orders[PRODUCT_LONG_LEG] = long_orders
                    if short_orders:
                        orders[PRODUCT_SHORT_LEG] = short_orders

        conversions = 0
        trader_data = json.dumps(td)
        logger.flush(state, orders, conversions, trader_data)
        return orders, conversions, trader_data
