"""
H8b: Deep dive on options -> spot signal.

Mark 01 (buyer) and Mark 22 (seller) show growing signal at t+20/t+50.
Check: per-day consistency, extended time horizon, combined signal strength,
and whether the signal is actionable for maker bias.
"""

import pandas as pd
import numpy as np
from scipy import stats

DATA_DIR = "data/round4"
DAYS = [1, 2, 3]
VE_SPOT = "VELVETFRUIT_EXTRACT"
EXTENDED_LAGS = [1, 2, 5, 10, 20, 50, 100, 200, 500]


def load_day(day):
    prices = pd.read_csv(f"{DATA_DIR}/prices_round_4_day_{day}.csv", sep=";")
    trades = pd.read_csv(f"{DATA_DIR}/trades_round_4_day_{day}.csv", sep=";")
    return prices, trades


def get_ve_spot_series(prices):
    ve = prices[prices["product"] == VE_SPOT][["timestamp", "mid_price"]].copy()
    ve = ve.sort_values("timestamp").reset_index(drop=True)
    return ve["timestamp"].values, ve["mid_price"].values


def get_bot_option_trades(trades, bot):
    vev_symbols = [s for s in trades["symbol"].unique() if s.startswith("VEV_")]
    is_buyer = (trades["buyer"] == bot) & (trades["symbol"].isin(vev_symbols))
    is_seller = (trades["seller"] == bot) & (trades["symbol"].isin(vev_symbols))
    buys = trades[is_buyer].copy()
    buys["direction"] = 1
    sells = trades[is_seller].copy()
    sells["direction"] = -1
    return pd.concat([buys, sells]).sort_values("timestamp").reset_index(drop=True)


def per_day_breakdown():
    print("=" * 65)
    print("PART 1: PER-DAY CONSISTENCY")
    print("=" * 65)

    for bot in ["Mark 01", "Mark 22"]:
        print(f"\n  {bot}:")
        print(f"  {'day':>4} {'lag':>5} {'mean':>7} {'t-stat':>7} {'n':>5}")
        print(f"  {'-'*4} {'-'*5} {'-'*7} {'-'*7} {'-'*5}")

        for day in DAYS:
            prices, trades = load_day(day)
            ve_ts, ve_mid = get_ve_spot_series(prices)
            option_trades = get_bot_option_trades(trades, bot)

            grouped = option_trades.groupby("timestamp")["direction"].sum().reset_index()

            for la in [10, 20, 50]:
                impacts = []
                for _, row in grouped.iterrows():
                    ts = row["timestamp"]
                    direction = np.sign(row["direction"])
                    if direction == 0:
                        continue
                    idx = np.searchsorted(ve_ts, ts)
                    if idx >= len(ve_ts) or ve_ts[idx] != ts:
                        continue
                    future_idx = idx + la
                    if future_idx < len(ve_mid):
                        move = direction * (ve_mid[future_idx] - ve_mid[idx])
                        impacts.append(move)

                if not impacts:
                    continue
                arr = np.array(impacts)
                mean = arr.mean()
                stderr = arr.std(ddof=1) / np.sqrt(len(arr))
                t_stat = mean / stderr if stderr > 0 else 0
                print(f"  {day:>4} {f'+{la}':>5} {mean:>+7.2f} {t_stat:>+7.2f} {len(arr):>5}")


def extended_horizon():
    print("\n" + "=" * 65)
    print("PART 2: EXTENDED SIGNAL SHAPE (t+1 to t+500)")
    print("=" * 65)

    for bot in ["Mark 01", "Mark 22"]:
        results = {la: [] for la in EXTENDED_LAGS}

        for day in DAYS:
            prices, trades = load_day(day)
            ve_ts, ve_mid = get_ve_spot_series(prices)
            option_trades = get_bot_option_trades(trades, bot)
            grouped = option_trades.groupby("timestamp")["direction"].sum().reset_index()

            for _, row in grouped.iterrows():
                ts = row["timestamp"]
                direction = np.sign(row["direction"])
                if direction == 0:
                    continue
                idx = np.searchsorted(ve_ts, ts)
                if idx >= len(ve_ts) or ve_ts[idx] != ts:
                    continue
                for la in EXTENDED_LAGS:
                    future_idx = idx + la
                    if future_idx < len(ve_mid):
                        results[la].append(direction * (ve_mid[future_idx] - ve_mid[idx]))

        print(f"\n  {bot}:")
        print(f"  {'lag':>6} {'mean':>7} {'median':>7} {'t-stat':>7} {'n':>5}")
        print(f"  {'-'*6} {'-'*7} {'-'*7} {'-'*7} {'-'*5}")
        for la in EXTENDED_LAGS:
            arr = np.array(results[la])
            mean = arr.mean()
            median = np.median(arr)
            stderr = arr.std(ddof=1) / np.sqrt(len(arr))
            t_stat = mean / stderr if stderr > 0 else 0
            print(f"  {f'+{la}':>6} {mean:>+7.2f} {median:>+7.1f} {t_stat:>+7.2f} {len(arr):>5}")


def combined_signal():
    print("\n" + "=" * 65)
    print("PART 3: COMBINED SIGNAL (Mark 01 buy + Mark 22 sell)")
    print("=" * 65)
    print("\nComposite direction: +1 when Mark 01 buys OR Mark 22 sells.")
    print("Signal 'on' = at least one fired in last N ticks.\n")

    SIGNAL_WINDOWS = [100, 500, 1000, 2000]

    for window in SIGNAL_WINDOWS:
        all_impacts = {la: [] for la in [10, 20, 50, 100]}
        total_signals = 0

        for day in DAYS:
            prices, trades = load_day(day)
            ve_ts, ve_mid = get_ve_spot_series(prices)

            # Collect all option signal events with unified direction
            # Mark 01 buys -> bullish (+1), Mark 22 sells -> bullish (+1)
            # Mark 01 sells -> bearish (-1), Mark 22 buys -> bearish (-1)
            m01_trades = get_bot_option_trades(trades, "Mark 01")
            m22_trades = get_bot_option_trades(trades, "Mark 22")

            # Mark 01: direction as-is (buy=+1 means bullish)
            # Mark 22: flip direction (sell=-1 means bullish, so negate)
            m22_trades["direction"] = -m22_trades["direction"]

            all_signals = pd.concat([m01_trades, m22_trades])
            net_per_ts = all_signals.groupby("timestamp")["direction"].sum().reset_index()
            signal_ts = net_per_ts["timestamp"].values
            signal_dir = np.sign(net_per_ts["direction"].values)

            # For each VE spot timestamp, check if signal fired within window
            for i, ts in enumerate(ve_ts):
                # Find signals in [ts - window, ts]
                mask = (signal_ts >= ts - window) & (signal_ts <= ts) & (signal_ts < ts)
                recent = signal_dir[mask]
                if len(recent) == 0:
                    continue
                net = np.sign(recent.sum())
                if net == 0:
                    continue

                total_signals += 1
                for la in all_impacts:
                    future_idx = i + la
                    if future_idx < len(ve_mid):
                        move = net * (ve_mid[future_idx] - ve_mid[i])
                        all_impacts[la].append(move)

        print(f"  Window={window} ticks: {total_signals} signal-on timestamps")
        for la in all_impacts:
            arr = np.array(all_impacts[la])
            if len(arr) < 10:
                continue
            mean = arr.mean()
            stderr = arr.std(ddof=1) / np.sqrt(len(arr))
            t_stat = mean / stderr if stderr > 0 else 0
            print(f"    +{la:<4d} mean={mean:+.3f}  t={t_stat:+.2f}  n={len(arr)}")


def signal_vs_drift():
    print("\n" + "=" * 65)
    print("PART 4: SIGNAL VS UNCONDITIONAL VE DRIFT")
    print("=" * 65)
    print("\nIs the 'signal' just VE's overall trend? Compare signal-on vs all ticks.\n")

    for day in DAYS:
        prices, _ = load_day(day)
        ve_ts, ve_mid = get_ve_spot_series(prices)

        # Unconditional: average t+50 move from any tick
        moves_50 = ve_mid[50:] - ve_mid[:-50]
        print(f"  Day {day}: unconditional t+50 mean={moves_50.mean():+.2f}, "
              f"median={np.median(moves_50):+.1f}, std={moves_50.std():.2f}")

        # Overall price range
        print(f"          price range: {ve_mid.min():.0f} to {ve_mid.max():.0f} "
              f"(delta={ve_mid.max()-ve_mid.min():.0f})")


def counterparty_check():
    print("\n" + "=" * 65)
    print("PART 5: COUNTERPARTY STRUCTURE IN OPTION TRADES")
    print("=" * 65)
    print("\nWho is on the other side of Mark 01/22 option trades?\n")

    for bot in ["Mark 01", "Mark 22"]:
        print(f"  {bot}:")
        for day in DAYS:
            _, trades = load_day(day)
            vev = [s for s in trades["symbol"].unique() if s.startswith("VEV_")]

            as_buyer = trades[(trades["buyer"] == bot) & (trades["symbol"].isin(vev))]
            as_seller = trades[(trades["seller"] == bot) & (trades["symbol"].isin(vev))]

            buy_counterparties = as_buyer["seller"].value_counts().head(3)
            sell_counterparties = as_seller["buyer"].value_counts().head(3)

            n_buy = len(as_buyer)
            n_sell = len(as_seller)
            print(f"    Day {day}: {n_buy} buys, {n_sell} sells")
            if n_buy > 0:
                top = buy_counterparties.index[0]
                pct = buy_counterparties.iloc[0] / n_buy
                print(f"      buys from: {top} ({pct:.0%})", end="")
                if len(buy_counterparties) > 1:
                    print(f", {buy_counterparties.index[1]} ({buy_counterparties.iloc[1]/n_buy:.0%})", end="")
                print()
            if n_sell > 0:
                top = sell_counterparties.index[0]
                pct = sell_counterparties.iloc[0] / n_sell
                print(f"      sells to: {top} ({pct:.0%})", end="")
                if len(sell_counterparties) > 1:
                    print(f", {sell_counterparties.index[1]} ({sell_counterparties.iloc[1]/n_sell:.0%})", end="")
                print()


def main():
    per_day_breakdown()
    extended_horizon()
    combined_signal()
    signal_vs_drift()
    counterparty_check()


if __name__ == "__main__":
    main()
