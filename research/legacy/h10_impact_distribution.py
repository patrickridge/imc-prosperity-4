"""H10: Impact distribution and tail event prediction for VE signal bots.

Examines whether Mark 67/49/22 trades predict tail moves, not just mean impact.
"""

import pandas as pd
import numpy as np
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data" / "round4"
PRODUCT = "VELVETFRUIT_EXTRACT"
SIGNAL_BOTS = {"Mark 67": "BUY", "Mark 49": "SELL", "Mark 22": "SELL"}
HORIZONS = [1, 5, 10, 20]
TAIL_THRESHOLDS = [5, 10, 15, 20]
OBSERVATION_DELAY = 100


def load_mid_series():
    """Load mid prices as (day, timestamp) -> mid_price for VE."""
    frames = []
    for day in range(1, 4):
        path = DATA_DIR / f"prices_round_4_day_{day}.csv"
        df = pd.read_csv(path, sep=";")
        df = df[df["product"] == PRODUCT][["day", "timestamp", "mid_price"]]
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def load_bot_trades():
    """Load VE trades involving signal bots, with their directional side."""
    frames = []
    for day in range(1, 4):
        path = DATA_DIR / f"trades_round_4_day_{day}.csv"
        df = pd.read_csv(path, sep=";")
        df["day"] = day
        df = df[df["symbol"] == PRODUCT]
        frames.append(df)
    trades = pd.concat(frames, ignore_index=True)

    rows = []
    for _, t in trades.iterrows():
        if t["buyer"] in SIGNAL_BOTS:
            rows.append({
                "day": t["day"],
                "timestamp": t["timestamp"],
                "bot": t["buyer"],
                "side": "BUY",
                "price": t["price"],
                "quantity": t["quantity"],
            })
        if t["seller"] in SIGNAL_BOTS:
            rows.append({
                "day": t["day"],
                "timestamp": t["timestamp"],
                "bot": t["seller"],
                "side": "SELL",
                "price": t["price"],
                "quantity": t["quantity"],
            })
    return pd.DataFrame(rows)


def get_mid_at(mids_df, day, timestamp):
    """Get mid price at or just before timestamp."""
    day_mids = mids_df[mids_df["day"] == day]
    valid = day_mids[day_mids["timestamp"] <= timestamp]
    if valid.empty:
        return np.nan
    return valid.iloc[-1]["mid_price"]


def get_mid_at_vectorized(mids_df, day, timestamps):
    """Vectorized mid lookup using merge_asof."""
    day_mids = mids_df[mids_df["day"] == day].sort_values("timestamp")
    query = pd.DataFrame({"timestamp": sorted(timestamps)})
    merged = pd.merge_asof(query, day_mids, on="timestamp", direction="backward")
    return dict(zip(merged["timestamp"], merged["mid_price"]))


def compute_signed_impacts(bot_trades, mids_df):
    """Compute signed impact at each horizon for each bot trade.

    Signed impact = (mid[t+h] - mid[t]) * sign, where sign=+1 for BUY, -1 for SELL.
    Uses trade timestamp (not observation time).
    """
    results = []
    for day in range(1, 4):
        day_mids = mids_df[mids_df["day"] == day].sort_values("timestamp").reset_index(drop=True)
        day_trades = bot_trades[bot_trades["day"] == day]

        for _, trade in day_trades.iterrows():
            t = trade["timestamp"]
            sign = 1 if trade["side"] == "BUY" else -1

            # Mid at trade time
            mask_base = day_mids["timestamp"] <= t
            if not mask_base.any():
                continue
            mid_base = day_mids.loc[mask_base, "mid_price"].iloc[-1]

            row = {"day": day, "timestamp": t, "bot": trade["bot"], "side": trade["side"]}

            for h in HORIZONS:
                target_ts = t + h * 100  # timestamps are in 100-unit steps
                mask_h = day_mids["timestamp"] <= target_ts
                if not mask_h.any():
                    row[f"impact_{h}"] = np.nan
                    continue
                mid_h = day_mids.loc[mask_h, "mid_price"].iloc[-1]
                row[f"impact_{h}"] = (mid_h - mid_base) * sign

            # Also compute from observation time (t + OBSERVATION_DELAY)
            obs_ts = t + OBSERVATION_DELAY
            mask_obs = day_mids["timestamp"] <= obs_ts
            if not mask_obs.any():
                mid_obs = mid_base
            else:
                mid_obs = day_mids.loc[mask_obs, "mid_price"].iloc[-1]

            for h in HORIZONS:
                target_ts = obs_ts + h * 100
                mask_h = day_mids["timestamp"] <= target_ts
                if not mask_h.any():
                    row[f"post_obs_impact_{h}"] = np.nan
                    continue
                mid_h = day_mids.loc[mask_h, "mid_price"].iloc[-1]
                row[f"post_obs_impact_{h}"] = (mid_h - mid_obs) * sign

            results.append(row)

    return pd.DataFrame(results)


def compute_unconditional_moves(mids_df):
    """Compute unconditional distribution of |price changes| at each horizon."""
    results = {h: [] for h in HORIZONS}
    for day in range(1, 4):
        day_mids = mids_df[mids_df["day"] == day].sort_values("timestamp").reset_index(drop=True)
        prices = day_mids["mid_price"].values
        timestamps = day_mids["timestamp"].values

        for i in range(len(prices)):
            for h in HORIZONS:
                target_ts = timestamps[i] + h * 100
                # Find closest timestamp <= target
                j = np.searchsorted(timestamps, target_ts, side="right") - 1
                if j > i and j < len(prices):
                    results[h].append(prices[j] - prices[i])

    return {h: np.array(v) for h, v in results.items()}


def print_section(title):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")


def main():
    print("Loading data...")
    mids_df = load_mid_series()
    bot_trades = load_bot_trades()

    print(f"VE mid prices: {len(mids_df)} rows across 3 days")
    print(f"Signal bot trades: {len(bot_trades)} trades")
    print(f"  Mark 67: {len(bot_trades[bot_trades['bot'] == 'Mark 67'])} trades")
    print(f"  Mark 49: {len(bot_trades[bot_trades['bot'] == 'Mark 49'])} trades")
    print(f"  Mark 22: {len(bot_trades[bot_trades['bot'] == 'Mark 22'])} trades")

    print("\nComputing signed impacts...")
    impacts = compute_signed_impacts(bot_trades, mids_df)

    print("Computing unconditional moves...")
    uncond_moves = compute_unconditional_moves(mids_df)

    # =========================================================================
    # 1. Full distribution of signed impact (percentiles)
    # =========================================================================
    print_section("1. SIGNED IMPACT DISTRIBUTION (from trade time)")

    percentiles = [5, 10, 25, 50, 75, 90, 95]
    for bot in SIGNAL_BOTS:
        bot_data = impacts[impacts["bot"] == bot]
        if bot_data.empty:
            continue
        print(f"\n  {bot} ({SIGNAL_BOTS[bot]}er, n={len(bot_data)}):")
        print(f"  {'Horizon':<10}", end="")
        for p in percentiles:
            print(f"{'p'+str(p):>8}", end="")
        print(f"{'mean':>8}{'std':>8}")

        for h in HORIZONS:
            col = f"impact_{h}"
            vals = bot_data[col].dropna()
            print(f"  t+{h:<7}", end="")
            for p in percentiles:
                print(f"{np.percentile(vals, p):>8.1f}", end="")
            print(f"{vals.mean():>8.1f}{vals.std():>8.1f}")

    # =========================================================================
    # 2. Tail event prediction (from trade time)
    # =========================================================================
    print_section("2. TAIL EVENT PREDICTION (from trade time)")
    print("  P(move > X ticks in signal direction | bot trade) vs unconditional P(|move| > X)")

    for bot in SIGNAL_BOTS:
        bot_data = impacts[impacts["bot"] == bot]
        if bot_data.empty:
            continue
        print(f"\n  {bot} (n={len(bot_data)}):")
        print(f"  {'Horizon':<10}{'Thresh':<8}{'P(cond)':<12}{'P(uncond)':<12}{'Ratio':<8}")

        for h in HORIZONS:
            col = f"impact_{h}"
            vals = bot_data[col].dropna().values
            uncond = uncond_moves[h]

            for x in TAIL_THRESHOLDS:
                p_cond = np.mean(vals > x) if len(vals) > 0 else 0
                p_uncond = np.mean(np.abs(uncond) > x) if len(uncond) > 0 else 0
                ratio = p_cond / p_uncond if p_uncond > 0 else np.inf
                print(f"  t+{h:<7}{x:<8}{p_cond:<12.3f}{p_uncond:<12.3f}{ratio:<8.2f}")

    # =========================================================================
    # 3. Post-observation tail prediction
    # =========================================================================
    print_section("3. POST-OBSERVATION TAIL PREDICTION (from obs time = trade + 100)")
    print("  P(move > X in signal dir | observed bot trade) vs unconditional")

    for bot in SIGNAL_BOTS:
        bot_data = impacts[impacts["bot"] == bot]
        if bot_data.empty:
            continue
        print(f"\n  {bot} (n={len(bot_data)}):")
        print(f"  {'Horizon':<10}{'Thresh':<8}{'P(cond)':<12}{'P(uncond)':<12}{'Ratio':<8}")

        for h in HORIZONS:
            col = f"post_obs_impact_{h}"
            vals = bot_data[col].dropna().values
            uncond = uncond_moves[h]

            for x in TAIL_THRESHOLDS:
                p_cond = np.mean(vals > x) if len(vals) > 0 else 0
                p_uncond = np.mean(np.abs(uncond) > x) if len(uncond) > 0 else 0
                ratio = p_cond / p_uncond if p_uncond > 0 else np.inf
                print(f"  t+{h:<7}{x:<8}{p_cond:<12.3f}{p_uncond:<12.3f}{ratio:<8.2f}")

    # =========================================================================
    # 4. Conditional tail ratio summary
    # =========================================================================
    print_section("4. CONDITIONAL TAIL RATIO SUMMARY (best opportunities)")
    print("  Cases where ratio > 1.5 (post-observation):")
    print(f"  {'Bot':<10}{'Horizon':<10}{'Thresh':<8}{'P(cond)':<12}{'Ratio':<8}")

    for bot in SIGNAL_BOTS:
        bot_data = impacts[impacts["bot"] == bot]
        if bot_data.empty:
            continue
        for h in HORIZONS:
            col = f"post_obs_impact_{h}"
            vals = bot_data[col].dropna().values
            uncond = uncond_moves[h]
            for x in TAIL_THRESHOLDS:
                p_cond = np.mean(vals > x) if len(vals) > 0 else 0
                p_uncond = np.mean(np.abs(uncond) > x) if len(uncond) > 0 else 0
                ratio = p_cond / p_uncond if p_uncond > 0 else np.inf
                if ratio > 1.5 and p_cond > 0.05:
                    print(f"  {bot:<10}t+{h:<8}{x:<8}{p_cond:<12.3f}{ratio:<8.2f}")

    # =========================================================================
    # 5. Per-day consistency
    # =========================================================================
    print_section("5. PER-DAY CONSISTENCY (post-obs, threshold=10 ticks)")

    for bot in SIGNAL_BOTS:
        bot_data = impacts[impacts["bot"] == bot]
        if bot_data.empty:
            continue
        print(f"\n  {bot}:")
        print(f"  {'Day':<6}{'Horizon':<10}{'n':<6}{'P(>10)':<10}{'Mean':<10}")

        for day in range(1, 4):
            day_data = bot_data[bot_data["day"] == day]
            for h in HORIZONS:
                col = f"post_obs_impact_{h}"
                vals = day_data[col].dropna().values
                if len(vals) == 0:
                    continue
                p_tail = np.mean(vals > 10)
                mean_val = np.mean(vals)
                print(f"  {day:<6}t+{h:<8}{len(vals):<6}{p_tail:<10.3f}{mean_val:<10.1f}")

    # =========================================================================
    # 6. Practical implication
    # =========================================================================
    print_section("6. PRACTICAL IMPLICATION")

    # Focus on Mark 67 post-observation, best horizon
    bot = "Mark 67"
    bot_data = impacts[impacts["bot"] == bot]
    if not bot_data.empty:
        print(f"\n  Mark 67 (smart buyer) post-observation profile:")
        for h in HORIZONS:
            col = f"post_obs_impact_{h}"
            vals = bot_data[col].dropna().values
            if len(vals) == 0:
                continue
            mean_imp = np.mean(vals)
            p_pos = np.mean(vals > 0)
            p_5 = np.mean(vals > 5)
            p_10 = np.mean(vals > 10)
            p_15 = np.mean(vals > 15)
            p_20 = np.mean(vals > 20)
            print(f"  t+{h}: mean={mean_imp:.1f}, P(>0)={p_pos:.2f}, "
                  f"P(>5)={p_5:.2f}, P(>10)={p_10:.2f}, "
                  f"P(>15)={p_15:.2f}, P(>20)={p_20:.2f}")

    # Check if distribution is symmetric
    print(f"\n  Distribution symmetry check (skewness of post-obs impacts):")
    for bot in SIGNAL_BOTS:
        bot_data = impacts[impacts["bot"] == bot]
        if bot_data.empty:
            continue
        for h in [5, 20]:
            col = f"post_obs_impact_{h}"
            vals = bot_data[col].dropna().values
            if len(vals) < 5:
                continue
            skew = pd.Series(vals).skew()
            kurt = pd.Series(vals).kurtosis()
            print(f"  {bot} t+{h}: skew={skew:.2f}, excess_kurtosis={kurt:.2f}")


if __name__ == "__main__":
    main()
