"""Scan all GALAXY_SOUNDS and OXYGEN_SHAKE products for best directional strategy."""

import csv
from collections import defaultdict

CSV_PATH = "/home/vscode/repos/imc-prosperity-4/research/oos_v10.csv"
POSITION_LIMIT = 10
TARGET_PREFIXES = ("GALAXY_SOUNDS_", "OXYGEN_SHAKE_")


def load_data():
    """Load mid, bid1, ask1 time series per product."""
    products = defaultdict(lambda: {"ts": [], "mid": [], "bid1": [], "ask1": []})
    with open(CSV_PATH) as f:
        reader = csv.DictReader(f)
        for row in reader:
            p = row["product"]
            if not any(p.startswith(pfx) for pfx in TARGET_PREFIXES):
                continue
            ts = int(row["ts"])
            if not row["pnl"] or not row["bid1"] or not row["ask1"]:
                continue
            mid = float(row["pnl"])  # "pnl" column actually holds mid price
            bid1 = int(row["bid1"])
            ask1 = int(row["ask1"])
            products[p]["ts"].append(ts)
            products[p]["mid"].append(mid)
            products[p]["bid1"].append(bid1)
            products[p]["ask1"].append(ask1)
    return dict(products)


def calc_pnl_go_long(data, start_tick):
    """Go long +10 starting at start_tick. Returns PnL."""
    mids = data["mid"]
    asks = data["ask1"]
    n = len(mids)
    if start_tick >= n:
        return 0.0

    # Fill at ask1 prices for first 10 ticks after start
    cash = 0.0
    pos = 0
    for i in range(start_tick, min(start_tick + POSITION_LIMIT, n)):
        cash -= asks[i]
        pos += 1

    # Mark-to-market at last mid
    return cash + pos * mids[-1]


def calc_pnl_go_short(data, start_tick):
    """Go short -10 starting at start_tick. Returns PnL."""
    mids = data["mid"]
    bids = data["bid1"]
    n = len(mids)
    if start_tick >= n:
        return 0.0

    cash = 0.0
    pos = 0
    for i in range(start_tick, min(start_tick + POSITION_LIMIT, n)):
        cash += bids[i]
        pos -= 1

    return cash + pos * mids[-1]


def calc_pnl_slope_triggered(data, window, threshold, direction):
    """
    direction='long': go long when slope > threshold
    direction='short': go short when slope < threshold (threshold negative)
    """
    mids = data["mid"]
    bids = data["bid1"]
    asks = data["ask1"]
    n = len(mids)

    cash = 0.0
    pos = 0
    triggered = False

    for i in range(n):
        if not triggered and i >= window:
            slope = mids[i] - mids[i - window]
            if direction == "short" and slope < threshold:
                triggered = True
            elif direction == "long" and slope > threshold:
                triggered = True

        if triggered and direction == "long" and pos < POSITION_LIMIT:
            cash -= asks[i]
            pos += 1
        elif triggered and direction == "short" and pos > -POSITION_LIMIT:
            cash += bids[i]
            pos -= 1

    return cash + pos * mids[-1]


def main():
    data = load_data()

    # Collect results: product -> list of (strategy_name, pnl)
    results = {}

    for product in sorted(data.keys()):
        d = data[product]
        mids = d["mid"]
        spread = sum(d["ask1"][i] - d["bid1"][i] for i in range(len(mids))) / len(mids)
        drift = mids[-1] - mids[0]
        strategies = []

        # Always-long
        pnl = calc_pnl_go_long(d, start_tick=0)
        strategies.append(("always_long", pnl))

        # Always-short
        pnl = calc_pnl_go_short(d, start_tick=0)
        strategies.append(("always_short", pnl))

        # Delayed long (in ticks, not timestamp units)
        for n_ticks in [50, 100, 200, 300, 500]:
            pnl = calc_pnl_go_long(d, start_tick=n_ticks)
            strategies.append((f"delayed_long_{n_ticks}", pnl))

        # Delayed short
        for n_ticks in [50, 100, 200, 300, 500]:
            pnl = calc_pnl_go_short(d, start_tick=n_ticks)
            strategies.append((f"delayed_short_{n_ticks}", pnl))

        # Slope-triggered short (window in ticks)
        for window in [100, 200, 300]:
            for thresh in [-10, -15, -20, -30]:
                pnl = calc_pnl_slope_triggered(d, window, thresh, "short")
                strategies.append((f"slope_short_w{window}_t{thresh}", pnl))

        # Slope-triggered long
        for window in [100, 200, 300]:
            for thresh in [10, 15, 20, 30]:
                pnl = calc_pnl_slope_triggered(d, window, thresh, "long")
                strategies.append((f"slope_long_w{window}_t{thresh}", pnl))

        results[product] = (drift, spread, strategies)

    # Print results
    print("=" * 100)
    print(f"{'PRODUCT':<40} {'DRIFT':>8} {'SPREAD':>7} {'BEST STRATEGY':<30} {'BEST PnL':>9} {'2nd BEST':<30} {'2nd PnL':>9}")
    print("=" * 100)

    for product in sorted(results.keys()):
        drift, spread, strategies = results[product]
        strategies.sort(key=lambda x: x[1], reverse=True)
        best_name, best_pnl = strategies[0]
        second_name, second_pnl = strategies[1]
        print(f"{product:<40} {drift:>+8.1f} {spread:>7.1f} {best_name:<30} {best_pnl:>+9.0f} {second_name:<30} {second_pnl:>+9.0f}")

    # Detailed breakdown for key products
    key_products = [
        "GALAXY_SOUNDS_BLACK_HOLES",
        "GALAXY_SOUNDS_DARK_MATTER",
        "OXYGEN_SHAKE_MORNING_BREATH",
        "GALAXY_SOUNDS_SOLAR_FLAMES",
        "GALAXY_SOUNDS_SOLAR_WINDS",
        "OXYGEN_SHAKE_CHOCOLATE",
    ]

    for product in key_products:
        if product not in results:
            continue
        drift, spread, strategies = results[product]
        strategies.sort(key=lambda x: x[1], reverse=True)
        print(f"\n--- {product} (drift={drift:+.1f}, spread={spread:.1f}) ---")
        print(f"  {'Strategy':<35} {'PnL':>9}")
        for name, pnl in strategies[:10]:
            print(f"  {name:<35} {pnl:>+9.0f}")
        print("  ...")
        for name, pnl in strategies[-3:]:
            print(f"  {name:<35} {pnl:>+9.0f}")

    # Recommendation table
    print("\n" + "=" * 100)
    print("RECOMMENDATIONS")
    print("=" * 100)
    print(f"{'PRODUCT':<40} {'ACTION':<15} {'STRATEGY':<30} {'PnL':>9} {'SAFE?':>6}")
    print("-" * 100)

    for product in sorted(results.keys()):
        drift, spread, strategies = results[product]
        strategies.sort(key=lambda x: x[1], reverse=True)
        best_name, best_pnl = strategies[0]

        # "Safe" = best PnL > spread * 10 (cost of round-trip * position)
        cost_threshold = spread * POSITION_LIMIT
        safe = best_pnl > cost_threshold

        if best_pnl <= 0:
            action = "SKIP"
        elif safe:
            action = "ENABLE"
        else:
            action = "MARGINAL"

        safe_str = "YES" if safe else "NO"
        print(f"{product:<40} {action:<15} {best_name:<30} {best_pnl:>+9.0f} {safe_str:>6}")


if __name__ == "__main__":
    main()
