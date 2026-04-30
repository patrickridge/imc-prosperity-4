"""Sweep EDGE for SNACKPACK MM using a theoretical spread-capture model.

Instead of trying to simulate order fills from LOB snapshots (which
can't capture passive fills accurately), this script:

1. Computes fair value at each tick
2. Measures adverse selection: how much does mid move against our fill
   on the ticks when we WOULD get filled
3. Estimates PnL/fill = edge_captured - adverse_selection - inventory_cost
4. Estimates fill rate from LOB depth and spread vs edge

This gives a more accurate picture of which edges are profitable.
"""

import csv
import math
from collections import defaultdict

CSV_PATH = "/home/vscode/repos/imc-prosperity-4/research/oos_v10.csv"

OBI_SKEW = 1.2
QUOTE_SIZE = 5
POSITION_LIMIT = 10

PRODUCTS = [
    "SNACKPACK_VANILLA",
    "SNACKPACK_STRAWBERRY",
    "SNACKPACK_PISTACHIO",
    "SNACKPACK_CHOCOLATE",
    "SNACKPACK_RASPBERRY",
]

EDGE_VALUES = [4, 5, 6, 7, 8, 9, 10, 11, 12]
INV_PENALTY_VALUES = [0.4, 0.6, 0.8, 1.0, 1.2]


def load_snackpack_data(path):
    data = defaultdict(list)
    with open(path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["product"] not in PRODUCTS:
                continue
            if not row["bid1"] or not row["ask1"]:
                continue
            bid1 = int(row["bid1"])
            ask1 = int(row["ask1"])
            parsed = {
                "ts": int(row["ts"]),
                "bid1": bid1,
                "ask1": ask1,
                "bvol1": int(row["bvol1"]),
                "avol1": int(row["avol1"]),
                "mid": (bid1 + ask1) / 2.0,
            }
            data[row["product"]].append(parsed)
    for product in data:
        data[product].sort(key=lambda r: r["ts"])
    return data


def analyze_microstructure(rows):
    """Compute key microstructure stats."""
    spreads = []
    mid_changes = []
    volatilities = []

    for i in range(len(rows)):
        r = rows[i]
        spreads.append(r["ask1"] - r["bid1"])
        if i > 0:
            delta = r["mid"] - rows[i - 1]["mid"]
            mid_changes.append(delta)
            volatilities.append(abs(delta))

    avg_spread = sum(spreads) / len(spreads)
    avg_vol = sum(volatilities) / len(volatilities) if volatilities else 0
    std_mid = (
        sum((d - sum(mid_changes) / len(mid_changes)) ** 2 for d in mid_changes)
        / len(mid_changes)
    ) ** 0.5 if mid_changes else 0

    return avg_spread, avg_vol, std_mid


def simulate_mm_realistic(rows, edge, inv_penalty):
    """Simulate MM using the actual backtester's fill model.

    The backtester processes orders against the existing LOB:
    - Buy orders at price P: matched against sell orders at P or lower
    - The order walks the book from best ask upward

    In our case, we place:
    - Buy at int(fair - edge): fills against asks at that price or lower
    - Sell at int(fair + edge): fills against bids at that price or higher

    With spread ~16 and edge ~8, our buy is at mid-8 and ask1 is at mid+8.
    So buy_price = mid-8 and ask1 = mid+8. They don't cross.

    BUT: the backtester also fills our orders against other bots' orders
    that arrive in the same tick. This is the key we can't simulate.

    ALTERNATIVE: Use mid-price return model.
    PnL per round trip = 2*edge - adverse_selection
    where adverse_selection = E[|mid_change| | filled]

    For passive MM at edge E from mid with spread S:
    - Our quote gets filled when mid moves by >= (S/2 - E) toward us
    - After fill, we're exposed to further adverse movement
    - Expected adverse selection increases with fill probability
    """
    position = 0
    cash = 0.0
    buy_fills = 0
    sell_fills = 0

    for i in range(len(rows)):
        r = rows[i]
        bid1 = r["bid1"]
        ask1 = r["ask1"]
        bvol1 = r["bvol1"]
        avol1 = r["avol1"]
        mid = r["mid"]
        spread = ask1 - bid1

        total_vol = bvol1 + avol1
        if total_vol == 0:
            continue

        obi = (bvol1 - avol1) / total_vol
        fair = mid + OBI_SKEW * obi * (spread / 2) - inv_penalty * position

        buy_price = int(fair - edge)
        sell_price = int(fair + edge)
        buy_size = min(QUOTE_SIZE, POSITION_LIMIT - position)
        sell_size = min(QUOTE_SIZE, POSITION_LIMIT + position)

        # Only aggressive fills against visible book
        if buy_size > 0 and buy_price >= ask1:
            fill_qty = min(buy_size, avol1)
            cash -= ask1 * fill_qty
            position += fill_qty
            buy_fills += fill_qty

        sell_size = min(QUOTE_SIZE, POSITION_LIMIT + position)
        if sell_size > 0 and sell_price <= bid1:
            fill_qty = min(sell_size, bvol1)
            cash += bid1 * fill_qty
            position -= fill_qty
            sell_fills += fill_qty

    last_mid = rows[-1]["mid"] if rows else 0
    pnl = cash + position * last_mid
    return pnl, position, buy_fills, sell_fills


def estimate_fill_pnl(rows, edge, inv_penalty):
    """Estimate PnL using a probabilistic model.

    At each tick, compute where our quotes would be placed.
    If the next tick's price movement would trigger a fill:
    - Buy fills when ask drops below our buy_price
    - Sell fills when bid rises above our sell_price

    Key improvement: also count fills from OBI skew pushing our
    fair value closer to one side, potentially crossing the spread.
    """
    position = 0
    cash = 0.0
    buy_fills = 0
    sell_fills = 0
    aggressive_buys = 0
    aggressive_sells = 0

    for i in range(len(rows)):
        r = rows[i]
        bid1 = r["bid1"]
        ask1 = r["ask1"]
        bvol1 = r["bvol1"]
        avol1 = r["avol1"]
        mid = r["mid"]
        spread = ask1 - bid1

        total_vol = bvol1 + avol1
        if total_vol == 0:
            continue

        obi = (bvol1 - avol1) / total_vol
        fair = mid + OBI_SKEW * obi * (spread / 2) - inv_penalty * position

        buy_price = int(fair - edge)
        sell_price = int(fair + edge)
        buy_size = min(QUOTE_SIZE, POSITION_LIMIT - position)
        sell_size = min(QUOTE_SIZE, POSITION_LIMIT + position)

        bought = False
        sold = False

        # 1. Aggressive cross on current tick
        if buy_size > 0 and buy_price >= ask1:
            fill_qty = min(buy_size, avol1)
            cash -= ask1 * fill_qty
            position += fill_qty
            buy_fills += fill_qty
            aggressive_buys += fill_qty
            bought = True

        sell_size = min(QUOTE_SIZE, POSITION_LIMIT + position)
        if sell_size > 0 and sell_price <= bid1:
            fill_qty = min(sell_size, bvol1)
            cash += bid1 * fill_qty
            position -= fill_qty
            sell_fills += fill_qty
            aggressive_sells += fill_qty
            sold = True

        # 2. Passive fills: check if the NEXT tick's book would
        #    fill our resting orders (price moved to our level)
        if i + 1 < len(rows) and not bought:
            next_r = rows[i + 1]
            buy_size = min(QUOTE_SIZE, POSITION_LIMIT - position)
            # Our resting buy at buy_price fills if next tick someone
            # offers at or below our price
            if buy_size > 0 and buy_price >= next_r["ask1"]:
                fill_qty = min(buy_size, next_r["avol1"])
                if fill_qty > 0:
                    cash -= buy_price * fill_qty
                    position += fill_qty
                    buy_fills += fill_qty

        if i + 1 < len(rows) and not sold:
            next_r = rows[i + 1]
            sell_size = min(QUOTE_SIZE, POSITION_LIMIT + position)
            if sell_size > 0 and sell_price <= next_r["bid1"]:
                fill_qty = min(sell_size, next_r["bvol1"])
                if fill_qty > 0:
                    cash += sell_price * fill_qty
                    position -= fill_qty
                    sell_fills += fill_qty

    last_mid = rows[-1]["mid"] if rows else 0
    pnl = cash + position * last_mid
    return pnl, position, buy_fills, sell_fills, aggressive_buys, aggressive_sells


def main():
    data = load_snackpack_data(CSV_PATH)

    # Microstructure analysis
    print("=" * 90)
    print("MICROSTRUCTURE ANALYSIS")
    print("=" * 90)
    print(
        f"  {'Product':<28}{'AvgSprd':>8}{'AvgMov':>8}{'StdMid':>8}"
        f"{'HalfSprd':>9}{'Sprd/Vol':>9}"
    )
    for product in PRODUCTS:
        rows = data[product]
        avg_spread, avg_vol, std_mid = analyze_microstructure(rows)
        half_spread = avg_spread / 2
        ratio = avg_spread / avg_vol if avg_vol > 0 else 0
        print(
            f"  {product:<28}{avg_spread:>8.1f}{avg_vol:>8.1f}{std_mid:>8.1f}"
            f"{half_spread:>9.1f}{ratio:>9.1f}"
        )

    # Count how often OBI pushes fair value significantly
    print()
    print("OBI skew analysis (how much OBI shifts fair from mid):")
    for product in PRODUCTS:
        rows = data[product]
        skews = []
        for r in rows:
            bv = r["bvol1"]
            av = r["avol1"]
            total = bv + av
            if total == 0:
                continue
            obi = (bv - av) / total
            spread = r["ask1"] - r["bid1"]
            skew = OBI_SKEW * obi * (spread / 2)
            skews.append(skew)
        avg_abs_skew = sum(abs(s) for s in skews) / len(skews)
        max_skew = max(abs(s) for s in skews)
        print(f"  {product:<28} avg_|skew|={avg_abs_skew:.2f}, max_|skew|={max_skew:.2f}")

    # Phase 1: Edge sweep with passive+aggressive model
    print()
    print("=" * 90)
    print("PHASE 1: EDGE SWEEP (passive+aggressive, inv_penalty=0.8)")
    print("=" * 90)

    best_edges = {}
    all_results = {}

    header = f"{'Product':<28}" + "".join(f"{'E=' + str(e):>9}" for e in EDGE_VALUES)
    print(header)
    print("-" * len(header))

    for product in PRODUCTS:
        rows = data[product]
        best_pnl = -999999
        best_edge = EDGE_VALUES[0]
        results = []

        for edge_val in EDGE_VALUES:
            pnl, pos, bf, sf, ab, as_ = estimate_fill_pnl(rows, edge_val, 0.8)
            results.append(pnl)
            all_results[(product, edge_val)] = (pnl, pos, bf, sf, ab, as_)
            if pnl > best_pnl:
                best_pnl = pnl
                best_edge = edge_val

        best_edges[product] = best_edge
        line = f"{product:<28}" + "".join(f"{int(p):>9}" for p in results)
        print(line)

    print()
    print("Best EDGE per product:")
    for product in PRODUCTS:
        e = best_edges[product]
        pnl, pos, bf, sf, ab, as_ = all_results[(product, e)]
        print(
            f"  {product:<28} edge={e:<4} PnL={int(pnl):>7}"
            f"  buys={bf}(agg={ab}) sells={sf}(agg={as_})"
            f"  final_pos={pos}"
        )

    # Phase 2: Aggressive-only model (baseline)
    print()
    print("=" * 90)
    print("PHASE 2: AGGRESSIVE-ONLY (for comparison)")
    print("=" * 90)

    header = f"{'Product':<28}" + "".join(f"{'E=' + str(e):>9}" for e in EDGE_VALUES)
    print(header)
    print("-" * len(header))

    for product in PRODUCTS:
        rows = data[product]
        results = []
        for edge_val in EDGE_VALUES:
            pnl, pos, bf, sf = simulate_mm_realistic(rows, edge_val, 0.8)
            results.append(pnl)
        line = f"{product:<28}" + "".join(f"{int(p):>9}" for p in results)
        print(line)

    # Phase 3: Inventory penalty sweep
    print()
    print("=" * 90)
    print("PHASE 3: INVENTORY PENALTY SWEEP (at best edge)")
    print("=" * 90)

    header2 = f"{'Product':<28}" + "".join(f"{'P=' + str(p):>9}" for p in INV_PENALTY_VALUES)
    print(header2)
    print("-" * len(header2))

    best_inv = {}
    for product in PRODUCTS:
        rows = data[product]
        edge_val = best_edges[product]
        results = []
        best_pnl = -999999
        best_p = INV_PENALTY_VALUES[0]

        for inv_p in INV_PENALTY_VALUES:
            pnl, _, _, _, _, _ = estimate_fill_pnl(rows, edge_val, inv_p)
            results.append(pnl)
            if pnl > best_pnl:
                best_pnl = pnl
                best_p = inv_p

        best_inv[product] = best_p
        line = f"{product:<28}" + "".join(f"{int(p):>9}" for p in results)
        print(f"{line}  (edge={edge_val})")

    # Phase 4: Detailed analysis
    print()
    print("=" * 90)
    print("PHASE 4: FILL BREAKDOWN")
    print("=" * 90)

    for product in PRODUCTS:
        rows = data[product]
        spread = sum(r["ask1"] - r["bid1"] for r in rows) / len(rows)
        print(f"\n{product} (avg_spread={spread:.1f}):")
        print(
            f"  {'Edge':<6}{'PnL':>8}{'Pos':>6}"
            f"{'Buys':>7}{'Sells':>7}{'AggB':>6}{'AggS':>6}{'PnL/Fill':>10}"
        )

        for edge_val in EDGE_VALUES:
            pnl, pos, bf, sf, ab, as_ = estimate_fill_pnl(rows, edge_val, 0.8)
            total = bf + sf
            pnl_per = pnl / total if total > 0 else 0
            print(
                f"  {edge_val:<6}{int(pnl):>8}{pos:>6}"
                f"{bf:>7}{sf:>7}{ab:>6}{as_:>6}{pnl_per:>10.1f}"
            )

    # Summary
    print()
    print("=" * 90)
    print("SUMMARY & RECOMMENDATIONS")
    print("=" * 90)
    print()
    print("NOTE: This simulation can only model aggressive fills (our quote")
    print("crosses the existing book) and next-tick passive fills (book moves")
    print("to our level). The actual backtester fills against bot order flow")
    print("which we cannot observe in LOB snapshots. Results are directional.")
    print()
    for product in PRODUCTS:
        e = best_edges[product]
        pnl, pos, bf, sf, ab, as_ = all_results[(product, e)]
        bp = best_inv[product]
        total = bf + sf
        status = "ENABLE" if pnl > 50 else ("MARGINAL" if pnl > -100 else "DISABLE")
        print(
            f"  {product:<28} edge={e:<4} inv_pen={bp:<5}"
            f" PnL={int(pnl):>7} ({total} fills) -> {status}"
        )


if __name__ == "__main__":
    main()
