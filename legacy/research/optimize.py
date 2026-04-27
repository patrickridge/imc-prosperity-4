"""Parameter sweep for mm strategy. Run: python3 utils/optimize.py"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backtester.data import read_day_data, LIMITS
from backtester.datamodel import Order, OrderDepth, Observation, TradingState, Listing
from backtester.file_reader import PackageResourcesReader
from backtester.models import TradeMatchingMode
from backtester.runner import run_backtest
from itertools import product as iterproduct


POSITION_LIMIT = 80


def wall_mid(order_depth):
    bids = sorted(order_depth.buy_orders.keys())
    asks = sorted(order_depth.sell_orders.keys())
    if len(bids) >= 2 and len(asks) >= 2:
        return (bids[0] + asks[-1]) / 2
    if bids and asks:
        return (bids[-1] + asks[0]) / 2
    return None


def make_trader(take_edge, quote_offset, inventory_skew_factor, emerald_fv):
    """Factory: returns a Trader class with given params."""

    class Trader:
        def run(self, state: TradingState):
            orders = {}
            for prod, od in state.order_depths.items():
                pos = state.position.get(prod, 0)

                if prod == "EMERALDS":
                    fv = emerald_fv
                else:
                    fv = wall_mid(od)
                    if fv is None:
                        orders[prod] = []
                        continue

                # Inventory skew: shift fair value toward flattening position
                skew = -pos * inventory_skew_factor
                adj_fv = fv + skew

                prod_orders = []

                # Take mispriced
                for ask_p in sorted(od.sell_orders.keys()):
                    if ask_p > adj_fv - take_edge:
                        break
                    vol = abs(od.sell_orders[ask_p])
                    qty = min(vol, POSITION_LIMIT - pos)
                    if qty > 0:
                        prod_orders.append(Order(prod, ask_p, qty))
                        pos += qty

                for bid_p in sorted(od.buy_orders.keys(), reverse=True):
                    if bid_p < adj_fv + take_edge:
                        break
                    vol = od.buy_orders[bid_p]
                    qty = min(vol, POSITION_LIMIT + pos)
                    if qty > 0:
                        prod_orders.append(Order(prod, bid_p, -qty))
                        pos -= qty

                # Quote
                best_bid = max(od.buy_orders.keys()) if od.buy_orders else None
                best_ask = min(od.sell_orders.keys()) if od.sell_orders else None
                if best_bid and best_ask:
                    buy_price = min(int(adj_fv) - quote_offset, best_bid + 1)
                    sell_price = max(int(adj_fv) + quote_offset, best_ask - 1)

                    buy_qty = POSITION_LIMIT - pos
                    sell_qty = POSITION_LIMIT + pos

                    if buy_qty > 0:
                        prod_orders.append(Order(prod, buy_price, buy_qty))
                    if sell_qty > 0:
                        prod_orders.append(Order(prod, sell_price, -sell_qty))

                orders[prod] = prod_orders

            return orders, 0, state.traderData or ""

    return Trader


def eval_params(take_edge, quote_offset, inv_skew, emerald_fv):
    reader = PackageResourcesReader()
    total = 0
    for day in [-2, -1]:
        trader = make_trader(take_edge, quote_offset, inv_skew, emerald_fv)()
        result = run_backtest(trader, reader, 0, day, False, TradeMatchingMode.all, True, False)
        last_ts = result.activity_logs[-1].timestamp
        for row in reversed(result.activity_logs):
            if row.timestamp != last_ts:
                break
            total += row.columns[-1]
    return total


def main():
    take_edges = [0, 0.5, 1]
    quote_offsets = [1, 2, 3]
    inv_skews = [0, 0.05, 0.1, 0.2]
    emerald_fvs = [9999, 10000, 10001]

    results = []
    total_combos = len(take_edges) * len(quote_offsets) * len(inv_skews) * len(emerald_fvs)
    print(f"Running {total_combos} parameter combinations...")

    for i, (te, qo, inv, efv) in enumerate(iterproduct(take_edges, quote_offsets, inv_skews, emerald_fvs)):
        profit = eval_params(te, qo, inv, efv)
        results.append((profit, te, qo, inv, efv))
        if (i + 1) % 12 == 0:
            print(f"  {i+1}/{total_combos} done...")

    results.sort(reverse=True)

    print(f"\n{'Profit':>10}  {'TakeEdge':>8}  {'QuoteOff':>8}  {'InvSkew':>8}  {'EmerFV':>8}")
    print("-" * 55)
    for profit, te, qo, inv, efv in results[:15]:
        print(f"{profit:>10,.0f}  {te:>8.1f}  {qo:>8}  {inv:>8.2f}  {efv:>8}")


if __name__ == "__main__":
    main()
