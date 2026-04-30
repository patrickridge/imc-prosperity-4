"""H6: Bot-vs-bot counterparty pairing signal on VE and HP.

Tests whether trades between specific bot pairs carry stronger
directional signals than the same bot trading with other counterparties.

Direction convention:
  - Mark 67 is a known smart buyer on VE → his buys are direction +1
  - Mark 49, Mark 22 are known dumb sellers on VE → their sells are direction -1
  - Mark 14 is a known smart bot on HP → his buys are +1
  - Signed impact = direction * (future_mid - current_mid)
"""

import pandas as pd
import numpy as np
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data" / "round4"

HORIZONS = [1, 5, 10, 20]
HORIZON_COLS = [f"impact_{h}" for h in HORIZONS]
SIG_THRESHOLD = 1.65


def load_all_trades():
    frames = []
    for day in range(1, 4):
        path = DATA_DIR / f"trades_round_4_day_{day}.csv"
        df = pd.read_csv(path, sep=";")
        df["day"] = day
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def load_all_prices():
    frames = []
    for day in range(1, 4):
        path = DATA_DIR / f"prices_round_4_day_{day}.csv"
        df = pd.read_csv(path, sep=";")
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def compute_forward_mids(prices, product):
    """Return (day, timestamp) -> mid and forward mid arrays for a product."""
    prod_prices = prices[prices["product"] == product].copy()
    prod_prices = prod_prices.sort_values(["day", "timestamp"])

    day_data = {}
    for day, group in prod_prices.groupby("day"):
        timestamps = group["timestamp"].values
        mids = group["mid_price"].values
        day_data[day] = (timestamps, mids)
    return day_data


def compute_trade_impacts(trades, day_data, direction_fn):
    """Compute signed forward impact for each trade.

    direction_fn(row) -> +1 or -1 based on the buyer/seller identity.
    Returns None to skip the trade.
    """
    results = []
    for _, trade in trades.iterrows():
        day = trade["day"]
        if day not in day_data:
            continue

        timestamps, mids = day_data[day]
        ts = trade["timestamp"]
        idx = np.searchsorted(timestamps, ts)
        if idx >= len(timestamps):
            continue

        mid_at_trade = np.interp(ts, timestamps, mids)
        direction = direction_fn(trade)
        if direction is None:
            continue

        row = {
            "day": day,
            "timestamp": ts,
            "buyer": trade["buyer"],
            "seller": trade["seller"],
            "price": trade["price"],
            "quantity": trade["quantity"],
            "mid_at_trade": mid_at_trade,
            "direction": direction,
        }

        for h in HORIZONS:
            future_idx = idx + h
            if future_idx < len(mids):
                row[f"impact_{h}"] = direction * (mids[future_idx] - mid_at_trade)
            else:
                row[f"impact_{h}"] = np.nan

        results.append(row)

    return pd.DataFrame(results)


def ve_direction(trade):
    """Mark 67 buying = +1. Mark 49/22 selling = -1 (same as 67 buying).

    For other combos, use buyer-side convention if a signal bot is involved.
    """
    buyer = trade["buyer"]
    seller = trade["seller"]

    # Mark 67 buys → follow the buy
    if buyer == "Mark 67":
        return +1
    # Mark 67 sells → follow the sell (role reversal)
    if seller == "Mark 67":
        return -1
    # Mark 49 or 22 sells (no Mark 67 involved) → their sell = price going down
    if seller in ("Mark 49", "Mark 22"):
        return -1
    # Mark 49 or 22 buys (role reversal, no Mark 67)
    if buyer in ("Mark 49", "Mark 22"):
        return +1
    # No signal bot involved → skip
    return None


def hp_direction(trade):
    """Mark 14 buying = +1 (known smart bot on HP). Mark 38 = dumb."""
    buyer = trade["buyer"]
    seller = trade["seller"]

    if buyer == "Mark 14":
        return +1
    if seller == "Mark 14":
        return -1
    if buyer == "Mark 38":
        return +1
    if seller == "Mark 38":
        return -1
    return None


def fmt_impact(vals):
    """Format mean ± significance marker."""
    n = len(vals)
    if n == 0:
        return f"{'n/a':>8}"
    mean = vals.mean()
    if n > 1:
        se = vals.std() / np.sqrt(n)
        marker = "*" if se > 0 and abs(mean / se) >= SIG_THRESHOLD else " "
    else:
        marker = " "
    return f"{mean:>+7.2f}{marker}"


def print_pairing_table(impacts_df, product):
    """Print pairing frequency and impact table."""
    print(f"\n{'='*75}")
    print(f"  {product} — Counterparty Pairing Frequency")
    print(f"{'='*75}")

    pairing_counts = (
        impacts_df.groupby(["buyer", "seller"])
        .agg(count=("quantity", "size"), total_qty=("quantity", "sum"))
        .sort_values("count", ascending=False)
    )
    print(pairing_counts.to_string())


def print_impact_by_pairing(impacts_df, product):
    """Print signed impact grouped by (buyer, seller) pairing."""
    print(f"\n{'='*75}")
    print(f"  {product} — Signed Impact by Counterparty Pairing (* = sig 90%)")
    print(f"{'='*75}")

    pairings = (
        impacts_df.groupby(["buyer", "seller"])
        .size()
        .sort_values(ascending=False)
        .index
    )

    header = f"{'Buyer':>10} → {'Seller':<10} {'Dir':>4} {'N':>5}"
    for h in HORIZONS:
        header += f" {'t+'+str(h):>8}"
    print(header)
    print("-" * len(header))

    for buyer, seller in pairings:
        subset = impacts_df[
            (impacts_df["buyer"] == buyer) & (impacts_df["seller"] == seller)
        ]
        n = len(subset)
        direction = subset["direction"].iloc[0]
        dir_label = "+1" if direction > 0 else "-1"

        line = f"{buyer:>10} → {seller:<10} {dir_label:>4} {n:>5}"
        for h in HORIZONS:
            col = f"impact_{h}"
            vals = subset[col].dropna()
            line += f" {fmt_impact(vals)}"
        print(line)

    # Overall
    print("-" * len(header))
    line = f"{'ALL':>10}   {'':10} {'':>4} {len(impacts_df):>5}"
    for h in HORIZONS:
        vals = impacts_df[f"impact_{h}"].dropna()
        line += f" {fmt_impact(vals)}"
    print(line)


def print_impact_by_pairing_per_day(impacts_df, product, key_pairings):
    """Per-day breakdown for key pairings to check consistency."""
    print(f"\n{'='*75}")
    print(f"  {product} — Per-Day Consistency for Key Pairings")
    print(f"{'='*75}")

    for buyer, seller in key_pairings:
        subset = impacts_df[
            (impacts_df["buyer"] == buyer) & (impacts_df["seller"] == seller)
        ]
        if subset.empty:
            continue

        print(f"\n  {buyer} → {seller}")
        header = f"  {'Day':>4} {'N':>5}"
        for h in HORIZONS:
            header += f" {'t+'+str(h):>8}"
        print(header)
        print("  " + "-" * (len(header) - 2))

        for day in sorted(subset["day"].unique()):
            day_subset = subset[subset["day"] == day]
            line = f"  {day:>4} {len(day_subset):>5}"
            for h in HORIZONS:
                vals = day_subset[f"impact_{h}"].dropna()
                line += f" {fmt_impact(vals)}"
            print(line)


def print_grouped_comparison(impacts_df, product, signal_bot, signal_role):
    """Compare signal bot trading with specific counterparties vs others.

    signal_role: 'buyer' or 'seller' — the column where signal_bot appears.
    """
    other_col = "seller" if signal_role == "buyer" else "buyer"

    bot_trades = impacts_df[impacts_df[signal_role] == signal_bot]
    if bot_trades.empty:
        return

    print(f"\n{'='*75}")
    print(f"  {product} — {signal_bot} as {signal_role.upper()}: impact by counterparty")
    print(f"{'='*75}")

    header = f"{'Counterparty':>15} {'N':>5}"
    for h in HORIZONS:
        header += f" {'t+'+str(h):>8}"
    print(header)
    print("-" * len(header))

    for cp in sorted(bot_trades[other_col].unique()):
        subset = bot_trades[bot_trades[other_col] == cp]
        line = f"{cp:>15} {len(subset):>5}"
        for h in HORIZONS:
            vals = subset[f"impact_{h}"].dropna()
            line += f" {fmt_impact(vals)}"
        print(line)

    print("-" * len(header))
    line = f"{'ALL':>15} {len(bot_trades):>5}"
    for h in HORIZONS:
        vals = bot_trades[f"impact_{h}"].dropna()
        line += f" {fmt_impact(vals)}"
    print(line)


def print_role_reversal(impacts_df, product, bot, expected_role):
    """Check if a bot ever appears on the opposite side."""
    opposite = "seller" if expected_role == "buyer" else "buyer"
    reversed_trades = impacts_df[impacts_df[opposite] == bot]

    print(f"\n{'='*75}")
    print(f"  {product} — Role Reversal: {bot} as {opposite.upper()}")
    print(f"{'='*75}")

    if reversed_trades.empty:
        print(f"  No trades found where {bot} is {opposite}.")
        return

    print(f"  Found {len(reversed_trades)} trades where {bot} is {opposite}.")
    header = f"  {'Counterparty':>15} {'N':>5}"
    for h in HORIZONS:
        header += f" {'t+'+str(h):>8}"
    print(header)
    print("  " + "-" * 60)

    other_col = expected_role  # the column where the counterparty is
    for cp in sorted(reversed_trades[other_col].unique()):
        subset = reversed_trades[reversed_trades[other_col] == cp]
        line = f"  {cp:>15} {len(subset):>5}"
        for h in HORIZONS:
            vals = subset[f"impact_{h}"].dropna()
            line += f" {fmt_impact(vals)}"
        print(line)


def analyze_ve(trades, prices):
    print("\n" + "#" * 75)
    print("#  VELVETFRUIT_EXTRACT — Counterparty Pairing Analysis")
    print("#" * 75)

    ve_trades = trades[trades["symbol"] == "VELVETFRUIT_EXTRACT"].copy()
    day_data = compute_forward_mids(prices, "VELVETFRUIT_EXTRACT")

    # Only keep trades involving at least one signal bot
    signal_bots = {"Mark 67", "Mark 49", "Mark 22"}
    ve_signal = ve_trades[
        ve_trades["buyer"].isin(signal_bots) | ve_trades["seller"].isin(signal_bots)
    ]

    impacts = compute_trade_impacts(ve_signal, day_data, ve_direction)

    print_pairing_table(impacts, "VE")
    print_impact_by_pairing(impacts, "VE")

    # Grouped comparison: Mark 67 buying from different sellers
    print_grouped_comparison(impacts, "VE", "Mark 67", "buyer")

    # Role reversals
    print_role_reversal(impacts, "VE", "Mark 67", "buyer")
    print_role_reversal(impacts, "VE", "Mark 49", "seller")
    print_role_reversal(impacts, "VE", "Mark 22", "seller")

    # Per-day consistency for key pairings
    key_pairings = [
        ("Mark 67", "Mark 49"),
        ("Mark 67", "Mark 22"),
        ("Mark 67", "Mark 55"),
    ]
    print_impact_by_pairing_per_day(impacts, "VE", key_pairings)


def analyze_hp(trades, prices):
    print("\n\n" + "#" * 75)
    print("#  HYDROGEL_PACK — Counterparty Pairing Analysis")
    print("#" * 75)

    hp_trades = trades[trades["symbol"] == "HYDROGEL_PACK"].copy()
    day_data = compute_forward_mids(prices, "HYDROGEL_PACK")

    signal_bots = {"Mark 14", "Mark 38"}
    hp_signal = hp_trades[
        hp_trades["buyer"].isin(signal_bots) | hp_trades["seller"].isin(signal_bots)
    ]

    impacts = compute_trade_impacts(hp_signal, day_data, hp_direction)

    print_pairing_table(impacts, "HP")
    print_impact_by_pairing(impacts, "HP")

    # Mark 14 buying from different sellers
    print_grouped_comparison(impacts, "HP", "Mark 14", "buyer")
    # Mark 14 selling to different buyers
    print_grouped_comparison(impacts, "HP", "Mark 14", "seller")

    # Per-day consistency
    key_pairings = [
        ("Mark 14", "Mark 38"),
        ("Mark 38", "Mark 14"),
        ("Mark 22", "Mark 38"),
    ]
    print_impact_by_pairing_per_day(impacts, "HP", key_pairings)


def print_actionability_summary(ve_impacts, hp_impacts):
    """Final verdict: are any pairings above the spread threshold?"""
    VE_HALF_SPREAD = 3.0  # ~5-6 tick spread on VE
    HP_HALF_SPREAD = 8.0  # ~16 tick spread on HP

    print("\n\n" + "#" * 75)
    print("#  ACTIONABILITY SUMMARY")
    print("#" * 75)
    print(f"\n  VE half-spread ~ {VE_HALF_SPREAD:.0f} ticks, HP half-spread ~ {HP_HALF_SPREAD:.0f} ticks")
    print("  A taker strategy needs impact > half-spread to be profitable.\n")

    for label, impacts, threshold in [
        ("VE", ve_impacts, VE_HALF_SPREAD),
        ("HP", hp_impacts, HP_HALF_SPREAD),
    ]:
        pairings = impacts.groupby(["buyer", "seller"])
        print(f"  {label} pairings exceeding half-spread at t+20:")
        found = False
        for (buyer, seller), group in pairings:
            vals = group["impact_20"].dropna()
            if len(vals) < 5:
                continue
            mean = vals.mean()
            if mean > threshold:
                se = vals.std() / np.sqrt(len(vals))
                print(f"    {buyer} → {seller}: {mean:+.2f} (N={len(vals)}, SE={se:.2f})")
                found = True
        if not found:
            print("    None found with N >= 5.")
        print()


def main():
    trades = load_all_trades()
    prices = load_all_prices()

    # VE analysis
    ve_trades = trades[trades["symbol"] == "VELVETFRUIT_EXTRACT"].copy()
    ve_day_data = compute_forward_mids(prices, "VELVETFRUIT_EXTRACT")
    signal_bots_ve = {"Mark 67", "Mark 49", "Mark 22"}
    ve_signal = ve_trades[
        ve_trades["buyer"].isin(signal_bots_ve) | ve_trades["seller"].isin(signal_bots_ve)
    ]
    ve_impacts = compute_trade_impacts(ve_signal, ve_day_data, ve_direction)

    analyze_ve(trades, prices)

    # HP analysis
    hp_trades = trades[trades["symbol"] == "HYDROGEL_PACK"].copy()
    hp_day_data = compute_forward_mids(prices, "HYDROGEL_PACK")
    signal_bots_hp = {"Mark 14", "Mark 38"}
    hp_signal = hp_trades[
        hp_trades["buyer"].isin(signal_bots_hp) | hp_trades["seller"].isin(signal_bots_hp)
    ]
    hp_impacts = compute_trade_impacts(hp_signal, hp_day_data, hp_direction)

    analyze_hp(trades, prices)

    print_actionability_summary(ve_impacts, hp_impacts)


if __name__ == "__main__":
    main()
