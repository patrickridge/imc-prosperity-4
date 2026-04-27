"""H4: Cumulative bot inventory as a leading indicator on VELVETFRUIT_EXTRACT.

Tests whether Mark 67 (smart buyer), Mark 49 / Mark 22 (dumb sellers)
accumulate directional inventory, and whether cumulative position predicts
larger future price moves than individual trades.
"""

import pandas as pd
import numpy as np
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data" / "round4"
PRODUCT = "VELVETFRUIT_EXTRACT"
BOTS = ["Mark 67", "Mark 49", "Mark 22"]
DAYS = [1, 2, 3]

INVENTORY_QUARTILE_BINS = [0, 50, 100, 200, 350, 600]
INVENTORY_QUARTILE_LABELS = ["Q1: 0-50", "Q2: 50-100", "Q3: 100-200", "Q4: 200-350", "Q5: 350-600"]

FORWARD_HORIZONS = [1, 5, 10, 20]


def load_all_trades():
    frames = []
    for day in DAYS:
        path = DATA_DIR / f"trades_round_4_day_{day}.csv"
        df = pd.read_csv(path, sep=";")
        df["day"] = day
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def load_all_prices():
    frames = []
    for day in DAYS:
        path = DATA_DIR / f"prices_round_4_day_{day}.csv"
        df = pd.read_csv(path, sep=";")
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def get_ve_mid_series(prices):
    """Returns dict: day -> (timestamps_array, mids_array), sorted by timestamp."""
    ve = prices[prices["product"] == PRODUCT].sort_values(["day", "timestamp"])
    result = {}
    for day, group in ve.groupby("day"):
        result[day] = (group["timestamp"].values, group["mid_price"].values)
    return result


def get_ve_trades(trades):
    return trades[trades["symbol"] == PRODUCT].copy()


def build_bot_positions(ve_trades):
    """For each bot, build cumulative position trajectory per day.

    Returns DataFrame with columns:
        day, timestamp, bot, trade_qty (signed), cumulative_position
    """
    rows = []
    for day in DAYS:
        day_trades = ve_trades[ve_trades["day"] == day].sort_values("timestamp")
        for bot in BOTS:
            cumulative = 0
            bot_buys = day_trades[day_trades["buyer"] == bot]
            bot_sells = day_trades[day_trades["seller"] == bot]

            # Merge buys and sells into signed trade events
            events = []
            for _, row in bot_buys.iterrows():
                events.append((row["timestamp"], +row["quantity"]))
            for _, row in bot_sells.iterrows():
                events.append((row["timestamp"], -row["quantity"]))

            events.sort(key=lambda x: x[0])

            for ts, signed_qty in events:
                cumulative += signed_qty
                rows.append({
                    "day": day,
                    "timestamp": ts,
                    "bot": bot,
                    "trade_qty": signed_qty,
                    "cumulative_position": cumulative,
                })

    return pd.DataFrame(rows)


def get_mid_at(ts, timestamps, mids):
    """Interpolate mid price at given timestamp."""
    return np.interp(ts, timestamps, mids)


def compute_forward_returns(positions_df, mid_series):
    """Attach forward price changes at each trade event.

    mid_series: dict day -> (timestamps, mids)
    """
    for h in FORWARD_HORIZONS:
        positions_df[f"fwd_{h}"] = np.nan

    positions_df["mid_at_trade"] = np.nan

    for day in DAYS:
        timestamps, mids = mid_series[day]
        day_mask = positions_df["day"] == day

        for idx in positions_df[day_mask].index:
            ts = positions_df.loc[idx, "timestamp"]
            mid_now = get_mid_at(ts, timestamps, mids)
            positions_df.loc[idx, "mid_at_trade"] = mid_now

            for h in FORWARD_HORIZONS:
                future_ts = ts + h * 100
                if future_ts <= timestamps[-1]:
                    mid_future = get_mid_at(future_ts, timestamps, mids)
                    positions_df.loc[idx, f"fwd_{h}"] = mid_future - mid_now

    return positions_df


def print_position_trajectories(positions_df):
    """Print position trajectory summary per bot per day."""
    print("=" * 70)
    print("  POSITION TRAJECTORIES")
    print("=" * 70)

    for bot in BOTS:
        bot_data = positions_df[positions_df["bot"] == bot]
        print(f"\n  {bot}")
        print(f"  {'Day':>4} {'Trades':>7} {'Final Pos':>10} {'Max Pos':>9} {'Min Pos':>9}")
        print(f"  {'-'*43}")

        for day in DAYS:
            day_data = bot_data[bot_data["day"] == day]
            if day_data.empty:
                print(f"  {day:>4} {'(no trades)':>7}")
                continue
            final = day_data["cumulative_position"].iloc[-1]
            max_pos = day_data["cumulative_position"].max()
            min_pos = day_data["cumulative_position"].min()
            n_trades = len(day_data)
            print(f"  {day:>4} {n_trades:>7} {final:>+10.0f} {max_pos:>+9.0f} {min_pos:>+9.0f}")

        # Print detailed trajectory snapshots (every ~20% of day)
        print(f"\n  Trajectory snapshots (timestamp, cumulative_position):")
        for day in DAYS:
            day_data = bot_data[bot_data["day"] == day]
            if day_data.empty:
                continue
            n = len(day_data)
            sample_indices = [0, n // 4, n // 2, 3 * n // 4, n - 1]
            sample_indices = sorted(set(min(i, n - 1) for i in sample_indices))
            snapshots = day_data.iloc[sample_indices]
            points = [f"({int(r['timestamp']):>7d}, {r['cumulative_position']:>+4.0f})"
                      for _, r in snapshots.iterrows()]
            print(f"    Day {day}: {' -> '.join(points)}")


def print_signed_impact_by_quartile(positions_df):
    """Split trades by abs(cumulative_position) quartile.

    Signed impact: trade_qty_sign * forward_return.
    """
    print("\n" + "=" * 70)
    print("  SIGNAL STRENGTH BY INVENTORY QUARTILE")
    print("  (signed impact = sign(trade) * forward_return)")
    print("=" * 70)

    positions_df = positions_df.copy()
    positions_df["abs_position"] = positions_df["cumulative_position"].abs()
    positions_df["trade_sign"] = np.sign(positions_df["trade_qty"])
    positions_df["inv_quartile"] = pd.cut(
        positions_df["abs_position"],
        bins=INVENTORY_QUARTILE_BINS,
        labels=INVENTORY_QUARTILE_LABELS,
        include_lowest=True,
        right=True,
    )

    for bot in BOTS:
        bot_data = positions_df[positions_df["bot"] == bot].copy()
        print(f"\n  {bot}")
        header = f"  {'Quartile':>16} {'N':>5}"
        for h in FORWARD_HORIZONS:
            header += f" {'t+'+str(h):>9}"
        print(header)
        print(f"  {'-'*55}")

        for q in INVENTORY_QUARTILE_LABELS:
            q_data = bot_data[bot_data["inv_quartile"] == q]
            n = len(q_data)
            line = f"  {q:>16} {n:>5}"
            for h in FORWARD_HORIZONS:
                col = f"fwd_{h}"
                vals = q_data["trade_sign"] * q_data[col]
                vals = vals.dropna()
                if len(vals) < 2:
                    line += f" {'n/a':>9}"
                else:
                    mean = vals.mean()
                    se = vals.std() / np.sqrt(len(vals))
                    sig = "*" if se > 0 and abs(mean / se) >= 1.65 else " "
                    line += f" {mean:>+7.2f}{sig}"
            print(line)

        # Also show ALL
        n_all = len(bot_data)
        line = f"  {'ALL':>16} {n_all:>5}"
        for h in FORWARD_HORIZONS:
            col = f"fwd_{h}"
            vals = bot_data["trade_sign"] * bot_data[col]
            vals = vals.dropna()
            if len(vals) < 2:
                line += f" {'n/a':>9}"
            else:
                mean = vals.mean()
                se = vals.std() / np.sqrt(len(vals))
                sig = "*" if se > 0 and abs(mean / se) >= 1.65 else " "
                line += f" {mean:>+7.2f}{sig}"
        print(line)


def print_cumulative_position_vs_forward_return(positions_df):
    """Correlation between cumulative position level and forward returns.

    For Mark 67 (smart buyer), if he's accumulated a large long,
    does the price tend to move further up?
    """
    print("\n" + "=" * 70)
    print("  CUMULATIVE POSITION LEVEL vs FORWARD RETURN (correlation)")
    print("  Does knowing the bot's inventory size predict future price moves?")
    print("=" * 70)

    for bot in BOTS:
        bot_data = positions_df[positions_df["bot"] == bot]
        print(f"\n  {bot}")
        header = f"  {'Day':>4}"
        for h in FORWARD_HORIZONS:
            header += f" {'corr(pos,fwd'+str(h)+')':>18}"
        print(header)
        print(f"  {'-'*78}")

        for day in DAYS:
            day_data = bot_data[bot_data["day"] == day]
            line = f"  {day:>4}"
            for h in FORWARD_HORIZONS:
                col = f"fwd_{h}"
                valid = day_data[["cumulative_position", col]].dropna()
                if len(valid) < 5:
                    line += f" {'n/a':>18}"
                else:
                    corr = valid["cumulative_position"].corr(valid[col])
                    line += f" {corr:>+18.3f}"
            print(line)

        # All days combined
        line = f"  {'ALL':>4}"
        for h in FORWARD_HORIZONS:
            col = f"fwd_{h}"
            valid = bot_data[["cumulative_position", col]].dropna()
            if len(valid) < 5:
                line += f" {'n/a':>18}"
            else:
                corr = valid["cumulative_position"].corr(valid[col])
                line += f" {corr:>+18.3f}"
        print(line)


def print_mark67_limit_behavior(positions_df, mid_series):
    """When Mark 67 cumulative buys > 150, does buying stop? Price reverse?"""
    print("\n" + "=" * 70)
    print("  MARK 67 LIMIT-APPROACHING BEHAVIOR")
    print("  What happens when cumulative position > 150?")
    print("=" * 70)

    m67 = positions_df[positions_df["bot"] == "Mark 67"].copy()

    for day in DAYS:
        day_data = m67[m67["day"] == day].copy()
        if day_data.empty:
            print(f"\n  Day {day}: no Mark 67 trades")
            continue

        max_pos = day_data["cumulative_position"].max()
        min_pos = day_data["cumulative_position"].min()
        final_pos = day_data["cumulative_position"].iloc[-1]

        print(f"\n  Day {day}: range [{min_pos:+.0f}, {max_pos:+.0f}], final {final_pos:+.0f}")

        # Find the timestamp when position first exceeds 150
        over_150 = day_data[day_data["cumulative_position"] > 150]
        if over_150.empty:
            under_n150 = day_data[day_data["cumulative_position"] < -150]
            if under_n150.empty:
                print(f"    Never reached |pos| > 150")
                continue
            else:
                threshold_ts = under_n150.iloc[0]["timestamp"]
                threshold_dir = "short"
                print(f"    First exceeded -150 at timestamp {int(threshold_ts)}")
        else:
            threshold_ts = over_150.iloc[0]["timestamp"]
            threshold_dir = "long"
            print(f"    First exceeded +150 at timestamp {int(threshold_ts)}")

        # Trades before and after threshold
        before = day_data[day_data["timestamp"] < threshold_ts]
        after = day_data[day_data["timestamp"] >= threshold_ts]

        before_buy_pct = (before["trade_qty"] > 0).mean() * 100 if len(before) > 0 else 0
        after_buy_pct = (after["trade_qty"] > 0).mean() * 100 if len(after) > 0 else 0

        print(f"    Trades before threshold: {len(before)} ({before_buy_pct:.0f}% buys)")
        print(f"    Trades after threshold:  {len(after)} ({after_buy_pct:.0f}% buys)")

        # Price at threshold vs price at end of day
        timestamps, mids = mid_series[day]
        mid_at_threshold = get_mid_at(threshold_ts, timestamps, mids)
        mid_at_end = mids[-1]
        ts_at_end = timestamps[-1]

        price_change = mid_at_end - mid_at_threshold
        print(f"    Mid at threshold: {mid_at_threshold:.1f}")
        print(f"    Mid at day end:   {mid_at_end:.1f} (change: {price_change:+.1f})")

        # Also check: average forward return of trades before vs after threshold
        for h in FORWARD_HORIZONS:
            col = f"fwd_{h}"
            before_vals = before[col].dropna()
            after_vals = after[col].dropna()
            b_mean = before_vals.mean() if len(before_vals) > 0 else float("nan")
            a_mean = after_vals.mean() if len(after_vals) > 0 else float("nan")
            if not np.isnan(b_mean) and not np.isnan(a_mean):
                print(f"    Avg fwd_{h}: before={b_mean:+.2f}, after={a_mean:+.2f}")


def print_rate_of_accumulation(positions_df):
    """Does the RATE of inventory buildup carry signal?

    Split each bot's day into halves by trade count.
    Compare signed impact in 1st half vs 2nd half.
    """
    print("\n" + "=" * 70)
    print("  RATE OF ACCUMULATION: 1st HALF vs 2nd HALF OF DAY")
    print("  Does accelerating/decelerating buying matter?")
    print("=" * 70)

    positions_df = positions_df.copy()
    positions_df["trade_sign"] = np.sign(positions_df["trade_qty"])

    for bot in BOTS:
        bot_data = positions_df[positions_df["bot"] == bot]
        print(f"\n  {bot}")
        print(f"  {'Half':>8} {'N':>5} {'Avg pos':>8} {'Avg |delta|':>12}", end="")
        for h in FORWARD_HORIZONS:
            print(f" {'t+'+str(h):>9}", end="")
        print()
        print(f"  {'-'*65}")

        for half_label, half_selector in [("1st", "first"), ("2nd", "second")]:
            half_rows = []
            for day in DAYS:
                day_data = bot_data[bot_data["day"] == day]
                n = len(day_data)
                if n < 4:
                    continue
                mid = n // 2
                if half_selector == "first":
                    half_rows.append(day_data.iloc[:mid])
                else:
                    half_rows.append(day_data.iloc[mid:])

            if not half_rows:
                continue
            half_df = pd.concat(half_rows)
            n = len(half_df)
            avg_pos = half_df["cumulative_position"].mean()
            avg_delta = half_df["trade_qty"].abs().mean()

            line = f"  {half_label:>8} {n:>5} {avg_pos:>+8.1f} {avg_delta:>12.1f}"
            for h in FORWARD_HORIZONS:
                col = f"fwd_{h}"
                vals = half_df["trade_sign"] * half_df[col]
                vals = vals.dropna()
                if len(vals) < 2:
                    line += f" {'n/a':>9}"
                else:
                    mean = vals.mean()
                    se = vals.std() / np.sqrt(len(vals))
                    sig = "*" if abs(mean / se) >= 1.65 else " "
                    line += f" {mean:>+7.2f}{sig}"
            print(line)


def sanity_check_positions(positions_df, ve_trades):
    """Verify position tracking is correct."""
    print("\n" + "=" * 70)
    print("  SANITY CHECK: Position Tracking")
    print("=" * 70)

    for bot in BOTS:
        for day in DAYS:
            day_trades = ve_trades[ve_trades["day"] == day]
            buys = day_trades[day_trades["buyer"] == bot]["quantity"].sum()
            sells = day_trades[day_trades["seller"] == bot]["quantity"].sum()
            expected_final = buys - sells

            tracked = positions_df[
                (positions_df["bot"] == bot) & (positions_df["day"] == day)
            ]
            if tracked.empty:
                actual_final = 0
            else:
                actual_final = tracked["cumulative_position"].iloc[-1]

            match = "OK" if expected_final == actual_final else "MISMATCH"
            print(f"  {bot} Day {day}: buys={buys:>4}, sells={sells:>4}, "
                  f"expected={expected_final:>+5}, tracked={actual_final:>+5.0f} [{match}]")


def main():
    print("Loading data...")
    trades = load_all_trades()
    prices = load_all_prices()

    ve_trades = get_ve_trades(trades)
    mid_series = get_ve_mid_series(prices)

    print(f"VE trades: {len(ve_trades)} total across {len(DAYS)} days\n")

    # Build position trajectories
    positions_df = build_bot_positions(ve_trades)

    # Sanity check first
    sanity_check_positions(positions_df, ve_trades)

    # Attach forward returns
    positions_df = compute_forward_returns(positions_df, mid_series)

    # Analysis 1: Position trajectories
    print_position_trajectories(positions_df)

    # Analysis 2: Signal strength by inventory quartile
    print_signed_impact_by_quartile(positions_df)

    # Analysis 3: Cumulative position level vs forward return
    print_cumulative_position_vs_forward_return(positions_df)

    # Analysis 4: Mark 67 limit behavior
    print_mark67_limit_behavior(positions_df, mid_series)

    # Analysis 5: Rate of accumulation
    print_rate_of_accumulation(positions_df)


if __name__ == "__main__":
    main()
