"""Verify VE signal persistence - show both raw and signed impact."""
import pandas as pd
import numpy as np

# Load prices
price_frames = []
for day in [1, 2, 3]:
    df = pd.read_csv(f"data/round4/prices_round_4_day_{day}.csv", sep=";")
    df["day"] = day
    price_frames.append(df)
prices = pd.concat(price_frames, ignore_index=True)

ve_prices = prices[prices["product"] == "VELVETFRUIT_EXTRACT"].copy()
ve_prices["mid"] = (ve_prices["bid_price_1"] + ve_prices["ask_price_1"]) / 2.0
mid_series = ve_prices.set_index(["day", "timestamp"])["mid"].sort_index()

ts_by_day = {}
for day in [1, 2, 3]:
    ts_by_day[day] = sorted(mid_series.loc[day].index.unique())

# Load trades
trade_frames = []
for day in [1, 2, 3]:
    df = pd.read_csv(f"data/round4/trades_round_4_day_{day}.csv", sep=";")
    df["day"] = day
    trade_frames.append(df)
trades = pd.concat(trade_frames, ignore_index=True)
ve_trades = trades[trades["symbol"] == "VELVETFRUIT_EXTRACT"].copy()

HORIZONS = [1, 2, 3, 5, 10, 20, 50, 100]
BOTS = ["Mark 67", "Mark 49", "Mark 22"]

for bot in BOTS:
    bot_buys = ve_trades[ve_trades["buyer"] == bot]
    bot_sells = ve_trades[ve_trades["seller"] == bot]

    print(f"\n{'='*60}")
    print(f"{bot}: {len(bot_buys)} buys, {len(bot_sells)} sells")
    print(f"{'='*60}")

    # Separate analysis for buys and sells
    for label, subset, sign in [("BUYS", bot_buys, +1), ("SELLS", bot_sells, -1)]:
        if len(subset) == 0:
            continue
        print(f"\n  {label} ({len(subset)} trades):")

        raw_impacts = {h: [] for h in HORIZONS}

        for _, row in subset.iterrows():
            day = row["day"]
            ts = row["timestamp"]
            if day not in ts_by_day:
                continue
            day_ts = ts_by_day[day]
            try:
                idx = day_ts.index(ts)
            except ValueError:
                nearest_idx = np.searchsorted(day_ts, ts)
                if nearest_idx >= len(day_ts):
                    continue
                idx = nearest_idx

            current_mid = mid_series.loc[(day, day_ts[idx])]
            if isinstance(current_mid, pd.Series):
                current_mid = current_mid.iloc[0]

            for h in HORIZONS:
                future_idx = idx + h
                if future_idx >= len(day_ts):
                    continue
                future_mid = mid_series.loc[(day, day_ts[future_idx])]
                if isinstance(future_mid, pd.Series):
                    future_mid = future_mid.iloc[0]
                raw_impacts[h].append(future_mid - current_mid)

        print(f"  Horizon | N    | Raw mean chg | Raw median chg | Signed mean | Signed median")
        print(f"  --------+------+--------------+----------------+-------------+--------------")
        for h in HORIZONS:
            if raw_impacts[h]:
                arr = np.array(raw_impacts[h])
                signed = sign * arr
                print(f"  t+{h:<4d}  | {len(arr):4d} | {arr.mean():+12.2f} | {np.median(arr):+14.2f} | {signed.mean():+11.2f} | {np.median(signed):+12.2f}")

    # Combined analysis (all trades, signed = trade direction)
    print(f"\n  ALL TRADES COMBINED (signed by trade direction):")
    events = []
    for _, row in bot_buys.iterrows():
        events.append((row["day"], row["timestamp"], +1))
    for _, row in bot_sells.iterrows():
        events.append((row["day"], row["timestamp"], -1))

    signed_impacts = {h: [] for h in HORIZONS}
    for day, ts, sign in events:
        if day not in ts_by_day:
            continue
        day_ts = ts_by_day[day]
        try:
            idx = day_ts.index(ts)
        except ValueError:
            nearest_idx = np.searchsorted(day_ts, ts)
            if nearest_idx >= len(day_ts):
                continue
            idx = nearest_idx

        current_mid = mid_series.loc[(day, day_ts[idx])]
        if isinstance(current_mid, pd.Series):
            current_mid = current_mid.iloc[0]

        for h in HORIZONS:
            future_idx = idx + h
            if future_idx >= len(day_ts):
                continue
            future_mid = mid_series.loc[(day, day_ts[future_idx])]
            if isinstance(future_mid, pd.Series):
                future_mid = future_mid.iloc[0]
            signed_impacts[h].append(sign * (future_mid - current_mid))

    print(f"  Horizon | N    | Signed mean | Signed median")
    print(f"  --------+------+-------------+--------------")
    for h in HORIZONS:
        if signed_impacts[h]:
            arr = np.array(signed_impacts[h])
            print(f"  t+{h:<4d}  | {len(arr):4d} | {arr.mean():+11.2f} | {np.median(arr):+12.2f}")

# Summary
print(f"\n{'='*60}")
print("SUMMARY: Checking claim that impact appears at t+1, stays FLAT, decays by t+100")
print("='*60")
