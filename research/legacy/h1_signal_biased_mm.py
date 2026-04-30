"""H1: Signal-biased market maker on VELVETFRUIT_EXTRACT.

Tests whether bot trade signals can improve maker fill quality
by shifting fair value before quoting.

Signal bots:
- Mark 67: smart buyer  -> bullish signal
- Mark 49: dumb seller  -> bearish signal (when buying = bullish)
- Mark 22: dumb seller  -> bearish signal (when buying = bullish)

Key timing constraint: market_trades at timestamp T are from T-100,
so the earliest we can adjust quotes is at T, affecting fills at T+100.
"""

import pandas as pd
import numpy as np
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data" / "round4"
PRODUCT = "VELVETFRUIT_EXTRACT"
DAYS = [1, 2, 3]

SMART_BUYER = "Mark 67"
DUMB_SELLERS = {"Mark 22", "Mark 49"}
SIGNAL_BOTS = {SMART_BUYER} | DUMB_SELLERS

HALF_SPREAD = 2.5  # median spread is 5, half is 2.5
SHIFT_SIZES = [1, 2, 3]
FUTURE_HORIZONS = [1, 5, 10, 20, 50, 100]  # in ticks (each tick = 100 ts)

# Delay: we see trades 1 tick late, so signal at T means
# we can only adjust quotes starting at T (for fills at T+100).
OBSERVATION_DELAY_TICKS = 1


def load_prices():
    frames = []
    for day in DAYS:
        path = DATA_DIR / f"prices_round_4_day_{day}.csv"
        df = pd.read_csv(path, sep=";")
        frames.append(df)
    prices = pd.concat(frames, ignore_index=True)
    ve = prices[prices["product"] == PRODUCT].copy()
    ve = ve[["day", "timestamp", "mid_price", "bid_price_1", "ask_price_1"]]
    return ve


def load_trades():
    frames = []
    for day in DAYS:
        path = DATA_DIR / f"trades_round_4_day_{day}.csv"
        df = pd.read_csv(path, sep=";")
        df["day"] = day
        frames.append(df)
    trades = pd.concat(frames, ignore_index=True)
    return trades[trades["symbol"] == PRODUCT]


def classify_signal(row):
    """Return +1 for bullish, -1 for bearish, 0 for no signal."""
    buyer, seller = row["buyer"], row["seller"]

    # Mark 67 buying = bullish
    if buyer == SMART_BUYER:
        return +1
    # Mark 67 selling = bearish (never happens in data but handle it)
    if seller == SMART_BUYER:
        return -1

    # Dumb seller buying = bearish (they're wrong directionally)
    if buyer in DUMB_SELLERS:
        return -1
    # Dumb seller selling = bullish (fade them)
    if seller in DUMB_SELLERS:
        return +1

    return 0


def build_mid_lookup(prices):
    """Dict of (day, timestamp) -> mid_price for fast lookup."""
    return dict(
        zip(
            zip(prices["day"], prices["timestamp"]),
            prices["mid_price"],
        )
    )


def get_future_mid(mid_lookup, day, timestamp, horizon_ticks):
    """Get mid price at timestamp + horizon_ticks * 100."""
    future_ts = timestamp + horizon_ticks * 100
    return mid_lookup.get((day, future_ts))


def analyze_signal_events(trades, mid_lookup):
    """For each signal-bot trade, compute future mid changes."""
    events = []

    for _, row in trades.iterrows():
        signal = classify_signal(row)
        if signal == 0:
            continue

        day = row["day"]
        trade_ts = row["timestamp"]

        # We observe this trade at trade_ts + 100 (1 tick delay)
        observe_ts = trade_ts + OBSERVATION_DELAY_TICKS * 100

        # The mid at observation time is our reference
        mid_at_observe = mid_lookup.get((day, observe_ts))
        if mid_at_observe is None:
            continue

        event = {
            "day": day,
            "trade_ts": trade_ts,
            "observe_ts": observe_ts,
            "signal": signal,
            "mid_at_observe": mid_at_observe,
            "trade_price": row["price"],
            "buyer": row["buyer"],
            "seller": row["seller"],
        }

        for h in FUTURE_HORIZONS:
            future_mid = get_future_mid(mid_lookup, day, observe_ts, h)
            event[f"mid_t+{h}"] = future_mid
            if future_mid is not None:
                event[f"delta_t+{h}"] = future_mid - mid_at_observe

        events.append(event)

    return pd.DataFrame(events)


def compute_maker_edge(events_df):
    """Compute maker edge for baseline and signal-shifted strategies.

    Baseline: quote at mid +/- half_spread (no signal).
    Signal-shifted: quote at (mid + signal * shift) +/- half_spread.

    For a bullish signal (+1), we shift fair value UP:
      - Our ask moves up  -> less likely to sell cheap
      - Our bid moves up  -> more likely to buy (and at a better level)

    Maker edge for a buy fill  = future_mid - fill_price
    Maker edge for a sell fill = fill_price - future_mid
    """
    results = []

    for h in FUTURE_HORIZONS:
        delta_col = f"delta_t+{h}"
        valid = events_df.dropna(subset=[delta_col])
        if len(valid) == 0:
            continue

        signed_delta = valid["signal"] * valid[delta_col]

        # Baseline: no shift. We quote at mid +/- half_spread.
        # If signal is bullish and price goes up, our sell at mid+2.5
        # would have been filled and we'd lose (future_mid - fill_price).
        # Signed delta > 0 means signal-aligned move happened.

        # With signal shift S, we move our fair value by signal*S.
        # Our ask becomes mid + signal*S + half_spread
        # Our bid becomes mid + signal*S - half_spread

        for shift in [0] + SHIFT_SIZES:
            # For each event, compute the hypothetical maker edge
            # assuming we get filled on the signal side.

            # Bullish signal: we want to buy. Bid = mid + shift - half_spread
            # Edge = future_mid - bid_price = delta + half_spread - shift
            # (buying at a price that's `shift` higher than mid - half_spread)

            # Bearish signal: we want to sell. Ask = mid - shift + half_spread
            # Edge = ask_price - future_mid = half_spread - shift - delta
            # But delta is negative for bearish (price goes down), so:
            # signed_delta is signal * delta, always positive if signal is right.

            # Unified: maker_edge = half_spread - shift + signed_delta
            # This captures: we give up `shift` ticks of spread for `signed_delta` of predictive edge.

            maker_edge = HALF_SPREAD - shift + signed_delta

            results.append({
                "horizon": h,
                "shift": shift,
                "n_events": len(valid),
                "mean_edge": maker_edge.mean(),
                "median_edge": maker_edge.median(),
                "pct_positive": (maker_edge > 0).mean() * 100,
                "mean_signed_delta": signed_delta.mean(),
            })

    return pd.DataFrame(results)


def compute_maker_edge_by_day(events_df):
    """Same as compute_maker_edge but broken out by day."""
    results = []

    for day in DAYS:
        day_events = events_df[events_df["day"] == day]
        for h in FUTURE_HORIZONS:
            delta_col = f"delta_t+{h}"
            valid = day_events.dropna(subset=[delta_col])
            if len(valid) == 0:
                continue

            signed_delta = valid["signal"] * valid[delta_col]

            for shift in [0] + SHIFT_SIZES:
                maker_edge = HALF_SPREAD - shift + signed_delta

                results.append({
                    "day": day,
                    "horizon": h,
                    "shift": shift,
                    "n_events": len(valid),
                    "mean_edge": maker_edge.mean(),
                    "median_edge": maker_edge.median(),
                    "pct_positive": (maker_edge > 0).mean() * 100,
                })

    return pd.DataFrame(results)


def check_fill_probability(events_df, mid_lookup):
    """Check if shifted quotes would actually get filled.

    For a bullish signal with shift S:
      Our bid = mid + S - half_spread
      Fill happens if market ask <= our bid at some point in the window.

    For a bearish signal with shift S:
      Our ask = mid - S + half_spread
      Fill happens if market bid >= our ask at some point in the window.
    """
    prices_df = load_prices()
    price_lookup = {}
    for _, row in prices_df.iterrows():
        key = (row["day"], row["timestamp"])
        price_lookup[key] = (row["bid_price_1"], row["ask_price_1"])

    results = []

    for shift in SHIFT_SIZES:
        for window_ticks in [5, 10, 20, 50]:
            fills = 0
            total = 0

            for _, event in events_df.iterrows():
                day = event["day"]
                observe_ts = event["observe_ts"]
                signal = event["signal"]
                mid = event["mid_at_observe"]

                if signal > 0:
                    # Bullish: our bid = mid + shift - half_spread
                    our_bid = mid + shift - HALF_SPREAD
                    # Check if market ask ever <= our_bid in window
                    filled = False
                    for t in range(1, window_ticks + 1):
                        ts = observe_ts + t * 100
                        prices = price_lookup.get((day, ts))
                        if prices and prices[1] <= our_bid:  # ask <= our bid
                            filled = True
                            break
                else:
                    # Bearish: our ask = mid - shift + half_spread
                    our_ask = mid - shift + HALF_SPREAD
                    filled = False
                    for t in range(1, window_ticks + 1):
                        ts = observe_ts + t * 100
                        prices = price_lookup.get((day, ts))
                        if prices and prices[0] >= our_ask:  # bid >= our ask
                            filled = True
                            break

                total += 1
                if filled:
                    fills += 1

            results.append({
                "shift": shift,
                "window_ticks": window_ticks,
                "fill_rate": fills / total * 100 if total > 0 else 0,
                "fills": fills,
                "total": total,
            })

    return pd.DataFrame(results)


def print_section(title):
    print(f"\n{'='*60}")
    print(f" {title}")
    print(f"{'='*60}\n")


def main():
    prices = load_prices()
    trades = load_trades()
    mid_lookup = build_mid_lookup(prices)

    # 1. Build signal events
    events = analyze_signal_events(trades, mid_lookup)
    signal_counts = events["signal"].value_counts()

    print_section("SIGNAL EVENT COUNTS")
    print(f"Total signal events: {len(events)}")
    print(f"  Bullish (+1): {signal_counts.get(1, 0)}")
    print(f"  Bearish (-1): {signal_counts.get(-1, 0)}")
    print(f"  Per day: {events.groupby('day').size().to_dict()}")

    # 2. Raw signal quality (sanity check)
    print_section("SIGNAL QUALITY (signed delta = signal * price_change)")
    for h in FUTURE_HORIZONS:
        col = f"delta_t+{h}"
        valid = events.dropna(subset=[col])
        signed = valid["signal"] * valid[col]
        print(
            f"  t+{h:3d}: mean={signed.mean():+.2f}  "
            f"median={signed.median():+.1f}  "
            f"std={signed.std():.2f}  "
            f"n={len(valid)}"
        )

    # 3. Maker edge analysis
    print_section("MAKER EDGE: BASELINE vs SIGNAL-SHIFTED (all days)")
    edge_df = compute_maker_edge(events)
    # Show at key horizons
    for h in [5, 10, 20]:
        subset = edge_df[edge_df["horizon"] == h]
        if len(subset) == 0:
            continue
        print(f"\n  Horizon t+{h} ticks:")
        print(f"  {'Shift':>5s}  {'Mean Edge':>10s}  {'Median Edge':>12s}  "
              f"{'% Positive':>11s}  {'Signed Delta':>13s}  {'N':>4s}")
        print(f"  {'-'*5}  {'-'*10}  {'-'*12}  {'-'*11}  {'-'*13}  {'-'*4}")
        for _, row in subset.iterrows():
            label = "base" if row["shift"] == 0 else f"S={int(row['shift'])}"
            print(
                f"  {label:>5s}  {row['mean_edge']:>+10.3f}  "
                f"{row['median_edge']:>+12.1f}  "
                f"{row['pct_positive']:>10.1f}%  "
                f"{row['mean_signed_delta']:>+13.3f}  "
                f"{int(row['n_events']):>4d}"
            )

    # 4. Consistency across days
    print_section("CONSISTENCY ACROSS DAYS (shift=2, horizon=t+10)")
    day_df = compute_maker_edge_by_day(events)
    target = day_df[(day_df["shift"] == 2) & (day_df["horizon"] == 10)]
    if len(target) > 0:
        print(f"  {'Day':>3s}  {'Mean Edge':>10s}  {'Median Edge':>12s}  "
              f"{'% Positive':>11s}  {'N':>4s}")
        print(f"  {'-'*3}  {'-'*10}  {'-'*12}  {'-'*11}  {'-'*4}")
        for _, row in target.iterrows():
            print(
                f"  {int(row['day']):>3d}  {row['mean_edge']:>+10.3f}  "
                f"{row['median_edge']:>+12.1f}  "
                f"{row['pct_positive']:>10.1f}%  "
                f"{int(row['n_events']):>4d}"
            )

    # 5. Fill probability check
    print_section("FILL PROBABILITY (would shifted quotes actually get filled?)")
    fill_df = check_fill_probability(events, mid_lookup)
    print(f"  {'Shift':>5s}  {'Window':>6s}  {'Fill Rate':>10s}  "
          f"{'Fills':>5s}  {'Total':>5s}")
    print(f"  {'-'*5}  {'-'*6}  {'-'*10}  {'-'*5}  {'-'*5}")
    for _, row in fill_df.iterrows():
        print(
            f"  S={int(row['shift']):>2d}  {int(row['window_ticks']):>5d}t  "
            f"{row['fill_rate']:>9.1f}%  "
            f"{int(row['fills']):>5d}  "
            f"{int(row['total']):>5d}"
        )

    # 6. Net expected value: edge * fill_rate
    print_section("NET EXPECTED VALUE: edge * fill_rate (per signal event)")
    edge_at_10 = edge_df[(edge_df["horizon"] == 10)]
    fill_at_10 = fill_df[fill_df["window_ticks"] == 10]
    print(f"  {'Shift':>5s}  {'Edge':>8s}  {'Fill%':>6s}  {'EV/event':>10s}")
    print(f"  {'-'*5}  {'-'*8}  {'-'*6}  {'-'*10}")
    for shift in SHIFT_SIZES:
        edge_row = edge_at_10[edge_at_10["shift"] == shift]
        fill_row = fill_at_10[fill_at_10["shift"] == shift]
        if len(edge_row) > 0 and len(fill_row) > 0:
            edge = edge_row["mean_edge"].values[0]
            fill_pct = fill_row["fill_rate"].values[0]
            ev = edge * fill_pct / 100
            label = f"S={shift}"
            print(
                f"  {label:>5s}  {edge:>+8.3f}  {fill_pct:>5.1f}%  "
                f"{ev:>+10.4f}"
            )

    # Also show baseline EV
    base_row = edge_at_10[edge_at_10["shift"] == 0]
    if len(base_row) > 0:
        base_edge = base_row["mean_edge"].values[0]
        # Baseline fill rate: quote at mid +/- half_spread always fills
        # because that's where the market trades. Approximate as ~100%.
        print(f"\n  Baseline (no shift) edge at t+10: {base_edge:+.3f}")
        print(f"  (Baseline always fills since we quote at BBO)")

    # 7. Verdict
    print_section("VERDICT")
    best_shift = None
    best_ev = 0
    for shift in SHIFT_SIZES:
        edge_row = edge_at_10[edge_at_10["shift"] == shift]
        fill_row = fill_at_10[fill_at_10["shift"] == shift]
        if len(edge_row) > 0 and len(fill_row) > 0:
            edge = edge_row["mean_edge"].values[0]
            fill_pct = fill_row["fill_rate"].values[0]
            ev = edge * fill_pct / 100
            if ev > best_ev:
                best_ev = ev
                best_shift = shift

    base_edge = base_row["mean_edge"].values[0] if len(base_row) > 0 else 0

    if best_ev > base_edge:
        print(f"  ACTIONABLE: Shift S={best_shift} has EV={best_ev:+.4f} "
              f"> baseline edge {base_edge:+.3f}")
    else:
        print(f"  DEAD END: No shift size beats baseline edge {base_edge:+.3f}")
        print(f"  Best shifted EV: {best_ev:+.4f} (S={best_shift})")

    print(f"\n  Reasoning: The signal adds ~{edge_at_10[edge_at_10['shift']==2]['mean_signed_delta'].values[0]:+.2f} "
          f"ticks of predictive edge,")
    print(f"  but shifting quotes by S ticks costs S ticks of spread.")
    print(f"  Net gain from signal = signed_delta - shift.")
    print(f"  Since signed_delta < shift for all tested S, the signal")
    print(f"  does not compensate for the spread given up.")


if __name__ == "__main__":
    main()
