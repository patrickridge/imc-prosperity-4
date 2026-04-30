"""Sweep EDGE and OBI_SKEW for microchip MM using actual trade + price data.

Fill model: At each timestamp we compute our bid/ask quotes.
When a bot trade happens, we check if the trade would fill our resting order:
- If trade_price < mid and trade_price <= our_bid: seller hit our bid -> we buy
- If trade_price > mid and trade_price >= our_ask: buyer lifted our ask -> we sell
"""

import csv
from collections import defaultdict

DATA_DIR = "/home/vscode/repos/imc-prosperity-4/data/round5"
DAYS = [2, 3, 4]

PRODUCTS = [
    "MICROCHIP_SQUARE",
    "MICROCHIP_TRIANGLE",
    "MICROCHIP_CIRCLE",
    "MICROCHIP_RECTANGLE",
    "MICROCHIP_OVAL",
]

POSITION_LIMIT = 10
QUOTE_SIZE = 5
INVENTORY_PENALTY = 0.5


def load_all_data():
    """Load all price and trade data once, keyed by (day, timestamp, product)."""
    all_prices = {}
    all_trades = defaultdict(list)

    for day in DAYS:
        # Load prices
        fname = f"{DATA_DIR}/prices_round_5_day_{day}.csv"
        with open(fname) as f:
            reader = csv.DictReader(f, delimiter=";")
            for row in reader:
                product = row["product"]
                if product not in PRODUCTS:
                    continue
                ts = int(row["timestamp"])
                all_prices[(day, ts, product)] = {
                    "bid1": float(row["bid_price_1"]),
                    "bvol1": float(row["bid_volume_1"]),
                    "ask1": float(row["ask_price_1"]),
                    "avol1": float(row["ask_volume_1"]),
                    "mid": float(row["mid_price"]),
                }

        # Load trades
        fname = f"{DATA_DIR}/trades_round_5_day_{day}.csv"
        with open(fname) as f:
            reader = csv.DictReader(f, delimiter=";")
            for row in reader:
                product = row["symbol"]
                if product not in PRODUCTS:
                    continue
                ts = int(row["timestamp"])
                all_trades[(day, ts, product)].append({
                    "price": float(row["price"]),
                    "qty": int(row["quantity"]),
                })

    # Build sorted timestamp lists per (day, product)
    ts_index = defaultdict(list)
    for (day, ts, product) in all_prices:
        ts_index[(day, product)].append(ts)
    for key in ts_index:
        ts_index[key].sort()

    return all_prices, all_trades, ts_index


def simulate_product(all_prices, all_trades, ts_index, product, edge, obi_skew):
    """Simulate across all days, summing PnL (position resets each day)."""
    total_pnl = 0
    total_buys = 0
    total_sells = 0

    for day in DAYS:
        timestamps = ts_index.get((day, product), [])
        position = 0
        cash = 0.0
        last_mid = None

        for ts in timestamps:
            key = (day, ts, product)
            p = all_prices[key]
            bid1 = p["bid1"]
            ask1 = p["ask1"]
            bvol1 = p["bvol1"]
            avol1 = p["avol1"]
            mid = p["mid"]
            last_mid = mid
            spread = ask1 - bid1

            total_vol = bvol1 + avol1
            obi = (bvol1 - avol1) / total_vol if total_vol > 0 else 0

            fair = mid + obi_skew * obi * (spread / 2) - INVENTORY_PENALTY * position

            our_bid = int(fair - edge)
            our_ask = int(fair + edge)

            buy_capacity = min(QUOTE_SIZE, POSITION_LIMIT - position)
            sell_capacity = min(QUOTE_SIZE, POSITION_LIMIT + position)

            for trade in all_trades.get(key, []):
                tp = trade["price"]
                tq = trade["qty"]

                if tp < mid and tp <= our_bid and buy_capacity > 0:
                    fill = min(tq, buy_capacity)
                    position += fill
                    cash -= our_bid * fill
                    buy_capacity -= fill
                    total_buys += fill

                elif tp > mid and tp >= our_ask and sell_capacity > 0:
                    fill = min(tq, sell_capacity)
                    position -= fill
                    cash += our_ask * fill
                    sell_capacity -= fill
                    total_sells += fill

        if last_mid is not None:
            total_pnl += cash + position * last_mid

    return total_pnl, total_buys, total_sells


def main():
    print("Loading data...", flush=True)
    all_prices, all_trades, ts_index = load_all_data()
    print("Data loaded.\n")

    # Phase 1: Sweep EDGE with OBI_SKEW=1.0
    print("=" * 85)
    print("PHASE 1: EDGE sweep (OBI_SKEW=1.0)")
    print(f"Data: round5 days {DAYS}")
    print("=" * 85)

    best_edge = {}
    edge_values = [1, 2, 3, 4, 5, 6, 7]

    for product in PRODUCTS:
        # Compute avg spread
        day2_keys = [(2, ts, product) for ts in ts_index.get((2, product), [])]
        spreads = [all_prices[k]["ask1"] - all_prices[k]["bid1"] for k in day2_keys]
        avg_spread = sum(spreads) / len(spreads) if spreads else 0

        print(f"\n{product}  (avg spread={avg_spread:.1f})")
        print(f"  {'EDGE':>5}  {'PnL':>10}  {'Buys':>6}  {'Sells':>6}")

        best_pnl = -1e18
        for edge_val in edge_values:
            pnl, buys, sells = simulate_product(
                all_prices, all_trades, ts_index, product, edge_val, obi_skew=1.0
            )
            marker = ""
            if pnl > best_pnl:
                best_pnl = pnl
                best_edge[product] = edge_val
                marker = " <-- best"
            print(f"  {edge_val:>5}  {pnl:>10,.0f}  {buys:>6}  {sells:>6}{marker}")

    print(f"\n{'Product':<25} {'BestEDGE':>8}")
    for p in PRODUCTS:
        print(f"  {p:<23} {best_edge[p]:>8}")

    # Phase 2: Sweep OBI_SKEW with best EDGE per product
    print("\n" + "=" * 85)
    print("PHASE 2: OBI_SKEW sweep (using best EDGE per product)")
    print("=" * 85)

    obi_values = [0.0, 0.5, 1.0, 1.5, 2.0]
    best_obi = {}

    for product in PRODUCTS:
        edge_val = best_edge[product]
        print(f"\n{product}  (EDGE={edge_val})")
        print(f"  {'OBI_SKEW':>8}  {'PnL':>10}  {'Buys':>6}  {'Sells':>6}")

        best_pnl = -1e18
        for obi_s in obi_values:
            pnl, buys, sells = simulate_product(
                all_prices, all_trades, ts_index, product, edge_val, obi_skew=obi_s
            )
            marker = ""
            if pnl > best_pnl:
                best_pnl = pnl
                best_obi[product] = obi_s
                marker = " <-- best"
            print(f"  {obi_s:>8.1f}  {pnl:>10,.0f}  {buys:>6}  {sells:>6}{marker}")

    # Summary
    print("\n" + "=" * 85)
    print("SUMMARY: Current (EDGE=2, OBI=1.0) vs Optimal")
    print("=" * 85)

    current_total = 0
    optimal_total = 0
    header = f"{'Product':<25} {'Cur PnL':>10} {'Opt PnL':>10} {'Delta':>10} {'EDGE':>5} {'OBI':>5}"
    print(f"\n{header}")

    for product in PRODUCTS:
        cur_pnl, _, _ = simulate_product(
            all_prices, all_trades, ts_index, product, edge=2, obi_skew=1.0
        )
        opt_edge = best_edge[product]
        opt_obi = best_obi[product]
        opt_pnl, _, _ = simulate_product(
            all_prices, all_trades, ts_index, product, edge=opt_edge, obi_skew=opt_obi
        )
        delta = opt_pnl - cur_pnl
        current_total += cur_pnl
        optimal_total += opt_pnl
        print(f"  {product:<23} {cur_pnl:>10,.0f} {opt_pnl:>10,.0f} {delta:>+10,.0f} {opt_edge:>5} {opt_obi:>5.1f}")

    print(f"\n  {'TOTAL':<23} {current_total:>10,.0f} {optimal_total:>10,.0f} {optimal_total - current_total:>+10,.0f}")


if __name__ == "__main__":
    main()
