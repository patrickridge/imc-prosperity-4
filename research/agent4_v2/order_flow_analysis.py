"""
Order flow and volume technical analysis for Round 3 alpha discovery.
Tests 4 candidate signals without counterparty IDs.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from collections import defaultdict

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "round3"
RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)

def load_data(day):
    """Load trade and price data for a given day."""
    trades = pd.read_csv(DATA_DIR / f"trades_round_3_day_{day}.csv", sep=";")
    prices = pd.read_csv(DATA_DIR / f"prices_round_3_day_{day}.csv", sep=";")
    return trades, prices

def infer_aggressor(trades, prices):
    """
    Infer whether each trade was buy-aggressor or sell-aggressor.
    If trade price > mid_price, likely buy-aggressor (lifted the ask).
    If trade price < mid_price, likely sell-aggressor (hit the bid).
    If trade price == mid_price, ambiguous—skip or treat as neutral.
    """
    merged = trades.merge(
        prices[["timestamp", "product", "mid_price"]],
        on=["timestamp", "product"],
        how="left"
    )
    merged["aggressor_type"] = None
    buy_mask = merged["price"] > merged["mid_price"]
    sell_mask = merged["price"] < merged["mid_price"]
    merged.loc[buy_mask, "aggressor_type"] = "buy"
    merged.loc[sell_mask, "aggressor_type"] = "sell"
    return merged

def signal1_iceberg_repeat_orders(trades_with_agg, day, symbol):
    """
    Iceberg signal: Detect multiple identical-size or near-identical-size
    aggressor trades at the same price within a 50-tick window.
    """
    df = trades_with_agg[trades_with_agg["symbol"] == symbol].copy()
    df = df.sort_values("timestamp").reset_index(drop=True)

    results = []
    tick_window = 50

    for i in range(len(df)):
        current_ts = df.iloc[i]["timestamp"]
        current_price = df.iloc[i]["price"]
        current_qty = df.iloc[i]["quantity"]

        # Find all trades at the same price within the window
        mask = (df["timestamp"] >= current_ts) & \
               (df["timestamp"] < current_ts + tick_window) & \
               (df["price"] == current_price)

        same_price_trades = df[mask]

        if len(same_price_trades) >= 3:
            quantities = same_price_trades["quantity"].values
            qty_std = np.std(quantities)
            qty_mean = np.mean(quantities)

            # Signal: if quantities are very similar (low std), likely iceberg
            if qty_mean > 0 and qty_std / qty_mean < 0.2:  # < 20% variation
                results.append({
                    "day": day,
                    "symbol": symbol,
                    "trigger_ts": current_ts,
                    "price": current_price,
                    "num_trades": len(same_price_trades),
                    "qty_std_ratio": qty_std / qty_mean,
                    "signal_strength": len(same_price_trades)
                })

    return results

def signal2_volume_burst_predicts_price(trades_with_agg, prices, day, symbol):
    """
    Volume burst signal: Identify clusters where total trade volume
    in a 50-tick window is 3+ std above rolling mean.
    Then check if it predicts price move in next 100-500 ticks.
    """
    df_trades = trades_with_agg[trades_with_agg["symbol"] == symbol].copy()
    df_prices = prices[prices["product"] == symbol].copy()

    if len(df_trades) < 100:
        return []

    df_trades = df_trades.sort_values("timestamp").reset_index(drop=True)
    df_prices = df_prices.sort_values("timestamp").reset_index(drop=True)

    # Compute rolling volume statistics
    tick_window = 50
    rolling_volumes = []
    rolling_timestamps = []

    for i in range(len(df_trades)):
        ts = df_trades.iloc[i]["timestamp"]
        mask = (df_trades["timestamp"] >= ts) & (df_trades["timestamp"] < ts + tick_window)
        vol = df_trades[mask]["quantity"].sum()
        rolling_volumes.append(vol)
        rolling_timestamps.append(ts)

    rolling_volumes = np.array(rolling_volumes)
    rolling_mean = np.mean(rolling_volumes)
    rolling_std = np.std(rolling_volumes)

    results = []

    for i in range(len(df_trades)):
        if rolling_volumes[i] > rolling_mean + 3 * rolling_std:
            # This is a volume burst
            trigger_ts = rolling_timestamps[i]
            trigger_price = df_trades.iloc[i]["price"]

            # Look at price move 100-500 ticks ahead
            mask_future = (df_trades["timestamp"] > trigger_ts + 100) & \
                         (df_trades["timestamp"] <= trigger_ts + 500)

            if mask_future.sum() > 0:
                future_prices = df_trades[mask_future]["price"]
                price_move = (future_prices.mean() - trigger_price) / trigger_price * 100

                results.append({
                    "day": day,
                    "symbol": symbol,
                    "trigger_ts": trigger_ts,
                    "trigger_price": trigger_price,
                    "burst_volume": rolling_volumes[i],
                    "future_price_move_pct": price_move,
                    "burst_strength_std": (rolling_volumes[i] - rolling_mean) / rolling_std
                })

    return results

def signal3_imbalanced_flow_predicts_return(trades_with_agg, day, symbol):
    """
    Imbalanced flow signal: Compute net buy vs sell aggressor flow
    over 100-tick windows. Test if it predicts subsequent returns.
    """
    df = trades_with_agg[trades_with_agg["symbol"] == symbol].copy()

    if len(df) < 100:
        return []

    df = df.sort_values("timestamp").reset_index(drop=True)

    results = []
    tick_window = 100
    lookahead = 100  # How many ticks to look ahead for return

    for i in range(len(df) - lookahead):
        current_ts = df.iloc[i]["timestamp"]

        # Count buy vs sell aggressor trades in current window
        mask_current = (df["timestamp"] >= current_ts) & \
                      (df["timestamp"] < current_ts + tick_window)
        current_window = df[mask_current]

        if len(current_window) < 5:
            continue

        buy_count = (current_window["aggressor_type"] == "buy").sum()
        sell_count = (current_window["aggressor_type"] == "sell").sum()
        total = buy_count + sell_count

        if total == 0:
            continue

        imbalance = (buy_count - sell_count) / total

        # Look at price move ahead
        mask_lookahead = (df["timestamp"] > current_ts + tick_window) & \
                        (df["timestamp"] <= current_ts + tick_window + lookahead)
        lookahead_window = df[mask_lookahead]

        if len(lookahead_window) > 0:
            start_price = current_window.iloc[0]["price"]
            end_price = lookahead_window.iloc[-1]["price"]
            ret = (end_price - start_price) / start_price * 100

            results.append({
                "day": day,
                "symbol": symbol,
                "trigger_ts": current_ts,
                "buy_aggressor_imbalance": imbalance,
                "subsequent_return_pct": ret,
                "buy_count": buy_count,
                "sell_count": sell_count
            })

    return results

def signal4_lob_update_flicker(trades_with_agg, prices, day, symbol):
    """
    Quote-stuffing detection: Find timestamps with abnormally many LOB updates
    (price changes) without trades.
    """
    df_prices = prices[prices["product"] == symbol].copy()

    if len(df_prices) < 50:
        return []

    df_prices = df_prices.sort_values("timestamp").reset_index(drop=True)

    # Count consecutive prices without trades
    results = []
    consecutive_lob = 0

    for i in range(1, len(df_prices)):
        prev_bid = df_prices.iloc[i-1]["bid_price_1"]
        curr_bid = df_prices.iloc[i]["bid_price_1"]

        if prev_bid != curr_bid or \
           df_prices.iloc[i-1]["bid_volume_1"] != df_prices.iloc[i]["bid_volume_1"]:
            consecutive_lob += 1
        else:
            consecutive_lob = 0

        if consecutive_lob >= 10:
            results.append({
                "day": day,
                "symbol": symbol,
                "timestamp": df_prices.iloc[i]["timestamp"],
                "consecutive_lob_updates": consecutive_lob,
                "signal_type": "quote_stuffing"
            })

    return results

def compute_sharpe_signal(results, return_col, weight_col=None):
    """Compute Sharpe-like metric: mean return / std return."""
    if len(results) < 2:
        return None

    returns = np.array([r[return_col] for r in results])

    if np.std(returns) == 0:
        return None

    return np.mean(returns) / np.std(returns)

def main():
    print("=" * 80)
    print("ROUND 3 ORDER FLOW ALPHA DISCOVERY")
    print("=" * 80)

    # Get all products
    trades_d0, _ = load_data(0)
    all_symbols = trades_d0["symbol"].unique()
    print(f"\nFound {len(all_symbols)} products: {sorted(all_symbols)}")

    # Test on day 0 (in-sample), day 1 (validation), hold day 2

    # Signal 1: Iceberg repeat orders
    print("\n" + "=" * 80)
    print("SIGNAL 1: ICEBERG / REPEAT LARGE ORDERS")
    print("=" * 80)

    day0_icebergs = []
    for day in [0, 1]:
        trades, prices = load_data(day)
        trades_agg = infer_aggressor(trades, prices)

        for symbol in all_symbols:
            results = signal1_iceberg_repeat_orders(trades_agg, day, symbol)
            day0_icebergs.extend(results)

    print(f"Day 0 icebergs found: {len([r for r in day0_icebergs if r['day'] == 0])}")
    print(f"Day 1 icebergs found: {len([r for r in day0_icebergs if r['day'] == 1])}")

    if day0_icebergs:
        print(f"Sample (day 0): {day0_icebergs[0] if day0_icebergs else 'None'}")

    # Signal 2: Volume burst predicts price
    print("\n" + "=" * 80)
    print("SIGNAL 2: VOLUME BURST PREDICTS PRICE MOVE")
    print("=" * 80)

    day0_bursts = []
    for day in [0, 1]:
        trades, prices = load_data(day)
        trades_agg = infer_aggressor(trades, prices)

        for symbol in all_symbols:
            results = signal2_volume_burst_predicts_price(trades_agg, prices, day, symbol)
            day0_bursts.extend(results)

    print(f"Day 0 bursts found: {len([r for r in day0_bursts if r['day'] == 0])}")
    print(f"Day 1 bursts found: {len([r for r in day0_bursts if r['day'] == 1])}")

    if day0_bursts:
        sharpe_d0 = compute_sharpe_signal([r for r in day0_bursts if r['day'] == 0], "future_price_move_pct")
        sharpe_d1 = compute_sharpe_signal([r for r in day0_bursts if r['day'] == 1], "future_price_move_pct")
        print(f"Day 0 Sharpe (in-sample): {sharpe_d0:.3f}" if sharpe_d0 else "Day 0 Sharpe: N/A")
        print(f"Day 1 Sharpe (validation): {sharpe_d1:.3f}" if sharpe_d1 else "Day 1 Sharpe: N/A")
        if day0_bursts:
            print(f"Sample (day 0): {day0_bursts[0] if day0_bursts else 'None'}")

    # Signal 3: Imbalanced flow predicts return
    print("\n" + "=" * 80)
    print("SIGNAL 3: IMBALANCED FLOW PREDICTS RETURN")
    print("=" * 80)

    day0_imbalance = []
    for day in [0, 1]:
        trades, prices = load_data(day)
        trades_agg = infer_aggressor(trades, prices)

        for symbol in all_symbols:
            results = signal3_imbalanced_flow_predicts_return(trades_agg, day, symbol)
            day0_imbalance.extend(results)

    print(f"Day 0 observations: {len([r for r in day0_imbalance if r['day'] == 0])}")
    print(f"Day 1 observations: {len([r for r in day0_imbalance if r['day'] == 1])}")

    if day0_imbalance:
        sharpe_d0 = compute_sharpe_signal([r for r in day0_imbalance if r['day'] == 0], "subsequent_return_pct")
        sharpe_d1 = compute_sharpe_signal([r for r in day0_imbalance if r['day'] == 1], "subsequent_return_pct")
        print(f"Day 0 Sharpe (in-sample): {sharpe_d0:.3f}" if sharpe_d0 else "Day 0 Sharpe: N/A")
        print(f"Day 1 Sharpe (validation): {sharpe_d1:.3f}" if sharpe_d1 else "Day 1 Sharpe: N/A")
        if day0_imbalance:
            print(f"Sample (day 0): {day0_imbalance[0] if day0_imbalance else 'None'}")

    # Signal 4: Quote stuffing
    print("\n" + "=" * 80)
    print("SIGNAL 4: QUOTE STUFFING / FLICKER PATTERNS")
    print("=" * 80)

    day0_flicker = []
    for day in [0, 1]:
        trades, prices = load_data(day)

        for symbol in all_symbols:
            results = signal4_lob_update_flicker(trades, prices, day, symbol)
            day0_flicker.extend(results)

    print(f"Day 0 flicker events: {len([r for r in day0_flicker if r['day'] == 0])}")
    print(f"Day 1 flicker events: {len([r for r in day0_flicker if r['day'] == 1])}")

    # Detailed analysis on day 0 and 1 for signal 3 (most promising based on structure)
    print("\n" + "=" * 80)
    print("DETAILED SIGNAL 3 ANALYSIS: IMBALANCED FLOW")
    print("=" * 80)

    imbalance_day0 = [r for r in day0_imbalance if r['day'] == 0]
    imbalance_day1 = [r for r in day0_imbalance if r['day'] == 1]

    if imbalance_day0:
        df_d0 = pd.DataFrame(imbalance_day0)
        print(f"\nDay 0 (in-sample):")
        print(f"  Total observations: {len(df_d0)}")
        print(f"  Mean imbalance: {df_d0['buy_aggressor_imbalance'].mean():.3f}")
        print(f"  Mean return: {df_d0['subsequent_return_pct'].mean():.4f}%")
        print(f"  Correlation (imbalance vs return): {df_d0['buy_aggressor_imbalance'].corr(df_d0['subsequent_return_pct']):.3f}")

        # Sharpe per direction
        positive_imb = df_d0[df_d0['buy_aggressor_imbalance'] > 0.1]
        negative_imb = df_d0[df_d0['buy_aggressor_imbalance'] < -0.1]

        print(f"\n  Buy-heavy trades (imbalance > 0.1): {len(positive_imb)}")
        if len(positive_imb) > 0:
            print(f"    Mean return: {positive_imb['subsequent_return_pct'].mean():.4f}%")
            print(f"    Std return: {positive_imb['subsequent_return_pct'].std():.4f}%")
            if positive_imb['subsequent_return_pct'].std() > 0:
                print(f"    Sharpe: {positive_imb['subsequent_return_pct'].mean() / positive_imb['subsequent_return_pct'].std():.3f}")

        print(f"\n  Sell-heavy trades (imbalance < -0.1): {len(negative_imb)}")
        if len(negative_imb) > 0:
            print(f"    Mean return: {negative_imb['subsequent_return_pct'].mean():.4f}%")
            print(f"    Std return: {negative_imb['subsequent_return_pct'].std():.4f}%")
            if negative_imb['subsequent_return_pct'].std() > 0:
                print(f"    Sharpe: {negative_imb['subsequent_return_pct'].mean() / negative_imb['subsequent_return_pct'].std():.3f}")

    if imbalance_day1:
        df_d1 = pd.DataFrame(imbalance_day1)
        print(f"\nDay 1 (validation):")
        print(f"  Total observations: {len(df_d1)}")
        print(f"  Mean imbalance: {df_d1['buy_aggressor_imbalance'].mean():.3f}")
        print(f"  Mean return: {df_d1['subsequent_return_pct'].mean():.4f}%")
        print(f"  Correlation (imbalance vs return): {df_d1['buy_aggressor_imbalance'].corr(df_d1['subsequent_return_pct']):.3f}")

        positive_imb = df_d1[df_d1['buy_aggressor_imbalance'] > 0.1]
        negative_imb = df_d1[df_d1['buy_aggressor_imbalance'] < -0.1]

        print(f"\n  Buy-heavy trades (imbalance > 0.1): {len(positive_imb)}")
        if len(positive_imb) > 0:
            print(f"    Mean return: {positive_imb['subsequent_return_pct'].mean():.4f}%")
            print(f"    Std return: {positive_imb['subsequent_return_pct'].std():.4f}%")
            if positive_imb['subsequent_return_pct'].std() > 0:
                print(f"    Sharpe: {positive_imb['subsequent_return_pct'].mean() / positive_imb['subsequent_return_pct'].std():.3f}")

        print(f"\n  Sell-heavy trades (imbalance < -0.1): {len(negative_imb)}")
        if len(negative_imb) > 0:
            print(f"    Mean return: {negative_imb['subsequent_return_pct'].mean():.4f}%")
            print(f"    Std return: {negative_imb['subsequent_return_pct'].std():.4f}%")
            if negative_imb['subsequent_return_pct'].std() > 0:
                print(f"    Sharpe: {negative_imb['subsequent_return_pct'].mean() / negative_imb['subsequent_return_pct'].std():.3f}")

    # Save results
    pd.DataFrame(day0_imbalance).to_csv(RESULTS_DIR / "imbalance_signal_results.csv", index=False)
    pd.DataFrame(day0_bursts).to_csv(RESULTS_DIR / "volume_burst_results.csv", index=False)
    pd.DataFrame(day0_icebergs).to_csv(RESULTS_DIR / "iceberg_results.csv", index=False)

    print("\n" + "=" * 80)
    print("Results saved to research/agent4_v2/results/")
    print("=" * 80)

if __name__ == "__main__":
    main()
