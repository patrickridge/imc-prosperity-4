"""
VEV Options Bot Pattern Analysis
Identify which bots are smart vs dumb counterparties on VEV call options.
"""

import pandas as pd
import numpy as np
from pathlib import Path

DATA_DIR = Path("data/round4")
DAYS = [1, 2, 3]
VEV_SYMBOLS = [
    "VEV_4000", "VEV_5000", "VEV_5100", "VEV_5200",
    "VEV_5300", "VEV_5400", "VEV_5500",
]
IMPACT_HORIZONS = [1, 5, 10, 20]  # ticks forward (each tick = 100 timestamp units)
TICK_SIZE = 100


def load_day(day):
    prices = pd.read_csv(DATA_DIR / f"prices_round_4_day_{day}.csv", sep=";")
    trades = pd.read_csv(DATA_DIR / f"trades_round_4_day_{day}.csv", sep=";")
    prices = prices[prices["product"].isin(VEV_SYMBOLS)].copy()
    trades = trades[trades["symbol"].isin(VEV_SYMBOLS)].copy()
    return prices, trades


def build_mid_lookup(prices):
    """Dict of (symbol, timestamp) -> mid_price for fast lookup."""
    lookup = {}
    for _, row in prices.iterrows():
        lookup[(row["product"], row["timestamp"])] = row["mid_price"]
    return lookup


def compute_edge_and_impact(trades, mid_lookup, max_timestamp):
    """For each trade, compute edge vs mid and future price impact."""
    records = []
    for _, trade in trades.iterrows():
        sym = trade["symbol"]
        ts = trade["timestamp"]
        price = trade["price"]
        qty = trade["quantity"]
        buyer = trade["buyer"]
        seller = trade["seller"]

        mid_now = mid_lookup.get((sym, ts))
        if mid_now is None:
            continue

        # Future mids at each horizon
        future_mids = {}
        for h in IMPACT_HORIZONS:
            future_ts = ts + h * TICK_SIZE
            if future_ts <= max_timestamp:
                future_mids[h] = mid_lookup.get((sym, future_ts))

        # Buyer record: good deal = bought below mid
        records.append({
            "bot": buyer,
            "side": "buy",
            "symbol": sym,
            "timestamp": ts,
            "price": price,
            "quantity": qty,
            "mid_now": mid_now,
            "edge": mid_now - price,  # positive = bought cheap
            **{f"mid_t{h}": future_mids.get(h) for h in IMPACT_HORIZONS},
        })

        # Seller record: good deal = sold above mid
        records.append({
            "bot": seller,
            "side": "sell",
            "symbol": sym,
            "timestamp": ts,
            "price": price,
            "quantity": qty,
            "mid_now": mid_now,
            "edge": price - mid_now,  # positive = sold rich
            **{f"mid_t{h}": future_mids.get(h) for h in IMPACT_HORIZONS},
        })

    df = pd.DataFrame(records)

    # Signed impact: did the mid move in the bot's favor after trading?
    for h in IMPACT_HORIZONS:
        col = f"mid_t{h}"
        # Buyer wants price to go UP after buying
        # Seller wants price to go DOWN after selling
        df[f"impact_{h}"] = np.where(
            df["side"] == "buy",
            df[col] - df["mid_now"],
            df["mid_now"] - df[col],
        )

    return df


def print_section(title):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")


def main():
    all_records = []

    for day in DAYS:
        prices, trades = load_day(day)
        mid_lookup = build_mid_lookup(prices)
        max_ts = prices["timestamp"].max()
        day_records = compute_edge_and_impact(trades, mid_lookup, max_ts)
        day_records["day"] = day
        all_records.append(day_records)

    df = pd.concat(all_records, ignore_index=True)

    print_section("1. WHO TRADES VEV OPTIONS?")
    for sym in VEV_SYMBOLS:
        sym_df = df[df["symbol"] == sym]
        if sym_df.empty:
            continue
        print(f"\n  {sym}:")
        summary = (
            sym_df.groupby(["bot", "side"])
            .agg(trades=("quantity", "count"), total_qty=("quantity", "sum"))
            .reset_index()
            .sort_values(["bot", "side"])
        )
        for _, row in summary.iterrows():
            print(f"    {row['bot']:12s} {row['side']:4s}  {row['trades']:4d} trades  qty={row['total_qty']:6d}")

    print_section("2. BOT EDGE vs MID (positive = bot got a good deal)")
    edge_summary = (
        df.groupby(["bot", "symbol", "side"])
        .agg(
            n=("edge", "count"),
            total_qty=("quantity", "sum"),
            avg_edge=("edge", "mean"),
            qty_weighted_edge=("edge", lambda x: np.average(x, weights=df.loc[x.index, "quantity"])),
        )
        .reset_index()
        .sort_values(["symbol", "bot", "side"])
    )
    print(f"\n  {'Bot':12s} {'Symbol':10s} {'Side':4s} {'N':>5s} {'Qty':>6s} {'AvgEdge':>8s} {'QtyWtEdge':>10s}")
    print(f"  {'-'*12} {'-'*10} {'-'*4} {'-'*5} {'-'*6} {'-'*8} {'-'*10}")
    for _, r in edge_summary.iterrows():
        print(f"  {r['bot']:12s} {r['symbol']:10s} {r['side']:4s} {r['n']:5d} {r['total_qty']:6d} {r['avg_edge']:8.2f} {r['qty_weighted_edge']:10.2f}")

    print_section("3. DIRECTIONAL IMPACT (positive = bot traded in right direction)")
    impact_cols = [f"impact_{h}" for h in IMPACT_HORIZONS]

    # Aggregate per bot across all symbols
    print("\n  --- Aggregate across all VEV symbols ---")
    agg_dict = {"edge": [("n", "count")]}
    for col in impact_cols:
        agg_dict[col] = [("mean", "mean")]

    bot_impact = (
        df.groupby(["bot", "side"])
        .agg(
            n=("edge", "count"),
            avg_edge=("edge", "mean"),
            **{f"avg_imp_{h}": (f"impact_{h}", "mean") for h in IMPACT_HORIZONS},
        )
        .reset_index()
        .sort_values(["bot", "side"])
    )

    header = f"  {'Bot':12s} {'Side':4s} {'N':>5s} {'Edge':>7s}"
    for h in IMPACT_HORIZONS:
        header += f" {'t+'+str(h):>7s}"
    print(header)
    print(f"  {'-'*60}")
    for _, r in bot_impact.iterrows():
        line = f"  {r['bot']:12s} {r['side']:4s} {r['n']:5.0f} {r['avg_edge']:7.2f}"
        for h in IMPACT_HORIZONS:
            line += f" {r[f'avg_imp_{h}']:7.2f}"
        print(line)

    # Per bot per symbol
    print("\n  --- Per bot, per symbol ---")
    bot_sym_impact = (
        df.groupby(["bot", "symbol", "side"])
        .agg(
            n=("edge", "count"),
            avg_edge=("edge", "mean"),
            **{f"avg_imp_{h}": (f"impact_{h}", "mean") for h in IMPACT_HORIZONS},
        )
        .reset_index()
        .sort_values(["symbol", "bot", "side"])
    )

    header = f"  {'Bot':12s} {'Symbol':10s} {'Side':4s} {'N':>4s} {'Edge':>7s}"
    for h in IMPACT_HORIZONS:
        header += f" {'t+'+str(h):>7s}"
    print(header)
    print(f"  {'-'*72}")
    for _, r in bot_sym_impact.iterrows():
        line = f"  {r['bot']:12s} {r['symbol']:10s} {r['side']:4s} {r['n']:4.0f} {r['avg_edge']:7.2f}"
        for h in IMPACT_HORIZONS:
            line += f" {r[f'avg_imp_{h}']:7.2f}"
        print(line)

    print_section("4. CONSISTENCY ACROSS DAYS")
    day_impact = (
        df.groupby(["bot", "side", "day"])
        .agg(
            n=("edge", "count"),
            avg_edge=("edge", "mean"),
            **{f"avg_imp_{h}": (f"impact_{h}", "mean") for h in IMPACT_HORIZONS},
        )
        .reset_index()
        .sort_values(["bot", "side", "day"])
    )

    header = f"  {'Bot':12s} {'Side':4s} {'Day':>3s} {'N':>5s} {'Edge':>7s}"
    for h in IMPACT_HORIZONS:
        header += f" {'t+'+str(h):>7s}"
    print(header)
    print(f"  {'-'*60}")
    for _, r in day_impact.iterrows():
        line = f"  {r['bot']:12s} {r['side']:4s} {r['day']:3.0f} {r['n']:5.0f} {r['avg_edge']:7.2f}"
        for h in IMPACT_HORIZONS:
            line += f" {r[f'avg_imp_{h}']:7.2f}"
        print(line)

    print_section("5. KEY FINDING: EXPLOITABLE BOTS")

    # Flag bots with consistent sign of t+20 impact across all 3 days
    pivot = day_impact.pivot_table(
        index=["bot", "side"],
        columns="day",
        values="avg_imp_20",
    )
    print("\n  t+20 impact sign consistency (+ = smart, - = dumb):")
    print(f"  {'Bot':12s} {'Side':4s}  Day1     Day2     Day3     Consistent?")
    print(f"  {'-'*60}")
    for (bot, side), row in pivot.iterrows():
        vals = [row.get(d) for d in DAYS]
        signs = [np.sign(v) if pd.notna(v) else 0 for v in vals]
        all_pos = all(s > 0 for s in signs if s != 0)
        all_neg = all(s < 0 for s in signs if s != 0)
        active_days = sum(1 for s in signs if s != 0)
        if active_days < 2:
            tag = "insufficient data"
        elif all_pos:
            tag = "SMART (consistently right)"
        elif all_neg:
            tag = "DUMB (consistently wrong)"
        else:
            tag = "mixed"
        val_strs = [f"{v:8.2f}" if pd.notna(v) else "     N/A" for v in vals]
        print(f"  {bot:12s} {side:4s}  {''.join(val_strs)}  {tag}")

    # Also check edge consistency
    print("\n  Edge consistency (+ = bot gets good fills, - = bot gets adverse fills):")
    edge_pivot = day_impact.pivot_table(
        index=["bot", "side"],
        columns="day",
        values="avg_edge",
    )
    print(f"  {'Bot':12s} {'Side':4s}  Day1     Day2     Day3     Consistent?")
    print(f"  {'-'*60}")
    for (bot, side), row in edge_pivot.iterrows():
        vals = [row.get(d) for d in DAYS]
        signs = [np.sign(v) if pd.notna(v) else 0 for v in vals]
        all_pos = all(s > 0 for s in signs if s != 0)
        all_neg = all(s < 0 for s in signs if s != 0)
        active_days = sum(1 for s in signs if s != 0)
        if active_days < 2:
            tag = "insufficient data"
        elif all_pos:
            tag = "GOOD fills consistently"
        elif all_neg:
            tag = "BAD fills consistently"
        else:
            tag = "mixed"
        val_strs = [f"{v:8.2f}" if pd.notna(v) else "     N/A" for v in vals]
        print(f"  {bot:12s} {side:4s}  {''.join(val_strs)}  {tag}")


if __name__ == "__main__":
    main()
