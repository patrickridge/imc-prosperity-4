"""H12: Cross-bot temporal prediction on VELVETFRUIT_EXTRACT.

Does one bot trading predict WHEN another bot will trade?
Focus: Mark 67 (smart buyer), Mark 49 (mostly seller), Mark 22 (frequent seller).
"""

import pandas as pd
import numpy as np
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data" / "round4"
PRODUCT = "VELVETFRUIT_EXTRACT"

# Bots of interest
MARK_67 = "Mark 67"
MARK_49 = "Mark 49"
MARK_22 = "Mark 22"


def load_ve_trades():
    """Load all VE trades across 3 days."""
    frames = []
    for day in range(1, 4):
        path = DATA_DIR / f"trades_round_4_day_{day}.csv"
        df = pd.read_csv(path, sep=";")
        df["day"] = day
        frames.append(df)
    trades = pd.concat(frames, ignore_index=True)
    return trades[trades["symbol"] == PRODUCT].copy()


def bot_trade_timestamps(trades, bot_name, side=None):
    """Get sorted list of (day, timestamp) for a bot's trades.

    side: 'buy' filters to trades where bot is buyer,
          'sell' filters to trades where bot is seller,
          None includes both.
    """
    if side == "buy":
        mask = trades["buyer"] == bot_name
    elif side == "sell":
        mask = trades["seller"] == bot_name
    else:
        mask = (trades["buyer"] == bot_name) | (trades["seller"] == bot_name)

    subset = trades[mask][["day", "timestamp"]].drop_duplicates()
    return subset.sort_values(["day", "timestamp"]).reset_index(drop=True)


def time_to_next(trigger_ts, target_ts):
    """For each trigger event, find time until next target event (same day).

    Returns array of gaps (in ticks). NaN if no subsequent target on that day.
    """
    gaps = []
    for _, row in trigger_ts.iterrows():
        day, ts = row["day"], row["timestamp"]
        same_day_targets = target_ts[target_ts["day"] == day]["timestamp"].values
        future = same_day_targets[same_day_targets > ts]
        if len(future) > 0:
            gaps.append(future[0] - ts)
        else:
            gaps.append(np.nan)
    return np.array(gaps, dtype=float)


def unconditional_inter_trade_gaps(ts_df):
    """Compute inter-trade gaps within each day."""
    gaps = []
    for day in ts_df["day"].unique():
        day_ts = ts_df[ts_df["day"] == day]["timestamp"].sort_values().values
        if len(day_ts) > 1:
            gaps.extend(np.diff(day_ts))
    return np.array(gaps, dtype=float)


def conditional_hazard(trigger_ts, target_ts, k_values):
    """P(target trades within K ticks | trigger just fired) vs unconditional.

    Unconditional: sample random timestamps, check P(target within K).
    """
    gaps = time_to_next(trigger_ts, target_ts)
    valid_gaps = gaps[~np.isnan(gaps)]

    conditional_probs = {}
    for k in k_values:
        conditional_probs[k] = np.mean(valid_gaps <= k) if len(valid_gaps) > 0 else 0.0

    # Unconditional baseline: sample uniformly from trading day
    # For each day, pick random timestamps and compute time-to-next-target
    all_days = trigger_ts["day"].unique()
    unconditional_probs = {}
    rng = np.random.default_rng(42)

    random_gaps = []
    for day in all_days:
        day_targets = target_ts[target_ts["day"] == day]["timestamp"].sort_values().values
        if len(day_targets) == 0:
            continue
        # Sample 500 random timestamps per day from trading range
        min_ts = 0
        max_ts = 999900
        random_ts = rng.integers(min_ts, max_ts, size=500)
        for rt in random_ts:
            future = day_targets[day_targets > rt]
            if len(future) > 0:
                random_gaps.append(future[0] - rt)

    random_gaps = np.array(random_gaps, dtype=float)
    for k in k_values:
        unconditional_probs[k] = np.mean(random_gaps <= k) if len(random_gaps) > 0 else 0.0

    return conditional_probs, unconditional_probs


def per_day_breakdown(trigger_ts, target_ts, k):
    """Per-day conditional probability for a given K."""
    results = {}
    for day in sorted(trigger_ts["day"].unique()):
        day_trigger = trigger_ts[trigger_ts["day"] == day]
        day_target = target_ts[target_ts["day"] == day]
        gaps = time_to_next(day_trigger, day_target)
        valid = gaps[~np.isnan(gaps)]
        if len(valid) > 0:
            results[day] = (np.mean(valid <= k), len(valid))
        else:
            results[day] = (0.0, 0)
    return results


def simultaneous_rate(ts_a, ts_b):
    """What fraction of A's trades have B trading at exact same timestamp?"""
    merged = ts_a.merge(ts_b, on=["day", "timestamp"], how="inner")
    return len(merged) / len(ts_a) if len(ts_a) > 0 else 0.0


def main():
    trades = load_ve_trades()
    print(f"Total VE trades: {len(trades)}")
    print()

    # Get timestamps for each bot
    m67_buys = bot_trade_timestamps(trades, MARK_67, side="buy")
    m49_sells = bot_trade_timestamps(trades, MARK_49, side="sell")
    m49_all = bot_trade_timestamps(trades, MARK_49)
    m22_sells = bot_trade_timestamps(trades, MARK_22, side="sell")
    m22_all = bot_trade_timestamps(trades, MARK_22)
    m67_all = bot_trade_timestamps(trades, MARK_67)

    print(f"Mark 67 buy events: {len(m67_buys)}")
    print(f"Mark 49 sell events: {len(m49_sells)}")
    print(f"Mark 22 sell events: {len(m22_sells)}")
    print(f"Mark 22 all events: {len(m22_all)}")
    print()

    # ---- 1. Simultaneous trading rates ----
    print("=" * 60)
    print("1. SIMULTANEOUS TRADING (same timestamp)")
    print("=" * 60)
    rate_67_49 = simultaneous_rate(m67_buys, m49_sells)
    print(f"  Mark 67 buy & Mark 49 sell at same tick: {rate_67_49:.1%}")
    rate_67_22 = simultaneous_rate(m67_buys, m22_sells)
    print(f"  Mark 67 buy & Mark 22 sell at same tick: {rate_67_22:.1%}")
    print()

    # ---- 2. Conditional timing distributions ----
    print("=" * 60)
    print("2. CONDITIONAL TIMING: Mark 67 buy → Mark 49 next sell")
    print("=" * 60)
    # Exclude simultaneous (look at cases where Mark 49 doesn't fire with 67)
    m67_no_simul_49 = m67_buys[
        ~m67_buys.set_index(["day", "timestamp"]).index.isin(
            m49_sells.set_index(["day", "timestamp"]).index
        )
    ]
    print(f"  Mark 67 buys WITHOUT simultaneous Mark 49 sell: {len(m67_no_simul_49)}")
    gaps_67_to_49 = time_to_next(m67_no_simul_49, m49_sells)
    valid_67_49 = gaps_67_to_49[~np.isnan(gaps_67_to_49)]
    if len(valid_67_49) > 0:
        print(f"  Time to next Mark 49 sell (when not simultaneous):")
        print(f"    Median: {np.median(valid_67_49):.0f} ticks")
        print(f"    Mean:   {np.mean(valid_67_49):.0f} ticks")
        print(f"    P25/P75: {np.percentile(valid_67_49, 25):.0f} / {np.percentile(valid_67_49, 75):.0f}")
    print()

    # Unconditional Mark 49 inter-trade gaps
    uncond_49 = unconditional_inter_trade_gaps(m49_sells)
    if len(uncond_49) > 0:
        print(f"  Mark 49 unconditional inter-sell gap:")
        print(f"    Median: {np.median(uncond_49):.0f} ticks")
        print(f"    Mean:   {np.mean(uncond_49):.0f} ticks")
    print()

    # ---- 3. Mark 67 → Mark 22 ----
    print("=" * 60)
    print("3. CONDITIONAL TIMING: Mark 67 buy → Mark 22 next sell")
    print("=" * 60)
    gaps_67_to_22 = time_to_next(m67_buys, m22_sells)
    valid_67_22 = gaps_67_to_22[~np.isnan(gaps_67_to_22)]
    if len(valid_67_22) > 0:
        print(f"  Time from Mark 67 buy to next Mark 22 sell:")
        print(f"    Median: {np.median(valid_67_22):.0f} ticks")
        print(f"    Mean:   {np.mean(valid_67_22):.0f} ticks")
        print(f"    P25/P75: {np.percentile(valid_67_22, 25):.0f} / {np.percentile(valid_67_22, 75):.0f}")
    print()

    uncond_22 = unconditional_inter_trade_gaps(m22_sells)
    if len(uncond_22) > 0:
        print(f"  Mark 22 unconditional inter-sell gap:")
        print(f"    Median: {np.median(uncond_22):.0f} ticks")
        print(f"    Mean:   {np.mean(uncond_22):.0f} ticks")
    print()

    # ---- 4. Mark 22 → Mark 67 ----
    print("=" * 60)
    print("4. CONDITIONAL TIMING: Mark 22 sell → Mark 67 next buy")
    print("=" * 60)
    # Exclude simultaneous
    m22_no_simul_67 = m22_sells[
        ~m22_sells.set_index(["day", "timestamp"]).index.isin(
            m67_buys.set_index(["day", "timestamp"]).index
        )
    ]
    print(f"  Mark 22 sells WITHOUT simultaneous Mark 67 buy: {len(m22_no_simul_67)}")
    gaps_22_to_67 = time_to_next(m22_no_simul_67, m67_buys)
    valid_22_67 = gaps_22_to_67[~np.isnan(gaps_22_to_67)]
    if len(valid_22_67) > 0:
        print(f"  Time from Mark 22 sell to next Mark 67 buy:")
        print(f"    Median: {np.median(valid_22_67):.0f} ticks")
        print(f"    Mean:   {np.mean(valid_22_67):.0f} ticks")
        print(f"    P25/P75: {np.percentile(valid_22_67, 25):.0f} / {np.percentile(valid_22_67, 75):.0f}")
    print()

    uncond_67 = unconditional_inter_trade_gaps(m67_buys)
    if len(uncond_67) > 0:
        print(f"  Mark 67 unconditional inter-buy gap:")
        print(f"    Median: {np.median(uncond_67):.0f} ticks")
        print(f"    Mean:   {np.mean(uncond_67):.0f} ticks")
    print()

    # ---- 5. Cross-conditional hazard ----
    K_VALUES = [100, 500, 1000, 5000]
    print("=" * 60)
    print("5. CROSS-CONDITIONAL HAZARD RATES")
    print("=" * 60)

    pairs = [
        ("Mark 67 buy → Mark 49 sell", m67_buys, m49_sells),
        ("Mark 67 buy → Mark 22 sell", m67_buys, m22_sells),
        ("Mark 22 sell → Mark 67 buy", m22_sells, m67_buys),
        ("Mark 49 sell → Mark 67 buy", m49_sells, m67_buys),
    ]

    for label, trigger, target in pairs:
        cond, uncond = conditional_hazard(trigger, target, K_VALUES)
        print(f"\n  {label}:")
        print(f"    {'K':>6}  {'P(cond)':>10}  {'P(uncond)':>10}  {'Ratio':>8}")
        for k in K_VALUES:
            ratio = cond[k] / uncond[k] if uncond[k] > 0 else float("inf")
            print(f"    {k:>6}  {cond[k]:>10.3f}  {uncond[k]:>10.3f}  {ratio:>8.2f}x")

    # ---- 6. Per-day consistency ----
    print()
    print("=" * 60)
    print("6. PER-DAY CONSISTENCY (K=1000)")
    print("=" * 60)

    for label, trigger, target in pairs:
        print(f"\n  {label}:")
        day_results = per_day_breakdown(trigger, target, k=1000)
        for day, (prob, n) in day_results.items():
            print(f"    Day {day}: P(within 1000) = {prob:.3f}  (n={n})")

    # ---- 7. Actionability assessment ----
    print()
    print("=" * 60)
    print("7. ACTIONABILITY (100-tick observation delay)")
    print("=" * 60)
    print("  Question: If we see Mark 22 sell, can we act before Mark 67 buys?")
    print("  (We observe trades with 100-tick delay)")
    print()

    # After Mark 22 sells, what fraction of Mark 67 buys happen >100 ticks later?
    if len(valid_22_67) > 0:
        actionable = np.mean(valid_22_67 > 100)
        print(f"  Mark 22 sell → Mark 67 buy gaps > 100 ticks: {actionable:.1%}")
        actionable_1k = np.mean((valid_22_67 > 100) & (valid_22_67 <= 1000))
        print(f"  Mark 22 sell → Mark 67 buy gaps in (100, 1000]: {actionable_1k:.1%}")
        actionable_5k = np.mean((valid_22_67 > 100) & (valid_22_67 <= 5000))
        print(f"  Mark 22 sell → Mark 67 buy gaps in (100, 5000]: {actionable_5k:.1%}")
    print()

    # Also check: after Mark 49 sells (without simultaneous 67), time to 67
    m49_no_simul_67 = m49_sells[
        ~m49_sells.set_index(["day", "timestamp"]).index.isin(
            m67_buys.set_index(["day", "timestamp"]).index
        )
    ]
    gaps_49_to_67 = time_to_next(m49_no_simul_67, m67_buys)
    valid_49_67 = gaps_49_to_67[~np.isnan(gaps_49_to_67)]
    if len(valid_49_67) > 0:
        actionable = np.mean(valid_49_67 > 100)
        print(f"  Mark 49 sell (non-simul) → Mark 67 buy gaps > 100 ticks: {actionable:.1%}")
        print(f"  Median gap: {np.median(valid_49_67):.0f} ticks")


if __name__ == "__main__":
    main()
