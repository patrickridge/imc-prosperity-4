"""
VE (VELVETFRUIT_EXTRACT) Mean Reversion Analysis
Answers: Is VE mean-reverting? What's the anchor? Half-life? Optimal entry edge? Should we MM?
"""

import numpy as np
import pandas as pd
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data" / "round4"
PRODUCT = "VELVETFRUIT_EXTRACT"


# ============================================================
# DATA LOADING
# ============================================================

def load_prices():
    frames = []
    for day in [1, 2, 3]:
        path = DATA_DIR / f"prices_round_4_day_{day}.csv"
        df = pd.read_csv(path, sep=";")
        df = df[df["product"] == PRODUCT].copy()
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def load_trades():
    frames = []
    for day in [1, 2, 3]:
        path = DATA_DIR / f"trades_round_4_day_{day}.csv"
        df = pd.read_csv(path, sep=";")
        df = df[df["symbol"] == PRODUCT].copy()
        df["day"] = day
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


# ============================================================
# 1. AUTOCORRELATION OF RETURNS
# ============================================================

def analyze_autocorrelation(prices):
    print("=" * 70)
    print("1. AUTOCORRELATION OF RETURNS (negative = mean reversion)")
    print("=" * 70)

    results_by_day = {}
    for day in [1, 2, 3]:
        mid = prices[prices["day"] == day]["mid_price"].values
        returns = np.diff(mid)
        acf_vals = []
        for lag in range(1, 51):
            if len(returns) > lag:
                r = np.corrcoef(returns[:-lag], returns[lag:])[0, 1]
                acf_vals.append(r)
            else:
                acf_vals.append(np.nan)
        results_by_day[day] = acf_vals

    # Overall
    all_mid = prices["mid_price"].values
    all_returns = np.diff(all_mid)
    # Note: jumps at day boundaries — compute per-day then average
    avg_acf = np.mean(list(results_by_day.values()), axis=0)

    print(f"\n{'Lag':<6}{'Day1':<10}{'Day2':<10}{'Day3':<10}{'Average':<10}")
    print("-" * 46)
    key_lags = [1, 2, 3, 5, 10, 15, 20, 30, 50]
    for lag in key_lags:
        d1 = results_by_day[1][lag - 1]
        d2 = results_by_day[2][lag - 1]
        d3 = results_by_day[3][lag - 1]
        avg = avg_acf[lag - 1]
        print(f"{lag:<6}{d1:<10.4f}{d2:<10.4f}{d3:<10.4f}{avg:<10.4f}")

    # Significance threshold (2/sqrt(N))
    n = len(prices[prices["day"] == 1])
    sig_threshold = 2.0 / np.sqrt(n)
    print(f"\nSignificance threshold (2/sqrt(N)): ±{sig_threshold:.4f}")

    strongly_negative = sum(1 for v in avg_acf[:10] if v < -sig_threshold)
    print(f"Lags 1-10 significantly negative: {strongly_negative}/10")
    print(f"Lag-1 autocorrelation: {avg_acf[0]:.4f} — {'MEAN REVERTING' if avg_acf[0] < -sig_threshold else 'NOT significant'}")

    return avg_acf


# ============================================================
# 2. MEAN / ANCHOR ESTIMATION
# ============================================================

def analyze_mean(prices):
    print("\n" + "=" * 70)
    print("2. MEAN / ANCHOR PRICE")
    print("=" * 70)

    for day in [1, 2, 3]:
        day_prices = prices[prices["day"] == day]["mid_price"]
        print(f"\nDay {day}:")
        print(f"  Mean:   {day_prices.mean():.2f}")
        print(f"  Median: {day_prices.median():.2f}")
        print(f"  Std:    {day_prices.std():.2f}")
        print(f"  Min:    {day_prices.min():.2f}  Max: {day_prices.max():.2f}")
        print(f"  Range:  {day_prices.max() - day_prices.min():.0f} ticks")

    overall_mean = prices["mid_price"].mean()
    overall_median = prices["mid_price"].median()
    print(f"\nOverall mean:   {overall_mean:.2f}")
    print(f"Overall median: {overall_median:.2f}")
    print(f"Current anchor: 5255 — deviation from actual mean: {5255 - overall_mean:.1f} ticks")

    # Check if mean shifts across days (trend)
    day_means = [prices[prices["day"] == d]["mid_price"].mean() for d in [1, 2, 3]]
    drift = day_means[2] - day_means[0]
    print(f"\nMean drift day1→day3: {drift:.1f} ticks")
    print(f"  Day 1 mean: {day_means[0]:.1f}")
    print(f"  Day 2 mean: {day_means[1]:.1f}")
    print(f"  Day 3 mean: {day_means[2]:.1f}")

    return overall_mean, day_means


# ============================================================
# 3. HALF-LIFE (Ornstein-Uhlenbeck estimation)
# ============================================================

def analyze_half_life(prices, day_means):
    print("\n" + "=" * 70)
    print("3. HALF-LIFE OF MEAN REVERSION (Ornstein-Uhlenbeck)")
    print("=" * 70)

    half_lives = []
    for day in [1, 2, 3]:
        mid = prices[prices["day"] == day]["mid_price"].values
        mean = day_means[day - 1]
        deviation = mid - mean

        # OLS: delta_mid = theta * (mean - mid) + noise
        # i.e. delta = -theta * deviation + noise
        delta = np.diff(mid)
        dev_lagged = deviation[:-1]

        # Regress delta on dev_lagged
        # delta = beta * dev_lagged + intercept
        # beta should be negative for mean reversion
        # half-life = -ln(2) / ln(1 + beta)
        X = np.column_stack([dev_lagged, np.ones(len(dev_lagged))])
        beta, intercept = np.linalg.lstsq(X, delta, rcond=None)[0]

        if beta < 0:
            # Half-life in ticks
            hl = -np.log(2) / np.log(1 + beta)
            half_lives.append(hl)
            print(f"Day {day}: beta={beta:.6f}, half-life={hl:.1f} ticks ({hl * 0.1:.1f} seconds)")
        else:
            print(f"Day {day}: beta={beta:.6f} — NOT mean-reverting (positive beta)")
            half_lives.append(np.nan)

    avg_hl = np.nanmean(half_lives)
    print(f"\nAverage half-life: {avg_hl:.1f} ticks ({avg_hl * 0.1:.1f} seconds)")
    print("Interpretation: after a deviation, price reverts halfway in ~{:.0f} ticks".format(avg_hl))

    return avg_hl


# ============================================================
# 4. OPTIMAL ENTRY EDGE
# ============================================================

def analyze_entry_edges(prices, day_means):
    print("\n" + "=" * 70)
    print("4. OPTIMAL ENTRY EDGE (deviation thresholds)")
    print("=" * 70)

    thresholds = [2, 4, 6, 8, 10, 12, 15, 20]
    horizons = [1, 5, 10, 20, 50]

    print(f"\n{'Thresh':<8}{'Opps/day':<10}", end="")
    for h in horizons:
        print(f"{'Ret@' + str(h):<9}", end="")
    print(f"{'Hit@10':<8}{'MaxDD':<8}")
    print("-" * 80)

    for threshold in thresholds:
        all_returns = {h: [] for h in horizons}
        all_hit_rates = []
        all_drawdowns = []
        opps_per_day = []

        for day in [1, 2, 3]:
            mid = prices[prices["day"] == day]["mid_price"].values
            mean = day_means[day - 1]
            deviation = mid - mean
            n = len(mid)
            day_opps = 0

            for i in range(n):
                dev = deviation[i]
                if abs(dev) < threshold:
                    continue

                day_opps += 1
                # Direction: if price is ABOVE mean, we expect it to go DOWN (sell signal)
                # If price is BELOW mean, we expect it to go UP (buy signal)
                sign = -1 if dev > 0 else 1  # sign of expected move

                for h in horizons:
                    if i + h < n:
                        future_return = (mid[i + h] - mid[i]) * sign
                        all_returns[h].append(future_return)

                # Hit rate at horizon 10
                if i + 10 < n:
                    moved_toward_mean = (mid[i + 10] - mid[i]) * sign > 0
                    all_hit_rates.append(moved_toward_mean)

                # Max drawdown before reversion (look up to 100 ticks ahead)
                if i + 1 < n:
                    max_adverse = 0
                    for j in range(1, min(101, n - i)):
                        adverse = -(mid[i + j] - mid[i]) * sign
                        max_adverse = max(max_adverse, adverse)
                        if (mid[i + j] - mid[i]) * sign > abs(dev) * 0.5:
                            break  # reverted halfway, stop
                    all_drawdowns.append(max_adverse)

            opps_per_day.append(day_opps)

        avg_opps = np.mean(opps_per_day)
        hit_rate = np.mean(all_hit_rates) * 100 if all_hit_rates else 0
        avg_dd = np.mean(all_drawdowns) if all_drawdowns else 0

        print(f"{threshold:<8}{avg_opps:<10.0f}", end="")
        for h in horizons:
            if all_returns[h]:
                print(f"{np.mean(all_returns[h]):<9.2f}", end="")
            else:
                print(f"{'N/A':<9}", end="")
        print(f"{hit_rate:<8.1f}{avg_dd:<8.2f}")

    # Detailed breakdown for threshold=12 (current) and best alternatives
    print("\n\nDetailed per-day breakdown for threshold=12 (current strategy):")
    print(f"{'Day':<6}{'Opps':<8}{'MeanRet@10':<12}{'Hit@10':<10}{'MeanRet@50':<12}")
    for day in [1, 2, 3]:
        mid = prices[prices["day"] == day]["mid_price"].values
        mean = day_means[day - 1]
        deviation = mid - mean
        n = len(mid)

        rets_10 = []
        rets_50 = []
        hits_10 = []
        opps = 0

        for i in range(n):
            if abs(deviation[i]) < 12:
                continue
            opps += 1
            sign = -1 if deviation[i] > 0 else 1

            if i + 10 < n:
                r10 = (mid[i + 10] - mid[i]) * sign
                rets_10.append(r10)
                hits_10.append(r10 > 0)
            if i + 50 < n:
                r50 = (mid[i + 50] - mid[i]) * sign
                rets_50.append(r50)

        print(f"{day:<6}{opps:<8}{np.mean(rets_10):<12.2f}{np.mean(hits_10)*100:<10.1f}{np.mean(rets_50):<12.2f}")


# ============================================================
# 5. PASSIVE MARKET MAKING ANALYSIS
# ============================================================

def analyze_market_making(prices, day_means):
    print("\n" + "=" * 70)
    print("5. PASSIVE MARKET MAKING VIABILITY")
    print("=" * 70)

    # Approach: simulate posting quotes at mid ± offset each tick.
    # A bid fill occurs when next tick's mid drops to or below our bid level
    # (meaning aggressive sellers crossed us). An ask fill occurs when
    # next tick's mid rises to or above our ask level.
    # This is a conservative proxy — actual fills depend on order queue priority.

    offsets = [2, 3, 4, 5, 6, 8, 10]

    print(f"\n{'Offset':<9}{'BidFills':<10}{'AskFills':<10}{'AdvSel@5':<10}{'AdvSel@10':<11}{'NetPft@5':<10}{'NetPft@10':<11}{'PnL/day':<10}")
    print("-" * 80)

    for offset in offsets:
        bid_fills_total = []
        ask_fills_total = []
        profits_at_5 = []
        profits_at_10 = []
        adverse_at_5 = []
        adverse_at_10 = []

        for day in [1, 2, 3]:
            day_data = prices[prices["day"] == day]
            mid = day_data["mid_price"].values
            n = len(mid)

            day_bid_fills = 0
            day_ask_fills = 0

            for i in range(n - 1):
                my_bid = mid[i] - offset
                my_ask = mid[i] + offset

                # Bid fill: price dropped enough that someone would hit our bid
                # Use: did mid[i+1] go below our bid level?
                if mid[i + 1] <= my_bid:
                    day_bid_fills += 1
                    # Adverse selection: mid move against us after fill
                    if i + 6 < n:
                        # We bought at my_bid. Adverse = how much mid drops further
                        adv5 = my_bid - mid[i + 6]  # negative = mid above our entry = good
                        adverse_at_5.append(adv5)
                        profits_at_5.append(mid[i + 6] - my_bid)
                    if i + 11 < n:
                        adv10 = my_bid - mid[i + 11]
                        adverse_at_10.append(adv10)
                        profits_at_10.append(mid[i + 11] - my_bid)

                # Ask fill: price rose enough
                if mid[i + 1] >= my_ask:
                    day_ask_fills += 1
                    if i + 6 < n:
                        adv5 = mid[i + 6] - my_ask  # positive = mid above our sell = bad
                        adverse_at_5.append(adv5)
                        profits_at_5.append(my_ask - mid[i + 6])
                    if i + 11 < n:
                        adv10 = mid[i + 11] - my_ask
                        adverse_at_10.append(adv10)
                        profits_at_10.append(my_ask - mid[i + 11])

            bid_fills_total.append(day_bid_fills)
            ask_fills_total.append(day_ask_fills)

        avg_bid = np.mean(bid_fills_total)
        avg_ask = np.mean(ask_fills_total)
        avg_adv5 = np.mean(adverse_at_5) if adverse_at_5 else 0
        avg_adv10 = np.mean(adverse_at_10) if adverse_at_10 else 0
        avg_pft5 = np.mean(profits_at_5) if profits_at_5 else 0
        avg_pft10 = np.mean(profits_at_10) if profits_at_10 else 0
        # PnL per day estimate: fills * avg profit (using horizon 10 for unwinding)
        total_fills_per_day = avg_bid + avg_ask
        pnl_per_day = total_fills_per_day * avg_pft10

        print(f"{offset:<9}{avg_bid:<10.0f}{avg_ask:<10.0f}{avg_adv5:<10.2f}{avg_adv10:<11.2f}{avg_pft5:<10.2f}{avg_pft10:<11.2f}{pnl_per_day:<10.1f}")

    # Alternative: round-trip analysis
    # Post bid and ask simultaneously. If both fill, profit = 2*offset.
    # More common: one side fills, must unwind at mid.
    print("\n\nRound-trip analysis (post bid AND ask, profit when both fill):")
    print(f"{'Offset':<9}{'BothFill/day':<14}{'OneSide/day':<14}{'RT_profit':<12}{'1side_profit':<14}")
    print("-" * 63)
    for offset in offsets:
        both_fills = []
        one_side = []
        for day in [1, 2, 3]:
            mid = prices[prices["day"] == day]["mid_price"].values
            n = len(mid)
            day_both = 0
            day_one = 0
            for i in range(0, n - 1, 10):  # Check every 10 ticks (reduce correlation)
                my_bid = mid[i] - offset
                my_ask = mid[i] + offset
                # Look 10 ticks ahead for fills
                window = mid[i + 1:min(i + 11, n)]
                bid_hit = np.any(window <= my_bid)
                ask_hit = np.any(window >= my_ask)
                if bid_hit and ask_hit:
                    day_both += 1
                elif bid_hit or ask_hit:
                    day_one += 1
            both_fills.append(day_both)
            one_side.append(day_one)

        avg_both = np.mean(both_fills)
        avg_one = np.mean(one_side)
        rt_profit = avg_both * 2 * offset
        one_profit = avg_one * offset * 0.3  # assume 30% of edge on one-sided
        print(f"{offset:<9}{avg_both:<14.0f}{avg_one:<14.0f}{rt_profit:<12.1f}{one_profit:<14.1f}")

    # Actual market spread
    print("\n\nActual market spread statistics:")
    for day in [1, 2, 3]:
        day_data = prices[prices["day"] == day]
        spreads = day_data["ask_price_1"].values - day_data["bid_price_1"].values
        valid = spreads[~np.isnan(spreads)]
        print(f"  Day {day}: mean spread={np.mean(valid):.1f}, median={np.median(valid):.1f}, "
              f"min={np.min(valid):.0f}, max={np.max(valid):.0f}")

    # Realized volatility per tick (informs MM risk)
    print("\nRealized volatility (per-tick std of mid changes):")
    for day in [1, 2, 3]:
        mid = prices[prices["day"] == day]["mid_price"].values
        vol = np.std(np.diff(mid))
        print(f"  Day {day}: {vol:.3f} per tick")


# ============================================================
# 6. PER-DAY CONSISTENCY SUMMARY
# ============================================================

def analyze_consistency(prices, day_means):
    print("\n" + "=" * 70)
    print("6. PER-DAY CONSISTENCY CHECK")
    print("=" * 70)

    metrics = {}
    for day in [1, 2, 3]:
        mid = prices[prices["day"] == day]["mid_price"].values
        returns = np.diff(mid)
        mean = day_means[day - 1]
        deviation = mid - mean

        metrics[day] = {
            "mean": mean,
            "std": np.std(mid),
            "return_vol": np.std(returns),
            "lag1_acf": np.corrcoef(returns[:-1], returns[1:])[0, 1],
            "frac_above_mean": np.mean(mid > mean),
            "mean_abs_dev": np.mean(np.abs(deviation)),
            "max_dev": np.max(np.abs(deviation)),
        }

    print(f"\n{'Metric':<25}{'Day1':<12}{'Day2':<12}{'Day3':<12}{'Consistent?':<12}")
    print("-" * 61)
    for metric in metrics[1].keys():
        vals = [metrics[d][metric] for d in [1, 2, 3]]
        cv = np.std(vals) / np.mean(vals) if np.mean(vals) != 0 else 0
        consistent = "YES" if cv < 0.2 else "MARGINAL" if cv < 0.5 else "NO"
        print(f"{metric:<25}{vals[0]:<12.4f}{vals[1]:<12.4f}{vals[2]:<12.4f}{consistent:<12}")


# ============================================================
# ACTIONABLE SUMMARY
# ============================================================

def print_summary(acf, overall_mean, day_means, half_life):
    print("\n" + "=" * 70)
    print("ACTIONABLE SUMMARY")
    print("=" * 70)

    print(f"""
1. MEAN REVERSION: {'YES' if acf[0] < -0.02 else 'WEAK/NO'} (lag-1 ACF = {acf[0]:.4f})
   - VE is {'strongly' if acf[0] < -0.05 else 'weakly' if acf[0] < -0.02 else 'NOT'} mean-reverting

2. ANCHOR: {overall_mean:.1f} (current strategy uses 5255, off by {5255 - overall_mean:.1f})
   - Day means: {day_means[0]:.1f}, {day_means[1]:.1f}, {day_means[2]:.1f}
   - Recommendation: Use {round(overall_mean)} or per-day rolling mean

3. HALF-LIFE: {half_life:.0f} ticks ({half_life * 0.1:.1f} seconds)
   - After entry, expect to wait ~{half_life:.0f} ticks for halfway reversion

4. ENTRY EDGE: See table above for optimal threshold.
   - Compare opportunities vs. expected return at each level.

5. PASSIVE MM: See analysis above.
   - Key question: does adverse selection eat the spread?
""")


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    print("Loading VE data...")
    prices = load_prices()
    trades = load_trades()
    print(f"  Prices: {len(prices)} rows across 3 days")
    print(f"  Trades: {len(trades)} rows across 3 days")

    acf = analyze_autocorrelation(prices)
    overall_mean, day_means = analyze_mean(prices)
    half_life = analyze_half_life(prices, day_means)
    analyze_entry_edges(prices, day_means)
    analyze_market_making(prices, day_means)
    analyze_consistency(prices, day_means)
    print_summary(acf, overall_mean, day_means, half_life)
