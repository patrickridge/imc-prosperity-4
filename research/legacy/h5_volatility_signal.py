"""H5: Do bot trades predict spread or volatility changes?

Instead of direction, test whether bot trades predict:
1. Future spread (narrow = opportunity, wide = danger)
2. Realized volatility (abs mid change over horizon)
3. Activity clustering effects
4. Event-study spread dynamics around bot trades

Products: VELVETFRUIT_EXTRACT, HYDROGEL_PACK
"""

import pandas as pd
import numpy as np
from pathlib import Path
from scipy import stats

DATA_DIR = Path(__file__).parent.parent / "data" / "round4"
PRODUCTS = ["VELVETFRUIT_EXTRACT", "HYDROGEL_PACK"]
DAYS = [1, 2, 3]
HORIZONS = [1, 5, 10, 20, 50]
EVENT_WINDOW = [-10, -5, -1, 0, 1, 5, 10, 20]
TRADE_DELAY = 100  # market_trades at T are from T-100

VE_BOTS = ["Mark 67", "Mark 49", "Mark 22", "Mark 55", "Mark 14", "Mark 01"]
HP_BOTS = ["Mark 14", "Mark 38", "Mark 22"]


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


def build_price_series(prices, product):
    """Build per-day DataFrames with mid_price and spread, indexed by timestamp."""
    product_prices = prices[prices["product"] == product].copy()
    product_prices["spread"] = product_prices["ask_price_1"] - product_prices["bid_price_1"]
    return {
        day: grp.set_index("timestamp")[["mid_price", "spread"]].sort_index()
        for day, grp in product_prices.groupby("day")
    }


def get_bot_trade_timestamps(trades, product, bot):
    """Get unique timestamps when a bot traded a product, adjusted for delay."""
    prod_trades = trades[trades["symbol"] == product]
    bot_trades = prod_trades[(prod_trades["buyer"] == bot) | (prod_trades["seller"] == bot)]
    adjusted = bot_trades["timestamp"].values + TRADE_DELAY
    days = bot_trades["day"].values
    return pd.DataFrame({"day": days, "timestamp": adjusted}).drop_duplicates()


def spread_after_bot_trades(price_series, bot_events):
    """Compute spread at t+N after each bot trade. Return list of dicts."""
    rows = []
    for _, event in bot_events.iterrows():
        day = event["day"]
        t = event["timestamp"]
        if day not in price_series:
            continue
        ps = price_series[day]
        if t not in ps.index:
            continue

        row = {"day": day, "timestamp": t, "spread_t0": ps.loc[t, "spread"]}
        for h in HORIZONS:
            future_t = t + h * 100
            if future_t in ps.index:
                row[f"spread_t{h}"] = ps.loc[future_t, "spread"]
        rows.append(row)
    return pd.DataFrame(rows)


def realized_vol_after_bot_trades(price_series, bot_events):
    """Compute abs(mid change) at t+N after each bot trade."""
    rows = []
    for _, event in bot_events.iterrows():
        day = event["day"]
        t = event["timestamp"]
        if day not in price_series:
            continue
        ps = price_series[day]
        if t not in ps.index:
            continue

        mid_now = ps.loc[t, "mid_price"]
        row = {"day": day, "timestamp": t}
        for h in HORIZONS:
            future_t = t + h * 100
            if future_t in ps.index:
                row[f"vol_t{h}"] = abs(ps.loc[future_t, "mid_price"] - mid_now)
        rows.append(row)
    return pd.DataFrame(rows)


def unconditional_spread(price_series):
    """Compute unconditional average spread across all timestamps."""
    all_spreads = pd.concat([ps["spread"] for ps in price_series.values()])
    return all_spreads.mean(), all_spreads.std(), len(all_spreads)


def unconditional_vol(price_series):
    """Compute unconditional abs(mid change) at each horizon."""
    results = {}
    for h in HORIZONS:
        vols = []
        for day, ps in price_series.items():
            mids = ps["mid_price"].values
            timestamps = ps.index.values
            for i in range(len(timestamps)):
                future_t = timestamps[i] + h * 100
                idx = np.searchsorted(timestamps, future_t)
                if idx < len(timestamps) and timestamps[idx] == future_t:
                    vols.append(abs(mids[idx] - mids[i]))
        vols = np.array(vols)
        results[h] = {"mean": vols.mean(), "std": vols.std(), "n": len(vols)}
    return results


def event_study_spread(price_series, bot_events):
    """Capture spread at each offset in EVENT_WINDOW around bot trades."""
    rows = []
    for _, event in bot_events.iterrows():
        day = event["day"]
        t = event["timestamp"]
        if day not in price_series:
            continue
        ps = price_series[day]

        row = {"day": day, "timestamp": t}
        for offset in EVENT_WINDOW:
            target_t = t + offset * 100
            if target_t in ps.index:
                row[f"spread_{offset}"] = ps.loc[target_t, "spread"]
        rows.append(row)
    return pd.DataFrame(rows)


def activity_clustering(trades, product, price_series, window_size=20):
    """Count bot trades in rolling windows, compare spread/vol in high vs low activity."""
    prod_trades = trades[trades["symbol"] == product].copy()
    prod_trades["adjusted_ts"] = prod_trades["timestamp"] + TRADE_DELAY

    results_by_day = {}
    for day in DAYS:
        if day not in price_series:
            continue
        ps = price_series[day]
        day_trades = prod_trades[prod_trades["day"] == day]

        # Count trades per timestamp
        trade_counts = day_trades.groupby("adjusted_ts").size()

        # Rolling trade count: sum of trades in [t - window*100, t]
        timestamps = ps.index.values
        rolling_counts = np.zeros(len(timestamps))
        for i, t in enumerate(timestamps):
            window_start = t - window_size * 100
            mask = (trade_counts.index >= window_start) & (trade_counts.index <= t)
            rolling_counts[i] = trade_counts[mask].sum()

        # Split into high/low activity (above/below median)
        median_activity = np.median(rolling_counts)
        high_mask = rolling_counts > median_activity
        low_mask = rolling_counts <= median_activity

        spreads = ps["spread"].values
        high_spread = spreads[high_mask].mean() if high_mask.sum() > 0 else np.nan
        low_spread = spreads[low_mask].mean() if low_mask.sum() > 0 else np.nan

        results_by_day[day] = {
            "high_activity_spread": high_spread,
            "low_activity_spread": low_spread,
            "high_count": high_mask.sum(),
            "low_count": low_mask.sum(),
            "median_activity": median_activity,
        }

    return results_by_day


def ttest_vs_baseline(conditional_values, baseline_mean, baseline_std, baseline_n):
    """One-sample t-test: is conditional mean different from baseline?"""
    n = len(conditional_values)
    if n < 5:
        return np.nan, np.nan, n
    sample_mean = np.nanmean(conditional_values)
    sample_std = np.nanstd(conditional_values, ddof=1)
    se = sample_std / np.sqrt(n)
    if se == 0:
        return 0.0, 1.0, n
    t_stat = (sample_mean - baseline_mean) / se
    p_val = 2 * stats.t.sf(abs(t_stat), df=n - 1)
    return t_stat, p_val, n


def report_spread_analysis(product, price_series, trades, bots):
    print(f"\n{'='*70}")
    print(f"  SPREAD AFTER BOT TRADES — {product}")
    print(f"{'='*70}")

    base_mean, base_std, base_n = unconditional_spread(price_series)
    print(f"\nUnconditional spread: {base_mean:.3f} (std={base_std:.3f}, n={base_n})")

    for bot in bots:
        events = get_bot_trade_timestamps(trades, product, bot)
        if len(events) == 0:
            continue

        df = spread_after_bot_trades(price_series, events)
        if len(df) == 0:
            continue

        print(f"\n  {bot} ({len(df)} events)")
        print(f"  {'Horizon':<12} {'Mean':>8} {'vs Base':>10} {'t-stat':>8} {'p-val':>8} {'n':>6}")
        print(f"  {'-'*54}")

        for h in HORIZONS:
            col = f"spread_t{h}"
            if col not in df.columns:
                continue
            vals = df[col].dropna().values
            t_stat, p_val, n = ttest_vs_baseline(vals, base_mean, base_std, base_n)
            mean_val = np.nanmean(vals)
            diff = mean_val - base_mean
            sig = "***" if p_val < 0.001 else "**" if p_val < 0.01 else "*" if p_val < 0.05 else ""
            print(f"  t+{h:<8} {mean_val:>8.3f} {diff:>+10.3f} {t_stat:>8.2f} {p_val:>8.4f} {n:>6} {sig}")

        # Day-by-day consistency for t+1
        col = "spread_t1"
        if col in df.columns:
            print(f"\n  Day-by-day t+1 spread:")
            for day in DAYS:
                day_vals = df[df["day"] == day][col].dropna().values
                if len(day_vals) > 0:
                    print(f"    Day {day}: {np.mean(day_vals):.3f} (n={len(day_vals)})")


def report_vol_analysis(product, price_series, trades, bots):
    print(f"\n{'='*70}")
    print(f"  REALIZED VOL AFTER BOT TRADES — {product}")
    print(f"{'='*70}")

    base_vol = unconditional_vol(price_series)
    print("\nUnconditional realized vol:")
    for h in HORIZONS:
        bv = base_vol[h]
        print(f"  t+{h}: {bv['mean']:.3f} (std={bv['std']:.3f})")

    for bot in bots:
        events = get_bot_trade_timestamps(trades, product, bot)
        if len(events) == 0:
            continue

        df = realized_vol_after_bot_trades(price_series, events)
        if len(df) == 0:
            continue

        print(f"\n  {bot} ({len(df)} events)")
        print(f"  {'Horizon':<12} {'Mean':>8} {'vs Base':>10} {'Ratio':>8} {'t-stat':>8} {'p-val':>8} {'n':>6}")
        print(f"  {'-'*62}")

        for h in HORIZONS:
            col = f"vol_t{h}"
            if col not in df.columns:
                continue
            vals = df[col].dropna().values
            bv = base_vol[h]
            t_stat, p_val, n = ttest_vs_baseline(vals, bv["mean"], bv["std"], bv["n"])
            mean_val = np.nanmean(vals)
            diff = mean_val - bv["mean"]
            ratio = mean_val / bv["mean"] if bv["mean"] > 0 else np.nan
            sig = "***" if p_val < 0.001 else "**" if p_val < 0.01 else "*" if p_val < 0.05 else ""
            print(f"  t+{h:<8} {mean_val:>8.3f} {diff:>+10.3f} {ratio:>8.2f}x {t_stat:>8.2f} {p_val:>8.4f} {n:>6} {sig}")

        # Day-by-day for t+5
        col = "vol_t5"
        if col in df.columns:
            print(f"\n  Day-by-day t+5 vol:")
            for day in DAYS:
                day_vals = df[df["day"] == day][col].dropna().values
                if len(day_vals) > 0:
                    print(f"    Day {day}: {np.mean(day_vals):.3f} (n={len(day_vals)})")


def report_event_study(product, price_series, trades, bots):
    print(f"\n{'='*70}")
    print(f"  EVENT STUDY: SPREAD AROUND BOT TRADES — {product}")
    print(f"{'='*70}")

    base_mean, _, _ = unconditional_spread(price_series)

    for bot in bots:
        events = get_bot_trade_timestamps(trades, product, bot)
        if len(events) == 0:
            continue

        df = event_study_spread(price_series, events)
        if len(df) == 0:
            continue

        print(f"\n  {bot} ({len(df)} events)")
        print(f"  {'Offset':<10} {'Mean Spread':>12} {'vs Base':>10} {'n':>6}")
        print(f"  {'-'*40}")

        for offset in EVENT_WINDOW:
            col = f"spread_{offset}"
            if col not in df.columns:
                continue
            vals = df[col].dropna().values
            if len(vals) == 0:
                continue
            mean_val = np.mean(vals)
            diff = mean_val - base_mean
            print(f"  t{offset:>+4}      {mean_val:>12.3f} {diff:>+10.3f} {len(vals):>6}")


def report_clustering(product, trades, price_series):
    print(f"\n{'='*70}")
    print(f"  ACTIVITY CLUSTERING — {product}")
    print(f"{'='*70}")

    results = activity_clustering(trades, product, price_series)
    for day, res in sorted(results.items()):
        diff = res["high_activity_spread"] - res["low_activity_spread"]
        print(f"\n  Day {day}: median_activity={res['median_activity']:.0f}")
        print(f"    High activity: spread={res['high_activity_spread']:.3f} (n={res['high_count']})")
        print(f"    Low activity:  spread={res['low_activity_spread']:.3f} (n={res['low_count']})")
        print(f"    Difference:    {diff:+.3f}")


def main():
    prices = load_prices()
    trades = load_trades()

    for product in PRODUCTS:
        bots = VE_BOTS if product == "VELVETFRUIT_EXTRACT" else HP_BOTS
        price_series = build_price_series(prices, product)

        report_spread_analysis(product, price_series, trades, bots)
        report_vol_analysis(product, price_series, trades, bots)
        report_event_study(product, price_series, trades, bots)
        report_clustering(product, trades, price_series)

    print(f"\n{'='*70}")
    print("  SUMMARY")
    print(f"{'='*70}")
    print("\nSee above for detailed results per product, per bot.")
    print("Key question: any spread/vol prediction with |t| > 2 AND consistent across days?")


if __name__ == "__main__":
    main()
