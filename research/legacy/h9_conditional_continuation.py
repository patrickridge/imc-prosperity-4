"""H9: Conditional post-observation continuation for VE signal bots.

Tests whether the ~0.1 tick average post-observation continuation
becomes exploitably large (>2.5 ticks) under specific conditions:
1. High rolling volatility
2. Order book imbalance at observation time
3. Multiple signal bots firing in a cluster
4. Recent price momentum alignment
5. Time since last bot trade
"""

import pandas as pd
import numpy as np
from pathlib import Path
from scipy import stats

DATA_DIR = Path(__file__).parent.parent / "data" / "round4"
PRODUCT = "VELVETFRUIT_EXTRACT"

# Signal bots: Mark 67 buys (bullish signal), Mark 49/22 sell (bearish signal)
SMART_BUYER = "Mark 67"
FADE_SELLERS = ["Mark 49", "Mark 22"]

HORIZONS = [1, 5, 10, 20]  # timestamps after observation
OBSERVATION_DELAY = 100  # market_trades at T are from T-100


def load_prices():
    frames = []
    for day in range(1, 4):
        path = DATA_DIR / f"prices_round_4_day_{day}.csv"
        df = pd.read_csv(path, sep=";")
        frames.append(df)
    prices = pd.concat(frames, ignore_index=True)
    return prices[prices["product"] == PRODUCT].copy()


def load_trades():
    frames = []
    for day in range(1, 4):
        path = DATA_DIR / f"trades_round_4_day_{day}.csv"
        df = pd.read_csv(path, sep=";")
        df["day"] = day
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def build_mid_series(prices):
    """Build per-day mid price series indexed by timestamp."""
    series = {}
    for day, group in prices.groupby("day"):
        s = group.set_index("timestamp")["mid_price"].sort_index()
        series[day] = s
    return series


def build_book_imbalance(prices):
    """Bid vol / (bid vol + ask vol) at level 1."""
    prices = prices.copy()
    prices["imbalance"] = prices["bid_volume_1"] / (
        prices["bid_volume_1"] + prices["ask_volume_1"]
    )
    imb = {}
    for day, group in prices.groupby("day"):
        imb[day] = group.set_index("timestamp")["imbalance"].sort_index()
    return imb


def extract_signal_events(trades):
    """Extract bullish/bearish signal events from VE trades."""
    ve_trades = trades[trades["symbol"] == PRODUCT].copy()

    bullish = ve_trades[ve_trades["buyer"] == SMART_BUYER].copy()
    bullish["signal"] = 1  # +1 = bullish

    bearish = ve_trades[ve_trades["seller"].isin(FADE_SELLERS)].copy()
    # Exclude cases where Mark 67 is buying from fade sellers (already in bullish)
    bearish = bearish[bearish["buyer"] != SMART_BUYER]
    bearish["signal"] = -1  # -1 = bearish

    events = pd.concat([bullish, bearish], ignore_index=True)
    events = events.sort_values(["day", "timestamp"]).reset_index(drop=True)
    return events


def get_continuation(mid_series, day, obs_time, signal, horizons):
    """Compute signed continuation from observation time."""
    s = mid_series.get(day)
    if s is None:
        return [np.nan] * len(horizons)

    if obs_time not in s.index:
        # Find nearest available timestamp at or after obs_time
        valid = s.index[s.index >= obs_time]
        if len(valid) == 0:
            return [np.nan] * len(horizons)
        obs_time = valid[0]

    base_price = s.loc[obs_time]
    results = []
    for h in horizons:
        target_time = obs_time + h * 100  # timestamps are in 100-unit increments
        valid = s.index[s.index >= target_time]
        if len(valid) == 0:
            results.append(np.nan)
        else:
            future_price = s.loc[valid[0]]
            # Signed: positive = price moved in signal direction
            results.append((future_price - base_price) * signal)
    return results


def compute_rolling_vol(mid_series, window=50):
    """Rolling std of mid_price changes."""
    vol_series = {}
    for day, s in mid_series.items():
        changes = s.diff()
        vol = changes.rolling(window, min_periods=10).std()
        vol_series[day] = vol
    return vol_series


def compute_momentum(mid_series, window=50):
    """Rolling price change over last window timestamps."""
    mom_series = {}
    for day, s in mid_series.items():
        mom = s - s.shift(window)
        mom_series[day] = mom
    return mom_series


def report_bins(label, df, bin_col, horizons):
    """Report mean continuation, t-stat, N per bin."""
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")

    for bin_val in sorted(df[bin_col].dropna().unique()):
        subset = df[df[bin_col] == bin_val]
        n = len(subset)
        print(f"\n  Bin: {bin_val} (N={n})")
        print(f"  {'Horizon':<10} {'Mean':>8} {'Std':>8} {'t-stat':>8} {'p-val':>8}")
        print(f"  {'-'*44}")

        for h in horizons:
            col = f"cont_{h}"
            vals = subset[col].dropna()
            if len(vals) < 3:
                print(f"  t+{h:<7} {'N/A':>8} {'N/A':>8} {'N/A':>8} {'N/A':>8}")
                continue
            mean = vals.mean()
            std = vals.std()
            t_stat, p_val = stats.ttest_1samp(vals, 0)
            print(f"  t+{h:<7} {mean:>8.2f} {std:>8.2f} {t_stat:>8.2f} {p_val:>8.4f}")

    # Per-day consistency
    print(f"\n  Per-day breakdown (t+10 horizon):")
    for day in [1, 2, 3]:
        day_df = df[df["day"] == day]
        for bin_val in sorted(df[bin_col].dropna().unique()):
            subset = day_df[day_df[bin_col] == bin_val]
            vals = subset["cont_10"].dropna()
            if len(vals) > 0:
                print(f"    Day {day}, Bin {bin_val}: mean={vals.mean():.2f}, N={len(vals)}")


def main():
    print("Loading data...")
    prices = load_prices()
    trades = load_trades()

    mid_series = build_mid_series(prices)
    book_imb = build_book_imbalance(prices)
    vol_series = compute_rolling_vol(mid_series)
    mom_series = compute_momentum(mid_series)

    events = extract_signal_events(trades)
    print(f"Total signal events: {len(events)}")

    # Compute observation time and continuations
    events["obs_time"] = events["timestamp"] + OBSERVATION_DELAY

    for h in HORIZONS:
        events[f"cont_{h}"] = np.nan

    for idx, row in events.iterrows():
        conts = get_continuation(
            mid_series, row["day"], row["obs_time"], row["signal"], HORIZONS
        )
        for h, c in zip(HORIZONS, conts):
            events.at[idx, f"cont_{h}"] = c

    # Overall baseline
    print(f"\n{'='*60}")
    print(f"  BASELINE (all signal events)")
    print(f"{'='*60}")
    print(f"  {'Horizon':<10} {'Mean':>8} {'Std':>8} {'t-stat':>8} {'N':>6}")
    print(f"  {'-'*40}")
    for h in HORIZONS:
        col = f"cont_{h}"
        vals = events[col].dropna()
        mean = vals.mean()
        std = vals.std()
        t_stat, _ = stats.ttest_1samp(vals, 0)
        print(f"  t+{h:<7} {mean:>8.2f} {std:>8.2f} {t_stat:>8.2f} {len(vals):>6}")

    # --- CONDITION 1: Rolling volatility ---
    for idx, row in events.iterrows():
        day_vol = vol_series.get(row["day"])
        if day_vol is not None and row["obs_time"] in day_vol.index:
            events.at[idx, "vol"] = day_vol.loc[row["obs_time"]]
        else:
            # nearest prior
            if day_vol is not None:
                prior = day_vol.index[day_vol.index <= row["obs_time"]]
                if len(prior) > 0:
                    events.at[idx, "vol"] = day_vol.loc[prior[-1]]

    vol_valid = events["vol"].dropna()
    if len(vol_valid) > 0:
        quartiles = vol_valid.quantile([0.25, 0.5, 0.75])
        events["vol_bin"] = pd.cut(
            events["vol"],
            bins=[-np.inf, quartiles[0.25], quartiles[0.5], quartiles[0.75], np.inf],
            labels=["Q1_low", "Q2", "Q3", "Q4_high"],
        )
        report_bins("CONDITION 1: Rolling Volatility Quartiles", events, "vol_bin", HORIZONS)

    # --- CONDITION 2: Book imbalance ---
    for idx, row in events.iterrows():
        day_imb = book_imb.get(row["day"])
        if day_imb is not None and row["obs_time"] in day_imb.index:
            events.at[idx, "imbalance"] = day_imb.loc[row["obs_time"]]
        else:
            if day_imb is not None:
                prior = day_imb.index[day_imb.index <= row["obs_time"]]
                if len(prior) > 0:
                    events.at[idx, "imbalance"] = day_imb.loc[prior[-1]]

    # Classify: imbalance aligned with signal or not
    # Bullish signal (+1): high bid_vol fraction = aligned
    # Bearish signal (-1): low bid_vol fraction = aligned
    events["imb_aligned"] = np.where(
        events["signal"] == 1,
        events["imbalance"] > 0.5,  # more bids = aligned with bullish
        events["imbalance"] < 0.5,  # more asks = aligned with bearish
    )
    events["imb_bin"] = events["imb_aligned"].map({True: "aligned", False: "counter"})
    report_bins("CONDITION 2: Book Imbalance (aligned vs counter)", events, "imb_bin", HORIZONS)

    # Also try raw imbalance quartiles
    imb_valid = events["imbalance"].dropna()
    if len(imb_valid) > 0:
        iq = imb_valid.quantile([0.25, 0.5, 0.75])
        edges = sorted(set([-np.inf, iq[0.25], iq[0.5], iq[0.75], np.inf]))
        n_bins = len(edges) - 1
        labels = [f"imb_bin_{i+1}" for i in range(n_bins)]
        events["imb_quartile"] = pd.cut(
            events["imbalance"],
            bins=edges,
            labels=labels,
        )
        report_bins("CONDITION 2b: Raw Book Imbalance Quartiles", events, "imb_quartile", HORIZONS)

    # --- CONDITION 3: Cluster of signal bots ---
    CLUSTER_WINDOW = 500  # ticks
    events["in_cluster"] = False
    for idx, row in events.iterrows():
        same_day = events[
            (events["day"] == row["day"])
            & (events.index != idx)
            & (abs(events["timestamp"] - row["timestamp"]) <= CLUSTER_WINDOW)
        ]
        if len(same_day) >= 1:  # at least 1 other signal = 2+ total
            events.at[idx, "in_cluster"] = True

    events["cluster_bin"] = events["in_cluster"].map({True: "cluster_2+", False: "isolated"})
    report_bins("CONDITION 3: Signal Bot Clusters (within 500 ticks)", events, "cluster_bin", HORIZONS)

    # --- CONDITION 4: Recent momentum ---
    for idx, row in events.iterrows():
        day_mom = mom_series.get(row["day"])
        if day_mom is not None and row["obs_time"] in day_mom.index:
            events.at[idx, "momentum"] = day_mom.loc[row["obs_time"]]
        else:
            if day_mom is not None:
                prior = day_mom.index[day_mom.index <= row["obs_time"]]
                if len(prior) > 0:
                    events.at[idx, "momentum"] = day_mom.loc[prior[-1]]

    # Signed momentum: positive = momentum in same direction as signal
    events["signed_mom"] = events["momentum"] * events["signal"]
    mom_valid = events["signed_mom"].dropna()
    if len(mom_valid) > 0:
        mq = mom_valid.quantile([0.33, 0.67])
        events["mom_bin"] = pd.cut(
            events["signed_mom"],
            bins=[-np.inf, mq[0.33], mq[0.67], np.inf],
            labels=["reversal", "neutral", "trend"],
        )
        report_bins("CONDITION 4: Momentum Alignment", events, "mom_bin", HORIZONS)

    # --- CONDITION 5: Time since last bot trade ---
    events_sorted = events.sort_values(["day", "timestamp"]).reset_index(drop=True)
    events_sorted["time_since_last"] = np.nan
    for day in [1, 2, 3]:
        day_mask = events_sorted["day"] == day
        day_events = events_sorted[day_mask]
        timestamps = day_events["timestamp"].values
        for i, idx in enumerate(day_events.index):
            if i == 0:
                events_sorted.at[idx, "time_since_last"] = 999999  # first of day
            else:
                gap = timestamps[i] - timestamps[i - 1]
                events_sorted.at[idx, "time_since_last"] = gap

    tsl_valid = events_sorted["time_since_last"].dropna()
    if len(tsl_valid) > 0:
        tq = tsl_valid.quantile([0.33, 0.67])
        events_sorted["tsl_bin"] = pd.cut(
            events_sorted["time_since_last"],
            bins=[-np.inf, tq[0.33], tq[0.67], np.inf],
            labels=["rapid", "medium", "after_silence"],
        )
        # Need continuation cols in events_sorted too
        for h in HORIZONS:
            col = f"cont_{h}"
            if col not in events_sorted.columns:
                events_sorted[col] = events[col]

        report_bins("CONDITION 5: Time Since Last Bot Trade", events_sorted, "tsl_bin", HORIZONS)

    # --- SUMMARY: Best conditions ---
    print(f"\n{'='*60}")
    print(f"  SUMMARY: Max continuation by condition (t+10 horizon)")
    print(f"{'='*60}")

    def best_bin(df, bin_col, horizon=10):
        col = f"cont_{horizon}"
        best_mean = -999
        best_label = ""
        best_n = 0
        for bin_val in df[bin_col].dropna().unique():
            subset = df[df[bin_col] == bin_val]
            vals = subset[col].dropna()
            if len(vals) >= 5 and vals.mean() > best_mean:
                best_mean = vals.mean()
                best_label = str(bin_val)
                best_n = len(vals)
        return best_label, best_mean, best_n

    conditions = [
        ("Volatility", events, "vol_bin"),
        ("Book imbalance (aligned)", events, "imb_bin"),
        ("Book imbalance (quartile)", events, "imb_quartile"),
        ("Cluster", events, "cluster_bin"),
        ("Momentum", events, "mom_bin"),
        ("Time since last", events_sorted, "tsl_bin"),
    ]

    print(f"  {'Condition':<30} {'Best bin':<15} {'Mean cont':>10} {'N':>6}")
    print(f"  {'-'*65}")
    for name, df, col in conditions:
        if col in df.columns:
            label, mean, n = best_bin(df, col)
            flag = " ***" if mean > 2.5 else ""
            print(f"  {name:<30} {label:<15} {mean:>10.2f} {n:>6}{flag}")

    print(f"\n  Threshold for exploitability: >2.5 ticks (half-spread)")
    print(f"  *** = potentially exploitable")


if __name__ == "__main__":
    main()
