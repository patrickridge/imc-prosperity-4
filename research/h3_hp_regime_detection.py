"""H3: HP regime detection within the day.

Tests whether Mark 14/38 roles are consistent WITHIN each day,
even though they swap BETWEEN days. If so, early-period signals
can predict late-period behavior.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from scipy import stats

DATA_DIR = Path(__file__).parent.parent / "data" / "round4"
PRODUCT = "HYDROGEL_PACK"
BOTS = ["Mark 14", "Mark 38"]
HORIZONS = [1, 5, 10, 20]
SPLIT_FRACTIONS = [0.10, 0.15, 0.20, 0.25, 0.33, 0.50]
TICK_DELAY = 100


def load_mid_series():
    """Returns dict: day -> DataFrame(timestamp, mid_price) for HP."""
    result = {}
    for day in range(1, 4):
        path = DATA_DIR / f"prices_round_4_day_{day}.csv"
        df = pd.read_csv(path, sep=";")
        hp = df[df["product"] == PRODUCT][["timestamp", "mid_price"]].copy()
        hp = hp.sort_values("timestamp").reset_index(drop=True)
        result[day] = hp
    return result


def load_trades():
    """Returns all HP trades with day column, timestamp adjusted for tick delay."""
    frames = []
    for day in range(1, 4):
        path = DATA_DIR / f"trades_round_4_day_{day}.csv"
        df = pd.read_csv(path, sep=";")
        df["day"] = day
        frames.append(df)
    trades = pd.concat(frames, ignore_index=True)
    trades = trades[trades["symbol"] == PRODUCT].copy()
    # market_trades at timestamp T are from T-100
    trades["actual_timestamp"] = trades["timestamp"] - TICK_DELAY
    return trades


def bot_direction(trades, bot_name):
    """For each trade, assign direction for the given bot: +1 if buyer, -1 if seller."""
    is_buyer = trades["buyer"] == bot_name
    is_seller = trades["seller"] == bot_name
    involved = is_buyer | is_seller
    direction = pd.Series(0, index=trades.index)
    direction[is_buyer] = 1
    direction[is_seller] = -1
    return direction, involved


def compute_signed_impact(trades_day, mid_df, bot_name, horizons):
    """Compute signed price impact for a bot's trades on a single day.

    Returns DataFrame with columns: timestamp, direction, impact_1, impact_5, etc.
    """
    direction, involved = bot_direction(trades_day, bot_name)
    bot_trades = trades_day[involved].copy()
    bot_trades["direction"] = direction[involved].values

    mid_ts = mid_df["timestamp"].values
    mid_vals = mid_df["mid_price"].values

    rows = []
    for _, trade in bot_trades.iterrows():
        t_actual = trade["actual_timestamp"]

        # Find mid at trade time (latest mid <= actual_timestamp)
        idx_now = np.searchsorted(mid_ts, t_actual, side="right") - 1
        if idx_now < 0:
            continue
        mid_now = mid_vals[idx_now]

        impact_row = {
            "timestamp": trade["actual_timestamp"],
            "direction": trade["direction"],
            "mid_now": mid_now,
        }

        for h in horizons:
            future_t = t_actual + h * TICK_DELAY
            idx_future = np.searchsorted(mid_ts, future_t, side="right") - 1
            if idx_future < 0 or idx_future >= len(mid_ts):
                impact_row[f"impact_{h}"] = np.nan
            else:
                future_mid = mid_vals[idx_future]
                signed_impact = trade["direction"] * (future_mid - mid_now)
                impact_row[f"impact_{h}"] = signed_impact

        rows.append(impact_row)

    return pd.DataFrame(rows)


def impact_stats(impacts, horizon):
    """Mean, t-stat, p-value, N for a given horizon's impact column."""
    col = f"impact_{horizon}"
    vals = impacts[col].dropna()
    n = len(vals)
    if n < 3:
        return {"mean": np.nan, "t_stat": np.nan, "p_value": np.nan, "n": n}
    mean = vals.mean()
    t_stat, p_value = stats.ttest_1samp(vals, 0)
    return {"mean": round(mean, 4), "t_stat": round(t_stat, 3), "p_value": round(p_value, 4), "n": n}


def section(title):
    bar = "=" * 70
    print(f"\n{bar}")
    print(f"  {title}")
    print(bar)


def main():
    mid_by_day = load_mid_series()
    trades = load_trades()

    section("1. ALL BOTS TRADING HP (per day)")
    for day in range(1, 4):
        day_trades = trades[trades["day"] == day]
        buyers = day_trades.groupby("buyer")["quantity"].agg(["sum", "count"])
        sellers = day_trades.groupby("seller")["quantity"].agg(["sum", "count"])
        buyers.columns = ["buy_qty", "buy_count"]
        sellers.columns = ["sell_qty", "sell_count"]
        combined = buyers.join(sellers, how="outer").fillna(0).astype(int)
        combined["total_trades"] = combined["buy_count"] + combined["sell_count"]
        combined = combined.sort_values("total_trades", ascending=False)
        print(f"\nDay {day}:")
        print(combined.to_string())

    section("2. PER-DAY SIGNED IMPACT (full day, all horizons)")
    full_day_impacts = {}  # (day, bot) -> impact DataFrame
    for day in range(1, 4):
        day_trades = trades[trades["day"] == day]
        mid_df = mid_by_day[day]
        print(f"\nDay {day}:")
        for bot in BOTS:
            impacts = compute_signed_impact(day_trades, mid_df, bot, HORIZONS)
            full_day_impacts[(day, bot)] = impacts
            row_parts = [f"  {bot:8s}:"]
            for h in HORIZONS:
                s = impact_stats(impacts, h)
                row_parts.append(
                    f"  t+{h:2d}: mean={s['mean']:+.4f}  t={s['t_stat']:+.3f}  p={s['p_value']:.4f}  N={s['n']}"
                )
            print("\n".join(row_parts))

    section("3. REGIME DETECTION: EARLY vs LATE PERIOD")

    for split_frac in SPLIT_FRACTIONS:
        print(f"\n--- Split: first {split_frac*100:.0f}% early, rest late ---")

        regime_predictions = []

        for day in range(1, 4):
            day_trades = trades[trades["day"] == day]
            mid_df = mid_by_day[day]
            all_timestamps = sorted(day_trades["actual_timestamp"].unique())
            split_ts = all_timestamps[int(len(all_timestamps) * split_frac)]

            print(f"\n  Day {day} (split at ts={split_ts}):")

            early_means = {}
            late_means = {}

            for bot in BOTS:
                impacts = full_day_impacts[(day, bot)]
                early = impacts[impacts["timestamp"] <= split_ts]
                late = impacts[impacts["timestamp"] > split_ts]

                # Use t+5 as primary horizon for regime detection
                early_s = impact_stats(early, 5)
                late_s = impact_stats(late, 5)

                early_means[bot] = early_s["mean"]
                late_means[bot] = late_s["mean"]

                print(f"    {bot:8s} EARLY: mean={early_s['mean']:+.4f}  t={early_s['t_stat']:+.3f}  N={early_s['n']}")
                print(f"    {bot:8s} LATE:  mean={late_s['mean']:+.4f}  t={late_s['t_stat']:+.3f}  N={late_s['n']}")

            # Regime indicator: who is "smarter" in early period?
            early_14 = early_means.get("Mark 14", 0) or 0
            early_38 = early_means.get("Mark 38", 0) or 0
            late_14 = late_means.get("Mark 14", 0) or 0
            late_38 = late_means.get("Mark 38", 0) or 0

            early_signal = "Mark 14" if early_14 > early_38 else "Mark 38"
            late_smart = "Mark 14" if late_14 > late_38 else "Mark 38"
            match = early_signal == late_smart

            regime_predictions.append(match)
            print(f"    EARLY signal: {early_signal} smarter  |  LATE actual: {late_smart} smarter  |  MATCH: {match}")

        accuracy = sum(regime_predictions) / len(regime_predictions)
        print(f"\n  Regime prediction accuracy at {split_frac*100:.0f}% split: {accuracy:.1%} ({sum(regime_predictions)}/3)")

    section("4. REGIME CONSISTENCY ACROSS ALL HORIZONS (25% split)")

    SPLIT = 0.25
    for day in range(1, 4):
        day_trades = trades[trades["day"] == day]
        mid_df = mid_by_day[day]
        all_timestamps = sorted(day_trades["actual_timestamp"].unique())
        split_ts = all_timestamps[int(len(all_timestamps) * SPLIT)]

        print(f"\nDay {day} (split at ts={split_ts}):")
        for bot in BOTS:
            impacts = full_day_impacts[(day, bot)]
            early = impacts[impacts["timestamp"] <= split_ts]
            late = impacts[impacts["timestamp"] > split_ts]

            parts = [f"  {bot:8s}:"]
            for h in HORIZONS:
                e = impact_stats(early, h)
                l = impact_stats(late, h)
                sign_match = "YES" if (e["mean"] > 0) == (l["mean"] > 0) else "NO"
                parts.append(
                    f"    t+{h:2d}: early={e['mean']:+.4f}(N={e['n']})  late={l['mean']:+.4f}(N={l['n']})  same_sign={sign_match}"
                )
            print("\n".join(parts))

    section("5. EARLY-LATE IMPACT CORRELATION (signed impact at t+5)")

    print("\nFor each split fraction, do early and late signed impacts correlate")
    print("within the same bot on the same day?\n")

    for split_frac in [0.25, 0.33, 0.50]:
        print(f"--- Split: {split_frac*100:.0f}% ---")
        for day in range(1, 4):
            day_trades = trades[trades["day"] == day]
            all_timestamps = sorted(day_trades["actual_timestamp"].unique())
            split_ts = all_timestamps[int(len(all_timestamps) * split_frac)]

            for bot in BOTS:
                impacts = full_day_impacts[(day, bot)]
                early = impacts[impacts["timestamp"] <= split_ts]["impact_5"].dropna()
                late = impacts[impacts["timestamp"] > split_ts]["impact_5"].dropna()

                early_mean = early.mean() if len(early) > 0 else np.nan
                late_mean = late.mean() if len(late) > 0 else np.nan
                print(f"  Day {day} {bot:8s}: early_mean={early_mean:+.4f} (N={len(early)})  late_mean={late_mean:+.4f} (N={len(late)})")
        print()

    section("6. SUMMARY VERDICT")

    print("\nPer-day role assignments (based on t+5 full-day signed impact):")
    for day in range(1, 4):
        m14 = impact_stats(full_day_impacts[(day, "Mark 14")], 5)
        m38 = impact_stats(full_day_impacts[(day, "Mark 38")], 5)
        smart = "Mark 14" if m14["mean"] > m38["mean"] else "Mark 38"
        m14_sig = "*" if m14["p_value"] < 0.05 else ""
        m38_sig = "*" if m38["p_value"] < 0.05 else ""
        print(f"  Day {day}: Mark14={m14['mean']:+.4f}{m14_sig}  Mark38={m38['mean']:+.4f}{m38_sig}  -> smart={smart}")

    print("\nRegime prediction accuracy across split points (t+5):")
    for split_frac in SPLIT_FRACTIONS:
        predictions = []
        for day in range(1, 4):
            day_trades = trades[trades["day"] == day]
            all_timestamps = sorted(day_trades["actual_timestamp"].unique())
            split_ts = all_timestamps[int(len(all_timestamps) * split_frac)]

            results = {}
            for bot in BOTS:
                impacts = full_day_impacts[(day, bot)]
                early = impacts[impacts["timestamp"] <= split_ts]
                late = impacts[impacts["timestamp"] > split_ts]
                results[("early", bot)] = impact_stats(early, 5)["mean"] or 0
                results[("late", bot)] = impact_stats(late, 5)["mean"] or 0

            early_smart = "Mark 14" if results[("early", "Mark 14")] > results[("early", "Mark 38")] else "Mark 38"
            late_smart = "Mark 14" if results[("late", "Mark 14")] > results[("late", "Mark 38")] else "Mark 38"
            predictions.append(early_smart == late_smart)

        acc = sum(predictions) / len(predictions)
        print(f"  {split_frac*100:4.0f}%: {acc:.0%} ({sum(predictions)}/3)  {predictions}")


if __name__ == "__main__":
    main()
