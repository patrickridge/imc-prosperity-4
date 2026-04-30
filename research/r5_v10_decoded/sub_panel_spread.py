"""PANEL_1X4 vs PANEL_2X2 spread mean-reversion strategy.

H3 found these are the only PANEL pair with a sustained mean-reverting spread
(both have area = 4 sq units). Spread mean drifts day-to-day, so we use a
rolling z-score instead of absolute thresholds.

State is persisted in traderData as JSON: rolling history of the spread.
"""
import json



PRODUCT_LONG_LEG = "PANEL_1X4"
PRODUCT_SHORT_LEG = "PANEL_2X2"
POSITION_LIMIT = 10
WINDOW = 200
MIN_HISTORY = 30
QUOTE_SIZE = 5
# Drift filter: don't open new positions when the spread has moved
# strongly in one direction recently — that's the day 3 failure mode
# (spread drifts -3500 across the day, every entry catches a falling knife).
DRIFT_LOOKBACK = 100
MAX_DRIFT = 250


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


# --- Tuned via research/round5_panel_sweep.py (36 combos, 3 days). ---
# Best config: ENTRY_Z=2.5, EXIT_Z=0.0, WINDOW=200 -> +7,280 across 3 days
# (was -46,000 with the textbook starter values).
# Day-by-day: +10,425 / -25,003 / +21,858. Day 3 still hurts because that
# day's spread std is 4x the others. Volatility-regime filter as TODO.
ENTRY_Z = 2.5
EXIT_Z = 0.0
POSITION_SIZE = POSITION_LIMIT


def decide_target_positions(z, long_leg_pos, short_leg_pos, recent_drift):
    holding = long_leg_pos != 0 or short_leg_pos != 0
    if holding and abs(z) < EXIT_Z:
        return 0, 0
    drifting = abs(recent_drift) > MAX_DRIFT
    if z > ENTRY_Z and not drifting:
        return -POSITION_SIZE, POSITION_SIZE
    if z < -ENTRY_Z and not drifting:
        return POSITION_SIZE, -POSITION_SIZE
    return long_leg_pos, short_leg_pos


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
                history = td["history"]
                mean, std = rolling_mean_std(history)
                z = z_score(spread, mean, std) if mean is not None else None
                recent_drift = (
                    history[-1] - history[-DRIFT_LOOKBACK]
                    if len(history) >= DRIFT_LOOKBACK else 0
                )

                if z is not None:
                    long_pos = state.position.get(PRODUCT_LONG_LEG, 0)
                    short_pos = state.position.get(PRODUCT_SHORT_LEG, 0)
                    target_long, target_short = decide_target_positions(
                        z, long_pos, short_pos, recent_drift
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