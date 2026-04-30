"""H7: Does bot trade SIZE predict stronger directional signal on VE?

Tests whether Mark 67/49/22 trade in varying sizes and whether larger
trades carry proportionally bigger impact.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from scipy import stats

DATA_DIR = Path(__file__).parent.parent / "data" / "round4"
PRODUCT = "VELVETFRUIT_EXTRACT"
SIGNAL_BOTS = ["Mark 67", "Mark 49", "Mark 22"]
HORIZONS = [1, 5, 10, 20]
DAYS = [1, 2, 3]


def load_prices():
    frames = []
    for day in DAYS:
        path = DATA_DIR / f"prices_round_4_day_{day}.csv"
        df = pd.read_csv(path, sep=";")
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def load_trades():
    frames = []
    for day in DAYS:
        path = DATA_DIR / f"trades_round_4_day_{day}.csv"
        df = pd.read_csv(path, sep=";")
        df["day"] = day
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def compute_bot_signed_impacts(prices, trades):
    """For each signal bot trade on VE, compute signed impact at all horizons.

    Mark 67 = buyer -> direction = +1
    Mark 49, Mark 22 = seller -> direction = -1
    Signed impact = direction * (future_mid - current_mid)

    Returns one row per bot trade with quantity and signed impacts.
    """
    ve_prices = prices[prices["product"] == PRODUCT].copy()
    ve_trades = trades[trades["symbol"] == PRODUCT].copy()

    results = []
    for day in DAYS:
        day_prices = ve_prices[ve_prices["day"] == day].sort_values("timestamp")
        day_trades = ve_trades[ve_trades["day"] == day].sort_values("timestamp")

        timestamps = day_prices["timestamp"].values
        mids = day_prices["mid_price"].values

        for _, trade in day_trades.iterrows():
            ts = trade["timestamp"]
            idx = np.searchsorted(timestamps, ts)
            if idx >= len(timestamps):
                continue

            mid_now = mids[idx]

            # One trade can involve two signal bots (e.g. Mark 67 buys from Mark 49)
            for bot, direction in _all_signal_bots(trade):
                row = {
                    "day": day,
                    "timestamp": ts,
                    "bot": bot,
                    "direction": direction,
                    "quantity": trade["quantity"],
                }

                for h in HORIZONS:
                    future_idx = idx + h
                    if future_idx < len(mids):
                        row[f"impact_{h}"] = direction * (mids[future_idx] - mid_now)
                    else:
                        row[f"impact_{h}"] = np.nan

                results.append(row)

    return pd.DataFrame(results)


def _all_signal_bots(trade):
    """Yield (bot_name, direction) for every signal bot involved in this trade."""
    if trade["buyer"] == "Mark 67":
        yield "Mark 67", +1
    if trade["seller"] == "Mark 49":
        yield "Mark 49", -1
    if trade["seller"] == "Mark 22":
        yield "Mark 22", -1


def print_size_distribution(df):
    print("=" * 70)
    print("  1. TRADE SIZE DISTRIBUTION PER BOT")
    print("=" * 70)

    for bot in SIGNAL_BOTS:
        bot_df = df[df["bot"] == bot]
        qtys = bot_df["quantity"]
        print(f"\n  {bot} — {len(bot_df)} trades total")
        print(f"    min={qtys.min()}, Q1={qtys.quantile(0.25):.0f}, "
              f"median={qtys.quantile(0.5):.0f}, Q3={qtys.quantile(0.75):.0f}, "
              f"max={qtys.max()}")

        value_counts = qtys.value_counts().sort_index()
        print(f"    Size frequency:")
        for size, count in value_counts.items():
            pct = count / len(bot_df) * 100
            bar = "#" * int(pct / 2)
            print(f"      qty={int(size):>3}: {count:>4} ({pct:5.1f}%) {bar}")

        # Per-day breakdown
        for day in DAYS:
            day_qtys = bot_df[bot_df["day"] == day]["quantity"]
            if len(day_qtys) == 0:
                continue
            print(f"    Day {day}: n={len(day_qtys)}, "
                  f"mean={day_qtys.mean():.1f}, sizes={sorted(day_qtys.unique())}")


def print_impact_by_quartile(df):
    print("\n" + "=" * 70)
    print("  2. SIGNED IMPACT BY TRADE SIZE QUARTILE")
    print("=" * 70)

    for bot in SIGNAL_BOTS:
        bot_df = df[df["bot"] == bot].copy()
        unique_sizes = sorted(bot_df["quantity"].unique())

        if len(unique_sizes) <= 1:
            print(f"\n  {bot}: only one trade size ({unique_sizes}), skipping quartile split")
            _print_overall_impact(bot_df, bot)
            continue

        # Use quartile bins based on quantity
        try:
            bot_df["size_q"] = pd.qcut(bot_df["quantity"], q=4, labels=["Q1", "Q2", "Q3", "Q4"])
        except ValueError:
            # Too few unique values for 4 bins — use unique values as bins
            bot_df["size_q"] = pd.cut(
                bot_df["quantity"],
                bins=max(2, min(4, len(unique_sizes))),
                labels=False,
            )
            bot_df["size_q"] = bot_df["size_q"].map(lambda x: f"Bin{int(x)}" if pd.notna(x) else "?")

        print(f"\n  {bot}")
        print(f"  {'Quartile':>10} {'N':>5} {'Avg Qty':>8}", end="")
        for h in HORIZONS:
            print(f" {'t+'+str(h)+' mean':>10} {'t-stat':>7}", end="")
        print()
        print("  " + "-" * 85)

        for q_label in sorted(bot_df["size_q"].unique()):
            subset = bot_df[bot_df["size_q"] == q_label]
            n = len(subset)
            avg_qty = subset["quantity"].mean()
            print(f"  {str(q_label):>10} {n:>5} {avg_qty:>8.1f}", end="")
            for h in HORIZONS:
                vals = subset[f"impact_{h}"].dropna()
                if len(vals) < 2:
                    print(f" {'n/a':>10} {'':>7}", end="")
                    continue
                mean = vals.mean()
                se = vals.std() / np.sqrt(len(vals))
                t = mean / se if se > 0 else 0
                print(f" {mean:>+10.2f} {t:>+7.2f}", end="")
            print()

        # Per-day quartile breakdown
        _print_quartile_per_day(bot_df, bot)


def _print_overall_impact(df, bot):
    print(f"  {'ALL':>10} {len(df):>5} {df['quantity'].mean():>8.1f}", end="")
    for h in HORIZONS:
        vals = df[f"impact_{h}"].dropna()
        if len(vals) < 2:
            print(f" {'n/a':>10} {'':>7}", end="")
            continue
        mean = vals.mean()
        se = vals.std() / np.sqrt(len(vals))
        t = mean / se if se > 0 else 0
        print(f" {mean:>+10.2f} {t:>+7.2f}", end="")
    print()


def _print_quartile_per_day(bot_df, bot):
    """Check per-day consistency of the quartile pattern."""
    for day in DAYS:
        day_df = bot_df[bot_df["day"] == day]
        if len(day_df) < 8:
            continue
        print(f"\n    Day {day}:")
        for q_label in sorted(day_df["size_q"].unique()):
            subset = day_df[day_df["size_q"] == q_label]
            n = len(subset)
            avg_qty = subset["quantity"].mean()
            vals_1 = subset["impact_1"].dropna()
            vals_20 = subset["impact_20"].dropna()
            mean_1 = vals_1.mean() if len(vals_1) > 0 else float("nan")
            mean_20 = vals_20.mean() if len(vals_20) > 0 else float("nan")
            print(f"      {str(q_label):>6} n={n:>3}, avg_qty={avg_qty:>5.1f}, "
                  f"t+1={mean_1:>+6.2f}, t+20={mean_20:>+6.2f}")


def print_quantity_weighted_signal(df):
    print("\n" + "=" * 70)
    print("  3. QUANTITY-WEIGHTED vs UNWEIGHTED SIGNAL (correlation)")
    print("=" * 70)

    for bot in SIGNAL_BOTS:
        bot_df = df[df["bot"] == bot].copy()
        print(f"\n  {bot}")
        print(f"  {'Horizon':>10} {'R(dir, dP)':>12} {'R(qty*dir, dP)':>16} {'Improvement':>12}")
        print("  " + "-" * 55)

        for h in HORIZONS:
            col = f"impact_{h}"
            valid = bot_df[col].dropna()
            if len(valid) < 5:
                continue

            # Impact is already signed (direction * price change)
            # Unweighted: corr(direction, future_change) = corr(sign, raw_change)
            # But since direction is constant for each bot, we just compare means
            # Instead: corr(1, impact) vs corr(qty, impact)
            # More meaningful: does qty predict MAGNITUDE of signed impact?
            future_change = valid.values  # already direction * delta_mid
            qty_vals = bot_df.loc[valid.index, "quantity"].values

            # Unweighted: just direction (constant +1 or -1), so R = correlation of constant with impact = undefined
            # Better framing: regress impact on quantity
            # R² of impact ~ qty  vs  impact ~ constant
            r_dir = np.nan  # direction is constant per bot, corr undefined
            r_qty, p_qty = stats.pearsonr(qty_vals, future_change) if len(qty_vals) > 2 else (np.nan, np.nan)

            # Also do OLS: impact = a + b*qty
            slope, intercept, r_val, p_val, se = stats.linregress(qty_vals, future_change)

            print(f"  {'t+'+str(h):>10} {'(constant)':>12} {r_qty:>+16.4f} "
                  f"slope={slope:>+.4f}, p={p_val:.3f}")


def print_threshold_analysis(df):
    print("\n" + "=" * 70)
    print("  4. THRESHOLD ANALYSIS: at what size does signal exceed spread?")
    print("=" * 70)
    print("  Spread = 5 ticks. Need signal > 3 ticks to be interesting,")
    print("  > 5 ticks to profit as taker.")

    THRESHOLDS = [3, 4, 5]
    HORIZON = 20  # use t+20 as the "final" impact

    for bot in SIGNAL_BOTS:
        bot_df = df[df["bot"] == bot].copy()
        unique_sizes = sorted(bot_df["quantity"].unique())
        print(f"\n  {bot} — sizes: {unique_sizes}")

        # For each size, compute mean impact at t+20
        print(f"  {'Size':>6} {'N':>5} {'Mean t+20':>10} {'Median t+20':>12} {'% > 3':>7} {'% > 5':>7}")
        print("  " + "-" * 55)

        for size in unique_sizes:
            subset = bot_df[bot_df["quantity"] == size]
            vals = subset[f"impact_{HORIZON}"].dropna()
            if len(vals) == 0:
                continue
            mean = vals.mean()
            median = vals.median()
            pct_gt3 = (vals > 3).mean() * 100
            pct_gt5 = (vals > 5).mean() * 100
            print(f"  {size:>6} {len(vals):>5} {mean:>+10.2f} {median:>+12.2f} "
                  f"{pct_gt3:>6.1f}% {pct_gt5:>6.1f}%")

        # Cumulative: trades above each size threshold
        print(f"\n  Conditional mean impact for trades with qty >= threshold:")
        for thresh in sorted(unique_sizes):
            subset = bot_df[bot_df["quantity"] >= thresh]
            vals = subset[f"impact_{HORIZON}"].dropna()
            if len(vals) < 3:
                continue
            mean = vals.mean()
            se = vals.std() / np.sqrt(len(vals))
            t_stat = mean / se if se > 0 else 0
            per_day = []
            for day in DAYS:
                day_vals = subset[subset["day"] == day][f"impact_{HORIZON}"].dropna()
                per_day.append(f"d{day}={day_vals.mean():+.1f}" if len(day_vals) > 0 else f"d{day}=n/a")
            print(f"    qty>={thresh:>3}: n={len(vals):>4}, mean={mean:>+.2f}, "
                  f"t={t_stat:>+.2f}, {', '.join(per_day)}")

        # How many events per day would exceed spread?
        print(f"\n  Events per day where impact_20 > 5 ticks:")
        for day in DAYS:
            day_vals = bot_df[(bot_df["day"] == day)][f"impact_{HORIZON}"].dropna()
            n_gt5 = (day_vals > 5).sum()
            print(f"    Day {day}: {n_gt5} of {len(day_vals)} trades ({n_gt5/len(day_vals)*100:.1f}%)")


def print_combined_threshold(df):
    print("\n" + "=" * 70)
    print("  5. COMBINED: ALL SIGNAL BOTS — large trades only")
    print("=" * 70)

    # What if we only react to the LARGEST trades from each bot?
    for bot in SIGNAL_BOTS:
        bot_df = df[df["bot"] == bot]
        q75 = bot_df["quantity"].quantile(0.75)
        large = bot_df[bot_df["quantity"] >= q75]
        small = bot_df[bot_df["quantity"] < q75]

        vals_large = large["impact_20"].dropna()
        vals_small = small["impact_20"].dropna()

        if len(vals_large) < 2 or len(vals_small) < 2:
            continue

        mean_l = vals_large.mean()
        mean_s = vals_small.mean()
        # Welch's t-test: large vs small impact
        t, p = stats.ttest_ind(vals_large, vals_small, equal_var=False)

        print(f"\n  {bot}: top 25% (qty>={q75:.0f}) vs bottom 75%")
        print(f"    Large: n={len(vals_large)}, mean_impact_20={mean_l:+.2f}")
        print(f"    Small: n={len(vals_small)}, mean_impact_20={mean_s:+.2f}")
        print(f"    Difference: {mean_l - mean_s:+.2f}, t={t:+.2f}, p={p:.4f}")


def main():
    prices = load_prices()
    trades = load_trades()

    df = compute_bot_signed_impacts(prices, trades)
    print(f"Total signal bot trades on VE: {len(df)}")
    print(f"  Mark 67: {len(df[df['bot'] == 'Mark 67'])}")
    print(f"  Mark 49: {len(df[df['bot'] == 'Mark 49'])}")
    print(f"  Mark 22: {len(df[df['bot'] == 'Mark 22'])}")

    print_size_distribution(df)
    print_impact_by_quartile(df)
    print_quantity_weighted_signal(df)
    print_threshold_analysis(df)
    print_combined_threshold(df)


if __name__ == "__main__":
    main()
