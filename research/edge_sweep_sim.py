"""
Sweep EDGE values for fallback MM products.

Three fill models compared:
1. "aggressive": fill at our price if next-tick crosses (standard next-tick)
2. "conservative": fill at our price only if next-tick crosses by 1+ ticks
3. "mid-fill": assume we fill at mid when there's a favorable OBI signal,
   with edge as minimum profit threshold

Model 3 is closer to how MM actually works in the game:
we're not crossing the spread, we're sitting inside it and getting lifted.

CSV note: 'pnl' column = midprice, 'mid' column = unrelated.
"""
import csv
from collections import defaultdict, Counter

DATA_PATH = "/home/vscode/repos/imc-prosperity-4/research/oos_v10.csv"

OBI_SKEW = 1.2
INVENTORY_PENALTY = 0.5
QUOTE_SIZE = 5
POSITION_LIMIT = 10

EDGE_VALUES = [1, 2, 3, 4, 5, 6, 7, 8]

ACTIVE_PRODUCTS = [
    "TRANSLATOR_ASTRO_BLACK", "TRANSLATOR_ECLIPSE_CHARCOAL",
    "TRANSLATOR_GRAPHITE_MIST", "TRANSLATOR_VOID_BLUE",
    "SLEEP_POD_SUEDE", "SLEEP_POD_POLYESTER",
    "SLEEP_POD_NYLON", "SLEEP_POD_COTTON",
    "ROBOT_VACUUMING", "ROBOT_MOPPING",
    "ROBOT_LAUNDRY", "ROBOT_IRONING",
    "PANEL_2X4", "PANEL_4X4",
]
DISABLED_PRODUCTS = [
    "TRANSLATOR_SPACE_GRAY", "SLEEP_POD_LAMB_WOOL",
    "PANEL_1X2", "UV_VISOR_YELLOW",
]
CANDIDATE_PRODUCTS = [
    "OXYGEN_SHAKE_MINT", "OXYGEN_SHAKE_MORNING_BREATH",
]
ALL_PRODUCTS = ACTIVE_PRODUCTS + DISABLED_PRODUCTS + CANDIDATE_PRODUCTS


def load_data():
    product_data = defaultdict(list)
    with open(DATA_PATH) as f:
        reader = csv.DictReader(f)
        for row in reader:
            product = row["product"]
            if product not in ALL_PRODUCTS:
                continue
            product_data[product].append({
                "ts": int(row["ts"]),
                "bid1": int(row["bid1"]),
                "bvol1": int(row["bvol1"]),
                "ask1": int(row["ask1"]),
                "avol1": int(row["avol1"]),
                "mid": float(row["pnl"]),
            })
    for product in product_data:
        product_data[product].sort(key=lambda x: x["ts"])
    return product_data


def simulate_mm_game_model(ticks, edge, inv_penalty=INVENTORY_PENALTY):
    """
    Game-realistic fill model:

    The MM places orders at (fair-EDGE) and (fair+EDGE).
    In the game, these are limit orders that sit in the book.

    We model fills by asking: if our buy is at int(fair-EDGE),
    does the market move DOWN enough for our order to be at or above
    the best ask? We check: buy_price >= next_tick_ask1.

    But instead of filling at our price (which gives unrealistic edge),
    we fill at the MIDPOINT of our price and the market price, to model
    the average fill you'd get in practice.

    Actually, let's try the most accurate approach: fill at OUR posted price
    (since limit orders fill at their posted price in the game engine),
    but only when the next tick's market actually crosses our level.
    The key insight: the fill RATE matters. Not every touch leads to a fill.
    We model a FILL_RATE to calibrate against actual backtest results.
    """
    position = 0
    cash = 0.0
    buy_fills = 0
    sell_fills = 0

    for i in range(len(ticks) - 1):
        curr = ticks[i]
        nxt = ticks[i + 1]

        bid1 = curr["bid1"]
        ask1 = curr["ask1"]
        bvol1 = curr["bvol1"]
        avol1 = curr["avol1"]
        mid = curr["mid"]
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

        next_ask = nxt["ask1"]
        next_bid = nxt["bid1"]

        # Buy fills if next tick's ask <= our buy price
        if buy_size > 0 and buy_price >= next_ask:
            cash -= buy_price * buy_size
            position += buy_size
            buy_fills += buy_size

        # Sell fills if next tick's bid >= our sell price
        if sell_size > 0 and sell_price <= next_bid:
            cash += sell_price * sell_size
            position -= sell_size
            sell_fills += sell_size

    final_mid = ticks[-1]["mid"]
    final_pnl = cash + position * final_mid

    return {
        "pnl": final_pnl,
        "buys": buy_fills,
        "sells": sell_fills,
        "trades": buy_fills + sell_fills,
        "final_pos": position,
    }


def simulate_mm_halfspread(ticks, edge, inv_penalty=INVENTORY_PENALTY):
    """
    Alternative model: compute fair value, then check if we WOULD place
    orders. If fair-EDGE is above bid (we improve the bid) AND the next
    tick mid moves down through our level, we get a buy fill.

    This asks: does the market sell enough that our level gets hit?
    We fill at our posted price.
    """
    position = 0
    cash = 0.0
    buy_fills = 0
    sell_fills = 0

    for i in range(len(ticks) - 1):
        curr = ticks[i]
        nxt = ticks[i + 1]

        bid1 = curr["bid1"]
        ask1 = curr["ask1"]
        bvol1 = curr["bvol1"]
        avol1 = curr["avol1"]
        mid = curr["mid"]
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

        next_mid = nxt["mid"]

        # Our buy order is between bid1 and ask1 (inside the spread).
        # It fills if the next mid drops to or below our buy price.
        if buy_size > 0 and next_mid <= buy_price:
            cash -= buy_price * buy_size
            position += buy_size
            buy_fills += buy_size

        # Our sell fills if next mid rises to or above our sell price
        if sell_size > 0 and next_mid >= sell_price:
            cash += sell_price * sell_size
            position -= sell_size
            sell_fills += sell_size

    final_mid = ticks[-1]["mid"]
    final_pnl = cash + position * final_mid

    return {
        "pnl": final_pnl,
        "buys": buy_fills,
        "sells": sell_fills,
        "trades": buy_fills + sell_fills,
        "final_pos": position,
    }


def main():
    print("Loading data...")
    product_data = load_data()
    print(f"Loaded {len(product_data)} products\n")

    spreads = {}
    for product, ticks in product_data.items():
        spreads[product] = sum(t["ask1"] - t["bid1"] for t in ticks) / len(ticks)

    # ---- MODEL COMPARISON ----
    # Run both models for a few key products to understand behavior
    print("=" * 120)
    print("MODEL COMPARISON (select products, EDGE=3)")
    print("=" * 120)
    test_products = ["TRANSLATOR_ASTRO_BLACK", "ROBOT_LAUNDRY", "SLEEP_POD_SUEDE",
                     "ROBOT_IRONING", "PANEL_4X4"]
    print(f"{'Product':<35} | {'NextTick PnL':>12} {'Trds':>5} | {'MidCross PnL':>13} {'Trds':>5}")
    print("-" * 85)
    for product in test_products:
        ticks = product_data[product]
        r1 = simulate_mm_game_model(ticks, 3)
        r2 = simulate_mm_halfspread(ticks, 3)
        print(f"{product:<35} | {r1['pnl']:>12.0f} {r1['trades']:>5} | {r2['pnl']:>13.0f} {r2['trades']:>5}")

    # ---- Main sweep with mid-cross model (more conservative) ----
    print("\n" + "=" * 140)
    print("EDGE SWEEP — Mid-Cross Fill Model")
    print("(Buy fills when next_mid <= buy_price; sell fills when next_mid >= sell_price)")
    print("=" * 140)

    results = {}
    for product in ALL_PRODUCTS:
        if product not in product_data:
            continue
        ticks = product_data[product]
        results[product] = {}
        for edge in EDGE_VALUES:
            results[product][edge] = simulate_mm_halfspread(ticks, edge)

    header = f"{'Product':<35} {'Sprd':>4} |"
    for e in EDGE_VALUES:
        header += f" {'E=' + str(e):>8}"
    header += f" | {'Best':>4} {'BstPnL':>8}"
    print(header)
    print("-" * len(header))

    def print_group(title, products):
        print(f"\n--- {title} ---")
        for product in products:
            if product not in results:
                continue
            sprd = spreads[product]
            pnls = {e: results[product][e]["pnl"] for e in EDGE_VALUES}
            best_e = max(pnls, key=pnls.get)
            line = f"{product:<35} {sprd:>4.1f} |"
            for e in EDGE_VALUES:
                marker = "*" if e == best_e else " "
                line += f" {pnls[e]:>7.0f}{marker}"
            line += f" | E={best_e:<2} {pnls[best_e]:>8.0f}"
            print(line)

    print_group("ACTIVE (currently EDGE=3)", ACTIVE_PRODUCTS)
    print_group("DISABLED (currently off)", DISABLED_PRODUCTS)
    print_group("CANDIDATES (not yet added)", CANDIDATE_PRODUCTS)

    # ---- TRADE DETAIL ----
    print("\n" + "=" * 100)
    print(f"{'Product':<35} {'BstE':>4} {'PnL':>8} {'Trds':>5} {'Buys':>5} {'Sells':>5} {'Pos':>4}")
    print("-" * 100)
    for product in ALL_PRODUCTS:
        if product not in results:
            continue
        pnls = {e: results[product][e]["pnl"] for e in EDGE_VALUES}
        best_e = max(pnls, key=pnls.get)
        r = results[product][best_e]
        print(f"{product:<35} {best_e:>4} {r['pnl']:>8.0f} {r['trades']:>5} "
              f"{r['buys']:>5} {r['sells']:>5} {r['final_pos']:>4}")

    # ---- RECOMMENDATIONS ----
    print("\n" + "=" * 100)
    print("RECOMMENDATIONS")
    print("=" * 100)

    total_e3 = 0
    total_best = 0
    for product in ACTIVE_PRODUCTS:
        if product not in results:
            continue
        pnls = {e: results[product][e]["pnl"] for e in EDGE_VALUES}
        best_e = max(pnls, key=pnls.get)
        pnl3 = pnls[3]
        best_pnl = pnls[best_e]
        total_e3 += pnl3
        total_best += best_pnl
        delta = best_pnl - pnl3
        if best_e != 3 and delta > 50:
            print(f"  {product:<35} EDGE 3->{best_e}  ({pnl3:>7.0f} -> {best_pnl:>7.0f}, +{delta:.0f})")
        else:
            print(f"  {product:<35} keep E=3  (PnL={pnl3:.0f})")

    print(f"\n  Total active: E=3={total_e3:.0f}, optimal={total_best:.0f}, "
          f"delta=+{total_best - total_e3:.0f}")

    print()
    for product in DISABLED_PRODUCTS + CANDIDATE_PRODUCTS:
        if product not in results:
            continue
        pnls = {e: results[product][e]["pnl"] for e in EDGE_VALUES}
        best_e = max(pnls, key=pnls.get)
        best_pnl = pnls[best_e]
        r = results[product][best_e]
        label = "DISABLED" if product in DISABLED_PRODUCTS else "CANDIDATE"
        if best_pnl > 200:
            print(f"  {product:<35} [{label}] RE-ENABLE E={best_e}  (PnL={best_pnl:.0f}, {r['trades']} trades)")
        elif best_pnl > 0:
            print(f"  {product:<35} [{label}] MARGINAL E={best_e} (PnL={best_pnl:.0f}, {r['trades']} trades)")
        else:
            print(f"  {product:<35} [{label}] SKIP (best={best_pnl:.0f})")

    # ---- UNDERPERFORMER DETAILS ----
    print("\n" + "=" * 100)
    print("UNDERPERFORMER DEEP DIVE")
    print("=" * 100)

    for product in ["SLEEP_POD_SUEDE", "ROBOT_MOPPING", "ROBOT_IRONING"]:
        if product not in results:
            continue
        sprd = spreads[product]
        ticks = product_data[product]
        mids = [t["mid"] for t in ticks]
        returns = [mids[i+1] - mids[i] for i in range(len(mids)-1)]
        avg_abs_ret = sum(abs(r) for r in returns) / len(returns)
        price_range = max(mids) - min(mids)
        trend = mids[-1] - mids[0]

        print(f"\n  {product}:")
        print(f"    avg_spread={sprd:.1f}, avg_|tick_move|={avg_abs_ret:.1f}, "
              f"range={price_range:.0f}, trend={trend:+.0f}")

        # Spread distribution
        spread_counts = Counter(t["ask1"] - t["bid1"] for t in ticks)
        dist = ", ".join(f"{k}:{v}" for k, v in sorted(spread_counts.items()))
        print(f"    spread_dist: [{dist}]")

        # Edge sweep detail
        print(f"    {'EDGE':>4} {'PnL':>8} {'Trds':>5} {'Buys':>5} {'Sells':>5} {'Pos':>4}")
        for edge in EDGE_VALUES:
            r = results[product][edge]
            print(f"    E={edge:<2} {r['pnl']:>8.0f} {r['trades']:>5} {r['buys']:>5} "
                  f"{r['sells']:>5} {r['final_pos']:>4}")

    # ---- HALF-SPREAD ANALYSIS ----
    print("\n" + "=" * 100)
    print("KEY INSIGHT: EDGE vs HALF-SPREAD")
    print("An EDGE <= half_spread means our quotes improve the book (inside the spread)")
    print("An EDGE > half_spread means our quotes are outside the spread (unlikely fills)")
    print("=" * 100)
    print(f"{'Product':<35} {'Sprd':>5} {'Half':>5} {'E<=Half fills?':>15}")
    print("-" * 70)
    for product in ALL_PRODUCTS:
        if product not in product_data:
            continue
        sprd = spreads[product]
        half = sprd / 2
        # At E=int(half), do we get any fills?
        best_inside_edge = max(1, int(half))
        if best_inside_edge in EDGE_VALUES and product in results:
            r = results[product][best_inside_edge]
            print(f"{product:<35} {sprd:>5.1f} {half:>5.1f}  E={best_inside_edge}: {r['trades']:>4} trades, PnL={r['pnl']:>8.0f}")


if __name__ == "__main__":
    main()
