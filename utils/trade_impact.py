"""
Trade impact analysis — detects informed trader patterns.

Rounds 1-3 (anonymous):  groups by quantity and price location.
Round 4+   (named bots): also groups by bot name.

Usage:
  python utils/trade_impact.py <day> [round]
  python utils/trade_impact.py 1 4          # day 1, round 4 (bot mode)
  python utils/trade_impact.py -1           # day -1, round 0 (anonymous)
"""

import sys
import pandas as pd
import numpy as np
from data_finder import find_data_files

HORIZONS = [1, 5, 10, 20]
LOCATION_BINS = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
LOCATION_LABELS = ["0.0-0.2", "0.2-0.4", "0.4-0.6", "0.6-0.8", "0.8-1.0"]
SIG_THRESHOLD = 1.65


# ── Core impact computation ──

def compute_impacts(product_prices, product_trades):
    timestamps = product_prices["timestamp"].values
    mids = product_prices["mid_price"].values

    results = []
    for _, trade in product_trades.iterrows():
        ts = trade["timestamp"]
        idx = np.searchsorted(timestamps, ts)
        if idx >= len(timestamps):
            continue

        mid_at_trade = np.interp(ts, timestamps, mids)
        side = 1 if trade["price"] >= mid_at_trade else -1

        row = {
            "timestamp": ts,
            "side": side,
            "quantity": trade["quantity"],
            "price_location": _price_location(mids, idx, mid_at_trade),
        }

        if "buyer" in trade.index:
            row["buyer"] = trade["buyer"]
            row["seller"] = trade["seller"]

        for h in HORIZONS:
            future_idx = idx + h
            if future_idx < len(mids):
                row[f"impact_{h}"] = side * (mids[future_idx] - mid_at_trade)
            else:
                row[f"impact_{h}"] = np.nan

        results.append(row)

    return pd.DataFrame(results)


def _price_location(mids, idx, mid_at_trade):
    running_min = mids[:idx + 1].min()
    running_max = mids[:idx + 1].max()
    running_range = running_max - running_min
    if running_range > 0:
        return (mid_at_trade - running_min) / running_range
    return 0.5


# ── Bot-level impact (R4+) ──

def compute_bot_impacts(impacts):
    """Unpivot trades into per-bot rows with signed forward returns.

    Buyer gets raw impact (positive = price went up after buy = smart).
    Seller gets negated impact (positive = price went down after sell = smart).
    """
    if "buyer" not in impacts.columns:
        return pd.DataFrame()

    impact_cols = [f"impact_{h}" for h in HORIZONS]
    common = ["timestamp", "quantity", "price_location"]

    buy_rows = impacts[common + impact_cols + ["buyer"]].copy()
    buy_rows = buy_rows.rename(columns={"buyer": "bot"})
    buy_rows["bot_side"] = "BUY"

    sell_rows = impacts[common + impact_cols + ["seller"]].copy()
    sell_rows = sell_rows.rename(columns={"seller": "bot"})
    sell_rows["bot_side"] = "SELL"
    for col in impact_cols:
        sell_rows[col] = -sell_rows[col]

    return pd.concat([buy_rows, sell_rows], ignore_index=True)


# ── Printing ──

def _fmt_impact(mean_val, se_val, n):
    if n < 2 or se_val == 0:
        marker = " "
    elif abs(mean_val / se_val) >= SIG_THRESHOLD:
        marker = "*"
    else:
        marker = " "
    return f"{mean_val:>+7.2f}{marker}"


def _print_group(label, subset, label_width=10):
    n = len(subset)
    print(f"{label:>{label_width}} {n:>5}", end="")
    for h in HORIZONS:
        col = f"impact_{h}"
        vals = subset[col].dropna()
        if len(vals) == 0:
            print(f" {'n/a':>8}", end="")
            continue
        mean_val = vals.mean()
        se_val = vals.std() / np.sqrt(len(vals)) if len(vals) > 1 else 0
        print(f" {_fmt_impact(mean_val, se_val, len(vals))}", end="")
    print()


def _print_header():
    print(f"{'':>10} {'Count':>5}", end="")
    for h in HORIZONS:
        print(f" {'t+'+str(h):>8}", end="")
    print()
    print("-" * 55)


def print_impact_by_bot(bot_impacts, product):
    if bot_impacts.empty:
        return

    print(f"\n{'='*60}")
    print(f"  {product} — Impact by Bot (* = sig at 90%)")
    print(f"{'='*60}")

    for bot in sorted(bot_impacts["bot"].unique()):
        bot_data = bot_impacts[bot_impacts["bot"] == bot]
        print(f"\n  {bot}")
        _print_header()
        for bot_side in ["BUY", "SELL"]:
            subset = bot_data[bot_data["bot_side"] == bot_side]
            if subset.empty:
                continue
            _print_group(bot_side, subset)
        _print_group("NET", bot_data)


def print_impact_by_quantity(impacts, product):
    print(f"\n{'='*60}")
    print(f"  {product} — Impact by Trade Size")
    print(f"{'='*60}")
    _print_header()

    for qty in sorted(impacts["quantity"].unique()):
        subset = impacts[impacts["quantity"] == qty]
        _print_group(str(int(qty)), subset)

    print("-" * 55)
    _print_group("ALL", impacts)


def print_impact_by_location(impacts, product):
    print(f"\n{'='*60}")
    print(f"  {product} — Impact by Price Location")
    print(f"  (0.0 = running low, 1.0 = running high)")
    print(f"{'='*60}")

    impacts = impacts.copy()
    impacts["loc_bin"] = pd.cut(
        impacts["price_location"], bins=LOCATION_BINS,
        labels=LOCATION_LABELS, include_lowest=True,
    )

    _print_header()
    for label in LOCATION_LABELS:
        subset = impacts[impacts["loc_bin"] == label]
        if len(subset) == 0:
            continue
        _print_group(label, subset)


def print_bot_summary(bot_impacts, product):
    """One-line-per-bot scorecard: avg signed impact at t+20."""
    if bot_impacts.empty:
        return

    print(f"\n{'='*60}")
    print(f"  {product} — Bot Scorecard (t+20 signed impact)")
    print(f"  Positive = trades predict future direction (smart)")
    print(f"  Negative = trades predict wrong direction (exploitable)")
    print(f"{'='*60}")
    print(f"{'Bot':>10} {'Trades':>7} {'Avg t+20':>9} {'Verdict':>12}")
    print("-" * 42)

    grouped = bot_impacts.groupby("bot")["impact_20"].agg(["mean", "count"])
    grouped = grouped.sort_values("mean", ascending=False)

    for bot, row in grouped.iterrows():
        avg = row["mean"]
        count = int(row["count"])
        if avg > 0.5:
            verdict = "SMART"
        elif avg < -0.5:
            verdict = "EXPLOITABLE"
        else:
            verdict = "NEUTRAL"
        print(f"{bot:>10} {count:>7} {avg:>+9.2f} {verdict:>12}")


# ── Main ──

def main():
    if len(sys.argv) < 2:
        print("Usage: python utils/trade_impact.py <day> [round]")
        print("Example: python utils/trade_impact.py 1 4")
        sys.exit(1)

    day = sys.argv[1]
    round_num = sys.argv[2] if len(sys.argv) > 2 else "0"
    prices_path, trades_path = find_data_files(day, round_num)

    prices = pd.read_csv(prices_path, sep=";")
    trades = pd.read_csv(trades_path, sep=";")
    day_label = str(prices["day"].iloc[0])
    has_bots = "buyer" in trades.columns

    print(f"Trade Impact Analysis — Day {day_label}")
    if has_bots:
        print("(Bot names detected — showing per-bot analysis)")

    for product in prices["product"].unique():
        product_prices = prices[prices["product"] == product].sort_values("timestamp")
        product_trades = trades[trades["symbol"] == product].sort_values("timestamp")
        if product_trades.empty:
            continue

        impacts = compute_impacts(product_prices, product_trades)

        if has_bots:
            bot_impacts = compute_bot_impacts(impacts)
            print_bot_summary(bot_impacts, product)
            print_impact_by_bot(bot_impacts, product)
        else:
            print_impact_by_quantity(impacts, product)
            print_impact_by_location(impacts, product)


if __name__ == "__main__":
    main()
