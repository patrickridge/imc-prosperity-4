from backtester.datamodel import Order, OrderDepth, TradingState
from strategies.logger import Logger
from math import log, sqrt, exp, pi
import json

logger = Logger()


HYDROGEL = "HYDROGEL_PACK"
VELVETFRUIT = "VELVETFRUIT_EXTRACT"
VOUCHER_STRIKES = {
    "VEV_4000": 4000, "VEV_4500": 4500, "VEV_5000": 5000, "VEV_5100": 5100,
    "VEV_5200": 5200, "VEV_5300": 5300, "VEV_5400": 5400, "VEV_5500": 5500,
    "VEV_6000": 6000, "VEV_6500": 6500,
}

POSITION_LIMITS = {
    HYDROGEL: 200,
    VELVETFRUIT: 200,
    **{v: 300 for v in VOUCHER_STRIKES},
}

DAYS_PER_YEAR = 252
ROUND_TO_DAYS = {1: 7, 2: 6, 3: 5, 4: 4, 5: 3}
CURRENT_ROUND = 4

IV_DEVIATION_THRESHOLD = 0.02
TIMESTAMP_LIMIT = 1_000_000


def norm_cdf(x):
    return 0.5 * (1 + _erf(x / sqrt(2)))


def _erf(x):
    t = 1.0 / (1.0 + 0.3275911 * abs(x))
    poly = ((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t + 0.254829592
    y = 1.0 - poly * t * exp(-x * x)
    return y if x >= 0 else -y


def black_scholes_call(spot, strike, time_to_expiry, vol):
    if time_to_expiry <= 0 or vol <= 0:
        return max(spot - strike, 0)
    sqrt_t = sqrt(time_to_expiry)
    d1 = (log(spot / strike) + 0.5 * vol * vol * time_to_expiry) / (vol * sqrt_t)
    d2 = d1 - vol * sqrt_t
    return spot * norm_cdf(d1) - strike * norm_cdf(d2)


def implied_vol(market_price, spot, strike, time_to_expiry):
    if market_price <= max(spot - strike, 0) + 1e-6:
        return None
    if time_to_expiry <= 0:
        return None

    low, high = 0.01, 5.0
    for _ in range(60):
        mid = (low + high) / 2
        price = black_scholes_call(spot, strike, time_to_expiry, mid)
        if price < market_price:
            low = mid
        else:
            high = mid
        if high - low < 1e-5:
            break
    return (low + high) / 2


def fit_parabolic_smile(moneyness_iv_pairs):
    if len(moneyness_iv_pairs) < 3:
        return None
    n = len(moneyness_iv_pairs)
    sx = sum(m for m, _ in moneyness_iv_pairs)
    sx2 = sum(m * m for m, _ in moneyness_iv_pairs)
    sx3 = sum(m ** 3 for m, _ in moneyness_iv_pairs)
    sx4 = sum(m ** 4 for m, _ in moneyness_iv_pairs)
    sy = sum(iv for _, iv in moneyness_iv_pairs)
    sxy = sum(m * iv for m, iv in moneyness_iv_pairs)
    sx2y = sum(m * m * iv for m, iv in moneyness_iv_pairs)

    a, b, c = _solve_3x3(sx4, sx3, sx2, sx3, sx2, sx, sx2, sx, n, sx2y, sxy, sy)
    if a is None:
        return None
    return lambda m: a * m * m + b * m + c


def _solve_3x3(a11, a12, a13, a21, a22, a23, a31, a32, a33, b1, b2, b3):
    det = (a11 * (a22 * a33 - a23 * a32)
           - a12 * (a21 * a33 - a23 * a31)
           + a13 * (a21 * a32 - a22 * a31))
    if abs(det) < 1e-12:
        return None, None, None
    inv_det = 1.0 / det
    x = inv_det * (b1 * (a22 * a33 - a23 * a32)
                   - a12 * (b2 * a33 - a23 * b3)
                   + a13 * (b2 * a32 - a22 * b3))
    y = inv_det * (a11 * (b2 * a33 - a23 * b3)
                   - b1 * (a21 * a33 - a23 * a31)
                   + a13 * (a21 * b3 - b2 * a31))
    z = inv_det * (a11 * (a22 * b3 - b2 * a32)
                   - a12 * (a21 * b3 - b2 * a31)
                   + b1 * (a21 * a32 - a22 * a31))
    return x, y, z


def best_bid_ask(depth: OrderDepth):
    best_ask = min(depth.sell_orders.keys()) if depth.sell_orders else None
    best_bid = max(depth.buy_orders.keys()) if depth.buy_orders else None
    return best_bid, best_ask


def time_to_expiry_years(state_timestamp):
    days_at_round_start = ROUND_TO_DAYS[CURRENT_ROUND]
    fraction_through_round = state_timestamp / TIMESTAMP_LIMIT
    days_remaining = days_at_round_start - fraction_through_round
    return max(days_remaining / DAYS_PER_YEAR, 1e-6)


def underlying_mid(state):
    depth = state.order_depths.get(VELVETFRUIT)
    if depth is None:
        return None
    bid, ask = best_bid_ask(depth)
    if bid is None or ask is None:
        return None
    return (bid + ask) / 2


def voucher_iv_snapshot(state, spot, ttx):
    pairs = []
    for symbol, strike in VOUCHER_STRIKES.items():
        depth = state.order_depths.get(symbol)
        if depth is None:
            continue
        bid, ask = best_bid_ask(depth)
        if bid is None or ask is None:
            continue
        mid = (bid + ask) / 2
        iv = implied_vol(mid, spot, strike, ttx)
        if iv is None:
            continue
        moneyness = log(strike / spot) / sqrt(ttx)
        pairs.append((symbol, strike, mid, iv, moneyness))
    return pairs


def deviation_orders(symbol, depth, position, theoretical_mid, edge):
    bid, ask = best_bid_ask(depth)
    if bid is None or ask is None:
        return []
    limit = POSITION_LIMITS[symbol]
    orders = []

    if ask < theoretical_mid - edge:
        qty = min(-depth.sell_orders[ask], limit - position)
        if qty > 0:
            orders.append(Order(symbol, ask, qty))

    if bid > theoretical_mid + edge:
        qty = min(depth.buy_orders[bid], limit + position)
        if qty > 0:
            orders.append(Order(symbol, bid, -qty))

    return orders


def compute_voucher_orders(state, spot, ttx):
    orders_by_symbol = {}
    snapshot = voucher_iv_snapshot(state, spot, ttx)
    if len(snapshot) < 4:
        return orders_by_symbol

    smile = fit_parabolic_smile([(m, iv) for _, _, _, iv, m in snapshot])
    if smile is None:
        return orders_by_symbol

    for symbol, strike, mid, iv, moneyness in snapshot:
        fair_iv = smile(moneyness)
        deviation = iv - fair_iv
        if abs(deviation) < IV_DEVIATION_THRESHOLD:
            continue
        theoretical_price = black_scholes_call(spot, strike, ttx, fair_iv)
        position = (state.position or {}).get(symbol, 0)
        depth = state.order_depths[symbol]
        symbol_orders = deviation_orders(symbol, depth, position, theoretical_price, edge=mid * 0.005)
        if symbol_orders:
            orders_by_symbol[symbol] = symbol_orders

    return orders_by_symbol


def hydrogel_orders(state):
    depth = state.order_depths.get(HYDROGEL)
    if depth is None:
        return []
    bid, ask = best_bid_ask(depth)
    if bid is None or ask is None:
        return []
    fair = (bid + ask) / 2
    position = (state.position or {}).get(HYDROGEL, 0)
    limit = POSITION_LIMITS[HYDROGEL]
    orders = []

    buy_qty = limit - position
    sell_qty = limit + position
    if buy_qty > 0:
        orders.append(Order(HYDROGEL, bid + 1, min(buy_qty, 50)))
    if sell_qty > 0:
        orders.append(Order(HYDROGEL, ask - 1, -min(sell_qty, 50)))
    return orders


def velvetfruit_orders(state):
    depth = state.order_depths.get(VELVETFRUIT)
    if depth is None:
        return []
    bid, ask = best_bid_ask(depth)
    if bid is None or ask is None:
        return []
    position = (state.position or {}).get(VELVETFRUIT, 0)
    limit = POSITION_LIMITS[VELVETFRUIT]
    orders = []
    buy_qty = limit - position
    sell_qty = limit + position
    if buy_qty > 0:
        orders.append(Order(VELVETFRUIT, bid + 1, min(buy_qty, 50)))
    if sell_qty > 0:
        orders.append(Order(VELVETFRUIT, ask - 1, -min(sell_qty, 50)))
    return orders


class Trader:
    def run(self, state: TradingState):
        orders = {}

        spot = underlying_mid(state)
        if spot is not None:
            ttx = time_to_expiry_years(state.timestamp)
            voucher_orders = compute_voucher_orders(state, spot, ttx)
            orders.update(voucher_orders)

        hyd_orders = hydrogel_orders(state)
        if hyd_orders:
            orders[HYDROGEL] = hyd_orders

        vfe_orders = velvetfruit_orders(state)
        if vfe_orders:
            orders[VELVETFRUIT] = vfe_orders

        logger.flush(state, orders, 0, "")
        return orders, 0, ""
