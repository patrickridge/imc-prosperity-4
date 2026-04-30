"""H11: Bot ABSENCE as signal for VELVETFRUIT_EXTRACT.

Tests whether extended silence from signal bots predicts VE price behavior.
"""

import pandas as pd
import numpy as np
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data" / "round4"

SIGNAL_BOTS = ["Mark 67", "Mark 49", "Mark 22"]
PRODUCT = "VELVETFRUIT_EXTRACT"
TICK_MAX = 1_000_000  # end of day


def load_data():
    prices_frames = []
    trades_frames = []
    for day in range(1, 4):
        p = pd.read_csv(DATA_DIR / f"prices_round_4_day_{day}.csv", sep=";")
        prices_frames.append(p)

        t = pd.read_csv(DATA_DIR / f"trades_round_4_day_{day}.csv", sep=";")
        t["day"] = day
        trades_frames.append(t)

    prices = pd.concat(prices_frames, ignore_index=True)
    trades = pd.concat(trades_frames, ignore_index=True)
    return prices, trades


def get_ve_mid(prices):
    ve = prices[prices["product"] == PRODUCT][["day", "timestamp", "mid_price"]].copy()
    ve = ve.sort_values(["day", "timestamp"]).reset_index(drop=True)
    return ve


def get_bot_trades(trades, bot):
    """Get all VE trades where bot is buyer or seller."""
    ve_trades = trades[trades["symbol"] == PRODUCT]
    mask = (ve_trades["buyer"] == bot) | (ve_trades["seller"] == bot)
    bot_trades = ve_trades[mask][["day", "timestamp", "buyer", "seller", "price", "quantity"]].copy()
    bot_trades = bot_trades.sort_values(["day", "timestamp"]).reset_index(drop=True)
    return bot_trades


def compute_gaps(bot_trades):
    """Compute inter-trade gaps per day."""
    gaps = []
    for day, group in bot_trades.groupby("day"):
        times = group["timestamp"].values
        if len(times) < 2:
            continue
        day_gaps = np.diff(times)
        for g in day_gaps:
            gaps.append({"day": day, "gap": g})
    return pd.DataFrame(gaps)


def forward_drift(ve_mid, day, timestamp, horizon=5000):
    """Compute price change from timestamp to timestamp + horizon."""
    day_mid = ve_mid[ve_mid["day"] == day]
    current = day_mid[day_mid["timestamp"] <= timestamp]["mid_price"]
    future = day_mid[day_mid["timestamp"] <= timestamp + horizon]["mid_price"]
    if current.empty or future.empty:
        return np.nan
    return future.iloc[-1] - current.iloc[-1]


def main():
    prices, trades = load_data()
    ve_mid = get_ve_mid(prices)

    print("=" * 60)
    print("H11: BOT ABSENCE AS SIGNAL FOR VELVETFRUIT_EXTRACT")
    print("=" * 60)

    # --- Section 1: Compute gap stats and 75th percentile ---
    print("\n--- Gap statistics (ticks) ---")
    gap_p75 = {}
    for bot in SIGNAL_BOTS:
        bot_trades = get_bot_trades(trades, bot)
        gaps = compute_gaps(bot_trades)
        if gaps.empty:
            continue
        p75 = gaps["gap"].quantile(0.75)
        gap_p75[bot] = p75
        print(f"  {bot}: median={gaps['gap'].median():.0f}, "
              f"p75={p75:.0f}, mean={gaps['gap'].mean():.0f}, n={len(gaps)}")

    # --- Section 2: Price behavior during extended silence ---
    print("\n--- Section 1: Price drift during SILENCE vs RECENT trade ---")
    HORIZON = 5000  # look-ahead ticks
    SAMPLE_INTERVAL = 1000  # sample every N ticks

    for bot in SIGNAL_BOTS:
        bot_trades = get_bot_trades(trades, bot)
        p75 = gap_p75[bot]

        silent_drifts = []
        recent_drifts = []

        for day in range(1, 4):
            day_bt = bot_trades[bot_trades["day"] == day]["timestamp"].values
            day_mid = ve_mid[ve_mid["day"] == day]
            sample_times = np.arange(0, TICK_MAX, SAMPLE_INTERVAL)

            for t in sample_times:
                # Time since last bot trade
                past_trades = day_bt[day_bt <= t]
                if len(past_trades) == 0:
                    time_since = t  # no trade yet
                else:
                    time_since = t - past_trades[-1]

                drift = forward_drift(ve_mid, day, t, HORIZON)
                if np.isnan(drift):
                    continue

                if time_since > p75:
                    silent_drifts.append(drift)
                elif time_since < 5000:
                    recent_drifts.append(drift)

        silent_mean = np.mean(silent_drifts) if silent_drifts else np.nan
        recent_mean = np.mean(recent_drifts) if recent_drifts else np.nan
        print(f"  {bot}: silence(>{p75:.0f}t) drift={silent_mean:+.3f} (n={len(silent_drifts)}), "
              f"recent(<5kt) drift={recent_mean:+.3f} (n={len(recent_drifts)})")

    # --- Section 3: Post-silence first trade impact ---
    print("\n--- Section 2: Post-silence FIRST TRADE impact ---")
    for bot in SIGNAL_BOTS:
        bot_trades = get_bot_trades(trades, bot)
        p75 = gap_p75[bot]

        normal_impacts = []
        post_silence_impacts = []

        for day in range(1, 4):
            day_bt = bot_trades[bot_trades["day"] == day].sort_values("timestamp")
            times = day_bt["timestamp"].values
            if len(times) < 2:
                continue

            gaps_arr = np.diff(times)
            for i, gap in enumerate(gaps_arr):
                t = times[i + 1]
                impact = forward_drift(ve_mid, day, t, HORIZON)
                if np.isnan(impact):
                    continue
                # Determine direction sign based on bot side
                row = day_bt.iloc[i + 1]
                side_sign = 1 if row["buyer"] == bot else -1
                signed_impact = impact * side_sign

                if gap > p75:
                    post_silence_impacts.append(signed_impact)
                else:
                    normal_impacts.append(signed_impact)

        normal_mean = np.mean(normal_impacts) if normal_impacts else np.nan
        silence_mean = np.mean(post_silence_impacts) if post_silence_impacts else np.nan
        print(f"  {bot}: normal impact={normal_mean:+.3f} (n={len(normal_impacts)}), "
              f"post-silence impact={silence_mean:+.3f} (n={len(post_silence_impacts)})")

    # --- Section 4: Mark 67 silence as bearish signal ---
    print("\n--- Section 3: Mark 67 silence as BEARISH signal ---")
    SILENCE_THRESHOLD = 20000
    RECENT_THRESHOLD = 5000
    bot = "Mark 67"
    bot_trades = get_bot_trades(trades, bot)

    for horizon in [5000, 10000, 20000]:
        silent_drifts = []
        recent_drifts = []

        for day in range(1, 4):
            day_bt = bot_trades[bot_trades["day"] == day]["timestamp"].values
            sample_times = np.arange(0, TICK_MAX, SAMPLE_INTERVAL)

            for t in sample_times:
                past_trades = day_bt[day_bt <= t]
                if len(past_trades) == 0:
                    time_since = t
                else:
                    time_since = t - past_trades[-1]

                drift = forward_drift(ve_mid, day, t, horizon)
                if np.isnan(drift):
                    continue

                if time_since > SILENCE_THRESHOLD:
                    silent_drifts.append(drift)
                elif time_since < RECENT_THRESHOLD:
                    recent_drifts.append(drift)

        s_mean = np.mean(silent_drifts) if silent_drifts else np.nan
        r_mean = np.mean(recent_drifts) if recent_drifts else np.nan
        s_std = np.std(silent_drifts) / np.sqrt(len(silent_drifts)) if len(silent_drifts) > 1 else np.nan
        r_std = np.std(recent_drifts) / np.sqrt(len(recent_drifts)) if len(recent_drifts) > 1 else np.nan
        print(f"  horizon={horizon/1000:.0f}k: silence drift={s_mean:+.3f}+-{s_std:.3f} (n={len(silent_drifts)}), "
              f"recent drift={r_mean:+.3f}+-{r_std:.3f} (n={len(recent_drifts)})")

    # --- Section 5: Combined silence ---
    print("\n--- Section 4: COMBINED silence (all bots quiet) ---")
    COMBINED_THRESHOLDS = [10000, 20000, 30000]

    for thresh in COMBINED_THRESHOLDS:
        all_silent_drifts = []
        any_active_drifts = []

        for day in range(1, 4):
            bot_times = {}
            for bot in SIGNAL_BOTS:
                bt = get_bot_trades(trades, bot)
                bot_times[bot] = bt[bt["day"] == day]["timestamp"].values

            sample_times = np.arange(0, TICK_MAX, SAMPLE_INTERVAL)
            for t in sample_times:
                all_silent = True
                for bot in SIGNAL_BOTS:
                    past = bot_times[bot][bot_times[bot] <= t]
                    time_since = t - past[-1] if len(past) > 0 else t
                    if time_since < thresh:
                        all_silent = False
                        break

                drift = forward_drift(ve_mid, day, t, 5000)
                if np.isnan(drift):
                    continue

                if all_silent:
                    all_silent_drifts.append(drift)
                else:
                    any_active_drifts.append(drift)

        s_mean = np.mean(all_silent_drifts) if all_silent_drifts else np.nan
        a_mean = np.mean(any_active_drifts) if any_active_drifts else np.nan
        print(f"  thresh={thresh/1000:.0f}k: all-silent drift={s_mean:+.3f} (n={len(all_silent_drifts)}), "
              f"any-active drift={a_mean:+.3f} (n={len(any_active_drifts)})")

    # --- Section 6: Actionability ---
    print("\n--- Section 5: Actionability ---")
    print("  VE typical spread: ~5-6 ticks (ask - bid)")
    # Use Mark 67 silence > 20k as the signal
    bot = "Mark 67"
    bot_trades = get_bot_trades(trades, bot)

    horizons = [2000, 5000, 10000]
    for h in horizons:
        drifts_silent = []
        for day in range(1, 4):
            day_bt = bot_trades[bot_trades["day"] == day]["timestamp"].values
            sample_times = np.arange(0, TICK_MAX, SAMPLE_INTERVAL)
            for t in sample_times:
                past = day_bt[day_bt <= t]
                time_since = t - past[-1] if len(past) > 0 else t
                if time_since > SILENCE_THRESHOLD:
                    d = forward_drift(ve_mid, day, t, h)
                    if not np.isnan(d):
                        drifts_silent.append(d)

        if drifts_silent:
            mean_d = np.mean(drifts_silent)
            median_d = np.median(drifts_silent)
            pct_neg = np.mean(np.array(drifts_silent) < 0) * 100
            print(f"  Mark67 silent >20k, horizon {h/1000:.0f}k: "
                  f"mean={mean_d:+.3f}, median={median_d:+.3f}, "
                  f"pct_negative={pct_neg:.1f}%, n={len(drifts_silent)}")

    # --- Section 7: Per-day consistency ---
    print("\n--- Section 6: Per-day consistency (Mark 67, silence>20k, horizon=5k) ---")
    bot = "Mark 67"
    bot_trades = get_bot_trades(trades, bot)

    for day in range(1, 4):
        day_bt = bot_trades[bot_trades["day"] == day]["timestamp"].values
        drifts_silent = []
        drifts_recent = []
        sample_times = np.arange(0, TICK_MAX, SAMPLE_INTERVAL)

        for t in sample_times:
            past = day_bt[day_bt <= t]
            time_since = t - past[-1] if len(past) > 0 else t
            d = forward_drift(ve_mid, day, t, 5000)
            if np.isnan(d):
                continue
            if time_since > SILENCE_THRESHOLD:
                drifts_silent.append(d)
            elif time_since < RECENT_THRESHOLD:
                drifts_recent.append(d)

        s_mean = np.mean(drifts_silent) if drifts_silent else np.nan
        r_mean = np.mean(drifts_recent) if drifts_recent else np.nan
        print(f"  Day {day}: silence={s_mean:+.3f} (n={len(drifts_silent)}), "
              f"recent={r_mean:+.3f} (n={len(drifts_recent)})")

    print("\n" + "=" * 60)
    print("DONE")


if __name__ == "__main__":
    main()
