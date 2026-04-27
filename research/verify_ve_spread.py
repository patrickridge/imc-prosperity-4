"""Verify VE spread economics claims independently."""
import pandas as pd
import numpy as np
from collections import Counter


price_frames = []
for day in [1, 2, 3]:
    df = pd.read_csv(f"data/round4/prices_round_4_day_{day}.csv", sep=";")
    df["day"] = day
    price_frames.append(df)
prices = pd.concat(price_frames, ignore_index=True)

ve_prices = prices[prices["product"] == "VELVETFRUIT_EXTRACT"].copy()
ve_prices["spread"] = ve_prices["ask_price_1"] - ve_prices["bid_price_1"]

print("=" * 60)
print("CLAIM 1: VE spread distribution")
print("=" * 60)
print(f"Total VE price observations: {len(ve_prices)}")
print(f"Median spread: {ve_prices['spread'].median()}")
print(f"Mean spread:   {ve_prices['spread'].mean():.2f}")
print()

spread_counts = ve_prices["spread"].value_counts().sort_index()
total = len(ve_prices)
print("Spread distribution:")
for spread_val, count in spread_counts.items():
    pct = count / total * 100
    print(f"  {spread_val:6.0f} ticks: {count:6d} ({pct:5.1f}%)")

print()
# Group for comparison with claim
pct_5 = (ve_prices["spread"] == 5).sum() / total * 100
pct_6 = (ve_prices["spread"] == 6).sum() / total * 100
pct_1_3 = ((ve_prices["spread"] >= 1) & (ve_prices["spread"] <= 3)).sum() / total * 100
pct_other = 100 - pct_5 - pct_6 - pct_1_3
print(f"Claimed: 5 ticks ~74%, 6 ticks ~18%, 1-3 ticks ~7%")
print(f"Actual:  5 ticks {pct_5:.1f}%, 6 ticks {pct_6:.1f}%, 1-3 ticks {pct_1_3:.1f}%, other {pct_other:.1f}%")


print()
print("=" * 60)
print("CLAIM 3: Signal persistence for Mark 67, Mark 49, Mark 22")
print("=" * 60)

trade_frames = []
for day in [1, 2, 3]:
    df = pd.read_csv(f"data/round4/trades_round_4_day_{day}.csv", sep=";")
    df["day"] = day
    trade_frames.append(df)
trades = pd.concat(trade_frames, ignore_index=True)

ve_trades = trades[trades["symbol"] == "VELVETFRUIT_EXTRACT"].copy()

# Build mid-price series keyed by (day, timestamp)
ve_prices["mid"] = (ve_prices["bid_price_1"] + ve_prices["ask_price_1"]) / 2.0
mid_series = ve_prices.set_index(["day", "timestamp"])["mid"].sort_index()

# Get sorted unique timestamps per day for forward-looking
ts_by_day = {}
for day in [1, 2, 3]:
    ts_by_day[day] = sorted(mid_series.loc[day].index.unique())

HORIZONS = [1, 5, 10, 20, 50, 100]
BOTS = ["Mark 67", "Mark 49", "Mark 22"]

for bot in BOTS:
    # Determine signal direction: is this bot a buyer or seller?
    bot_buys = ve_trades[ve_trades["buyer"] == bot]
    bot_sells = ve_trades[ve_trades["seller"] == bot]

    print(f"\n--- {bot} ---")
    print(f"  Buy trades:  {len(bot_buys)}")
    print(f"  Sell trades: {len(bot_sells)}")

    # Process all trades with a sign: +1 for buy, -1 for sell
    events = []
    for _, row in bot_buys.iterrows():
        events.append((row["day"], row["timestamp"], +1, row["quantity"]))
    for _, row in bot_sells.iterrows():
        events.append((row["day"], row["timestamp"], -1, row["quantity"]))

    if not events:
        print("  No trades found.")
        continue

    # For each event, compute mid-price change at each horizon
    impacts = {h: [] for h in HORIZONS}

    for day, ts, sign, qty in events:
        if day not in ts_by_day:
            continue
        day_ts = ts_by_day[day]

        # Find current timestamp index
        try:
            idx = day_ts.index(ts)
        except ValueError:
            # Timestamp not in price data; find nearest
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

            # Signed impact: positive means price moved in direction of trade
            impact = sign * (future_mid - current_mid)
            impacts[h].append(impact)

    print(f"  Horizon  |  N events  |  Mean impact  |  Median impact")
    print(f"  ---------+------------+---------------+----------------")
    for h in HORIZONS:
        if impacts[h]:
            arr = np.array(impacts[h])
            print(f"  t+{h:<5d}  |  {len(arr):8d}  |  {arr.mean():+11.2f}  |  {np.median(arr):+12.2f}")
        else:
            print(f"  t+{h:<5d}  |         0  |           N/A  |            N/A")

print()
print("=" * 60)
print("CLAIM 2: Bot signal vs spread cost")
print("=" * 60)
print(f"Median spread: {ve_prices['spread'].median()} ticks")
print(f"Half-spread (cost to cross): {ve_prices['spread'].median() / 2:.1f} ticks")
print("If signal is ~2 ticks and you cross spread (pay ~2.5 each side = 5 total),")
print("the signal cannot pay for the round-trip cost.")
print("See impact numbers above to assess signal magnitude.")
