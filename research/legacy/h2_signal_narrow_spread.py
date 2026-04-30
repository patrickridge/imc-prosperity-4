"""H2: Does signal + narrow spread make taking profitable?

Tests whether combining bot directional signals with narrow-spread
moments creates a profitable taker strategy on VELVETFRUIT_EXTRACT.

Timing model:
- market_trades at timestamp T are from T-100 (one tick delay)
- We SEE the trade at T, can PLACE orders at T
- Orders FILL at T+100, so fill price = ask/bid at T+100

Signal bots (from r4_bot_signals.md):
- Mark 67: smart buyer → follow (buy when he buys)
- Mark 49: dumb seller → fade (buy when he sells)
- Mark 22: dumb seller → fade (buy when he sells)
"""

import pandas as pd
import numpy as np
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data" / "round4"
PRODUCT = "VELVETFRUIT_EXTRACT"
DAYS = [1, 2, 3]

SIGNAL_BOTS = {
    "Mark 67": "follow",   # smart buyer: follow his direction
    "Mark 49": "fade",     # dumb seller: fade his direction
    "Mark 22": "fade",     # dumb seller: fade his direction
}

SPREAD_THRESHOLDS = [2, 3, 4]
HORIZONS = [1, 5, 10, 20]


def load_prices():
    frames = []
    for day in DAYS:
        path = DATA_DIR / f"prices_round_4_day_{day}.csv"
        df = pd.read_csv(path, sep=";")
        df = df[df["product"] == PRODUCT].copy()
        df["day"] = day
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def load_trades():
    frames = []
    for day in DAYS:
        path = DATA_DIR / f"trades_round_4_day_{day}.csv"
        df = pd.read_csv(path, sep=";")
        df = df[df["symbol"] == PRODUCT].copy()
        df["day"] = day
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def compute_spread(prices):
    """Spread = best ask - best bid."""
    prices["spread"] = prices["ask_price_1"] - prices["bid_price_1"]
    return prices


def get_signal_direction(trade_row):
    """Return +1 (buy signal) or -1 (sell signal) based on bot and action.

    Mark 67 is a 'follow' bot (smart buyer). When he buys, we buy (+1).
    Mark 49/22 are 'fade' bots (dumb sellers). When they sell, we buy (+1).
    """
    for bot_name, strategy in SIGNAL_BOTS.items():
        is_buyer = trade_row["buyer"] == bot_name
        is_seller = trade_row["seller"] == bot_name

        if not is_buyer and not is_seller:
            continue

        if strategy == "follow":
            return +1 if is_buyer else -1
        else:  # fade
            return +1 if is_seller else -1

    return 0  # not a signal bot


def build_price_lookup(prices):
    """Create dict: (day, timestamp) -> row data for fast lookup."""
    lookup = {}
    for _, row in prices.iterrows():
        lookup[(row["day"], row["timestamp"])] = row
    return lookup


def find_next_timestamp(day, ts, price_lookup, offset=100):
    """Find the price row at ts + offset."""
    key = (day, ts + offset)
    return price_lookup.get(key)


def analyze_spread_around_bot_trades(trades, prices):
    """Test: are narrow spreads more common around bot trades?"""
    print("=" * 70)
    print("PART 1: Do narrow spreads cluster around bot trades?")
    print("=" * 70)

    price_lookup = build_price_lookup(prices)

    # Baseline: spread distribution at ALL timestamps
    all_spreads = prices["spread"].dropna()
    total_obs = len(all_spreads)

    for thresh in SPREAD_THRESHOLDS:
        baseline_pct = (all_spreads <= thresh).mean() * 100
        print(f"\nBaseline: spread <= {thresh} at {baseline_pct:.1f}% "
              f"of all timestamps ({(all_spreads <= thresh).sum()}/{total_obs})")

    # Signal bot trades: check spread at T (when we see the trade)
    signal_trades = trades[
        trades["buyer"].isin(SIGNAL_BOTS) | trades["seller"].isin(SIGNAL_BOTS)
    ].copy()

    # De-duplicate: multiple trades at same (day, timestamp) → one event
    signal_events = signal_trades.drop_duplicates(subset=["day", "timestamp"])

    print(f"\nSignal bot trade events (unique timestamps): {len(signal_events)}")

    # Spread at the moment we see the trade (T = trade_ts + 100)
    observe_spreads = []
    for _, event in signal_events.iterrows():
        observe_ts = event["timestamp"] + 100
        row = price_lookup.get((event["day"], observe_ts))
        if row is not None:
            observe_spreads.append(row["spread"])

    observe_spreads = np.array(observe_spreads)
    n_obs = len(observe_spreads)
    print(f"Events with valid spread at T+100: {n_obs}")

    for thresh in SPREAD_THRESHOLDS:
        signal_pct = (observe_spreads <= thresh).mean() * 100
        n_narrow = (observe_spreads <= thresh).sum()
        baseline_pct = (all_spreads <= thresh).mean() * 100
        ratio = signal_pct / baseline_pct if baseline_pct > 0 else float("inf")
        print(f"\nSpread <= {thresh} at signal time: {signal_pct:.1f}% "
              f"({n_narrow}/{n_obs}) vs baseline {baseline_pct:.1f}%  "
              f"(ratio: {ratio:.2f}x)")

    # Also check at T (the trade timestamp itself, before the 100 offset)
    trade_ts_spreads = []
    for _, event in signal_events.iterrows():
        row = price_lookup.get((event["day"], event["timestamp"]))
        if row is not None:
            trade_ts_spreads.append(row["spread"])
    trade_ts_spreads = np.array(trade_ts_spreads)
    print(f"\n--- Spread at trade timestamp T (before observation delay) ---")
    for thresh in SPREAD_THRESHOLDS:
        pct = (trade_ts_spreads <= thresh).mean() * 100
        n = (trade_ts_spreads <= thresh).sum()
        baseline_pct = (all_spreads <= thresh).mean() * 100
        print(f"  Spread <= {thresh} at T: {pct:.1f}% ({n}/{len(trade_ts_spreads)}) "
              f"vs baseline {baseline_pct:.1f}%")


def analyze_signal_plus_narrow(trades, prices):
    """Main test: profitability of signal + narrow spread."""
    print("\n" + "=" * 70)
    print("PART 2: Signal + narrow spread profitability")
    print("=" * 70)

    price_lookup = build_price_lookup(prices)

    # Build signal events with direction
    events = []
    for _, trade in trades.iterrows():
        direction = get_signal_direction(trade)
        if direction == 0:
            continue

        bot = None
        for b in SIGNAL_BOTS:
            if trade["buyer"] == b or trade["seller"] == b:
                bot = b
                break

        observe_ts = trade["timestamp"] + 100
        observe_row = price_lookup.get((trade["day"], observe_ts))
        if observe_row is None:
            continue

        events.append({
            "day": trade["day"],
            "trade_ts": trade["timestamp"],
            "observe_ts": observe_ts,
            "bot": bot,
            "direction": direction,
            "spread_at_observe": observe_row["spread"],
            "mid_at_observe": observe_row["mid_price"],
            "bid_at_observe": observe_row["bid_price_1"],
            "ask_at_observe": observe_row["ask_price_1"],
        })

    events_df = pd.DataFrame(events)

    # De-duplicate: if multiple signal trades at same timestamp, keep strongest
    # (if conflicting directions, skip; if same direction, keep one)
    deduped = []
    for (day, ts), group in events_df.groupby(["day", "observe_ts"]):
        directions = group["direction"].unique()
        if len(directions) > 1:
            continue  # conflicting signals
        deduped.append(group.iloc[0])
    events_df = pd.DataFrame(deduped)

    print(f"\nTotal signal events (de-duped): {len(events_df)}")
    print(f"  Buy signals (+1): {(events_df['direction'] == 1).sum()}")
    print(f"  Sell signals (-1): {(events_df['direction'] == -1).sum()}")

    for thresh in SPREAD_THRESHOLDS:
        narrow = events_df[events_df["spread_at_observe"] <= thresh]
        print(f"\n{'─' * 60}")
        print(f"SPREAD THRESHOLD: <= {thresh} ticks")
        print(f"{'─' * 60}")
        print(f"Events with narrow spread: {len(narrow)} "
              f"({len(narrow)/len(events_df)*100:.1f}% of signal events)")

        if len(narrow) < 5:
            print("  Too few events for analysis.")
            continue

        # Per-day breakdown
        for day in DAYS:
            day_n = len(narrow[narrow["day"] == day])
            print(f"  Day {day}: {day_n} events")

        # For each qualifying event, compute:
        # 1. Signed impact at various horizons
        # 2. Taker PnL (fill at T+100 ask/bid, measure vs mid at T+h)
        results = []
        for _, event in narrow.iterrows():
            day = event["day"]
            direction = event["direction"]
            observe_ts = event["observe_ts"]

            # Fill price: we place at T, fills at T+100
            fill_ts = observe_ts + 100
            fill_row = price_lookup.get((day, fill_ts))
            if fill_row is None:
                continue

            if direction == +1:  # buy signal → buy at ask
                fill_price = fill_row["ask_price_1"]
            else:  # sell signal → sell at bid
                fill_price = fill_row["bid_price_1"]

            result = {
                "day": day,
                "observe_ts": observe_ts,
                "direction": direction,
                "fill_price": fill_price,
                "mid_at_fill": fill_row["mid_price"],
                "spread_at_fill": fill_row["spread"],
                "spread_at_observe": event["spread_at_observe"],
            }

            # Price impact at various horizons (from fill time)
            for h in HORIZONS:
                future_ts = fill_ts + h * 100
                future_row = price_lookup.get((day, future_ts))
                if future_row is not None:
                    future_mid = future_row["mid_price"]
                    # Signed impact: positive = price moved in our favor
                    impact = direction * (future_mid - event["mid_at_observe"])
                    result[f"impact_t{h}"] = impact

                    # Taker PnL: positive = we made money
                    pnl = direction * (future_mid - fill_price)
                    result[f"pnl_t{h}"] = pnl

            results.append(result)

        if not results:
            print("  No events with valid fill data.")
            continue

        res_df = pd.DataFrame(results)
        print(f"\nEvents with valid fills: {len(res_df)}")

        # Impact analysis (signed, from observe time)
        print(f"\nSigned price impact from observe time (direction-adjusted):")
        for h in HORIZONS:
            col = f"impact_t{h}"
            if col in res_df.columns:
                vals = res_df[col].dropna()
                mean_imp = vals.mean()
                median_imp = vals.median()
                se = vals.std() / np.sqrt(len(vals))
                t_stat = mean_imp / se if se > 0 else 0
                print(f"  t+{h:2d}: mean={mean_imp:+.2f}, "
                      f"median={median_imp:+.1f}, "
                      f"n={len(vals)}, t={t_stat:+.2f}")

        # Taker PnL analysis
        print(f"\nTaker PnL (fill at T+100 ask/bid, vs future mid):")
        for h in HORIZONS:
            col = f"pnl_t{h}"
            if col in res_df.columns:
                vals = res_df[col].dropna()
                mean_pnl = vals.mean()
                median_pnl = vals.median()
                se = vals.std() / np.sqrt(len(vals))
                t_stat = mean_pnl / se if se > 0 else 0
                win_rate = (vals > 0).mean() * 100
                print(f"  t+{h:2d}: mean={mean_pnl:+.2f}, "
                      f"median={median_pnl:+.1f}, "
                      f"win%={win_rate:.0f}%, "
                      f"n={len(vals)}, t={t_stat:+.2f}")

        # Per-day PnL breakdown at t+5 and t+10
        print(f"\nPer-day PnL (assuming qty=1 per trade):")
        for h in [5, 10]:
            col = f"pnl_t{h}"
            if col not in res_df.columns:
                continue
            print(f"  Horizon t+{h}:")
            for day in DAYS:
                day_data = res_df[res_df["day"] == day][col].dropna()
                if len(day_data) > 0:
                    total = day_data.sum()
                    print(f"    Day {day}: total={total:+.1f}, "
                          f"mean={day_data.mean():+.2f}, n={len(day_data)}")

        # Spread at fill time (T+100) vs observe time
        print(f"\nSpread at fill time (T+100) for these events:")
        fill_spreads = res_df["spread_at_fill"]
        print(f"  Mean: {fill_spreads.mean():.1f}, "
              f"Median: {fill_spreads.median():.1f}")
        for s in [1, 2, 3, 4, 5, 6]:
            pct = (fill_spreads <= s).mean() * 100
            print(f"  <= {s}: {pct:.0f}%")

    # Per-bot breakdown at best threshold
    print(f"\n{'=' * 70}")
    print("PART 3: Per-bot breakdown (spread <= 3)")
    print("=" * 70)

    for bot in SIGNAL_BOTS:
        bot_events = events_df[events_df["bot"] == bot]
        narrow = bot_events[bot_events["spread_at_observe"] <= 3]

        print(f"\n{bot} ({SIGNAL_BOTS[bot]}): "
              f"{len(narrow)}/{len(bot_events)} events with spread <= 3")

        if len(narrow) < 3:
            print("  Too few events.")
            continue

        results = []
        for _, event in narrow.iterrows():
            day = event["day"]
            direction = event["direction"]
            observe_ts = event["observe_ts"]
            fill_ts = observe_ts + 100
            fill_row = price_lookup.get((day, fill_ts))
            if fill_row is None:
                continue

            fill_price = (fill_row["ask_price_1"] if direction == +1
                          else fill_row["bid_price_1"])

            for h in [5, 10]:
                future_ts = fill_ts + h * 100
                future_row = price_lookup.get((day, future_ts))
                if future_row is not None:
                    pnl = direction * (future_row["mid_price"] - fill_price)
                    results.append({
                        "horizon": h,
                        "pnl": pnl,
                        "day": day,
                    })

        if not results:
            continue

        bot_res = pd.DataFrame(results)
        for h in [5, 10]:
            hdata = bot_res[bot_res["horizon"] == h]["pnl"]
            if len(hdata) > 0:
                print(f"  t+{h}: mean PnL={hdata.mean():+.2f}, "
                      f"n={len(hdata)}, total={hdata.sum():+.1f}")


def analyze_narrow_spread_timing(prices):
    """Check when narrow spreads occur — random or clustered?"""
    print(f"\n{'=' * 70}")
    print("PART 4: Narrow spread timing patterns")
    print("=" * 70)

    for day in DAYS:
        day_prices = prices[prices["day"] == day].copy()
        day_prices = day_prices.sort_values("timestamp")
        narrow_mask = day_prices["spread"] <= 3
        narrow_ts = day_prices.loc[narrow_mask, "timestamp"].values

        total = len(day_prices)
        n_narrow = narrow_mask.sum()
        print(f"\nDay {day}: {n_narrow}/{total} timestamps with spread <= 3 "
              f"({n_narrow/total*100:.1f}%)")

        if n_narrow < 2:
            continue

        # Check if narrow spreads cluster (run lengths)
        runs = []
        current_run = 0
        for val in narrow_mask.values:
            if val:
                current_run += 1
            elif current_run > 0:
                runs.append(current_run)
                current_run = 0
        if current_run > 0:
            runs.append(current_run)

        runs = np.array(runs)
        print(f"  Narrow-spread runs: {len(runs)} runs, "
              f"mean length={runs.mean():.1f}, max={runs.max()}")
        print(f"  Run length distribution: "
              f"1={np.sum(runs==1)}, 2={np.sum(runs==2)}, "
              f"3-5={np.sum((runs>=3)&(runs<=5))}, "
              f"6+={np.sum(runs>=6)}")


def main():
    prices = load_prices()
    prices = compute_spread(prices)
    trades = load_trades()

    # Sanity check
    print("SANITY CHECKS")
    print(f"VE price rows: {len(prices)}")
    print(f"VE trades: {len(trades)}")
    spread_dist = prices["spread"].value_counts().sort_index()
    print(f"Spread distribution:")
    for spread_val, count in spread_dist.items():
        print(f"  {spread_val:.0f}: {count} ({count/len(prices)*100:.1f}%)")

    print()
    analyze_spread_around_bot_trades(trades, prices)
    analyze_signal_plus_narrow(trades, prices)
    analyze_narrow_spread_timing(prices)

    print(f"\n{'=' * 70}")
    print("DONE")
    print("=" * 70)


if __name__ == "__main__":
    main()
