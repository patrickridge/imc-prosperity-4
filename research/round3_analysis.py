#!/usr/bin/env python3
"""
Round 3 Voucher Analysis: Extract call option bounds, IV smile, volatility.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from scipy.optimize import brentq
import warnings

warnings.filterwarnings('ignore')

DATA_DIR = Path('/sessions/amazing-upbeat-volta/mnt/imc-prosperity-4/data/round3')

# Black-Scholes call price with zero risk-free rate
def bs_call(S, K, T, sigma):
    if T <= 0 or sigma <= 0:
        return max(S - K, 0)
    from scipy.stats import norm
    d1 = (np.log(S / K) + (sigma ** 2 / 2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    return S * norm.cdf(d1) - K * norm.cdf(d2)

def bs_delta(S, K, T, sigma):
    if T <= 0 or sigma <= 0:
        return 1.0 if S > K else 0.0
    from scipy.stats import norm
    d1 = (np.log(S / K) + (sigma ** 2 / 2) * T) / (sigma * np.sqrt(T))
    return norm.cdf(d1)

def extract_iv(market_price, S, K, T, initial_guess=0.3):
    """Solve for IV using bisection."""
    if T <= 0.001:
        return np.nan

    try:
        def objective(sigma):
            return bs_call(S, K, T, sigma) - market_price

        # Check bounds
        low_price = max(S - K, 0)
        high_price = S

        if market_price < low_price - 0.01 or market_price > high_price + 0.01:
            return np.nan

        if objective(0.01) > 0:
            return np.nan
        if objective(10.0) < 0:
            return np.nan

        iv = brentq(objective, 0.01, 10.0, xtol=1e-6)
        return iv
    except:
        return np.nan

def load_and_analyze_day(day_idx):
    """Load prices, compute bounds and IV for a day."""
    price_file = DATA_DIR / f'prices_round_3_day_{day_idx}.csv'
    df = pd.read_csv(price_file, sep=';')

    # Filter vouchers
    vouchers = [c for c in df['product'].unique() if c.startswith('VEV_')]
    underlying = 'VELVETFRUIT_EXTRACT'

    results = []

    for ts in df['timestamp'].unique():
        ts_data = df[df['timestamp'] == ts]

        # Get underlying mid price
        underlying_row = ts_data[ts_data['product'] == underlying]
        if underlying_row.empty:
            continue

        S = underlying_row['mid_price'].values[0]

        for voucher in vouchers:
            voucher_row = ts_data[ts_data['product'] == voucher]
            if voucher_row.empty:
                continue

            bid_1 = voucher_row['bid_price_1'].values[0]
            ask_1 = voucher_row['ask_price_1'].values[0]
            mid = voucher_row['mid_price'].values[0]

            K = int(voucher.split('_')[1])

            # Skip invalid prices
            if pd.isna(bid_1) or pd.isna(ask_1) or bid_1 <= 0 or ask_1 <= 0:
                continue

            # Time to expiry: assume day 0 = 3 days, day 1 = 2 days, day 2 = 1 day
            T = (3 - day_idx) / 365.0

            # Test call option bounds
            lower_bound = max(S - K, 0)
            upper_bound = S

            violation = None
            if mid < lower_bound - 0.1:
                violation = 'BELOW_LOWER'
            elif mid > upper_bound + 0.1:
                violation = 'ABOVE_UPPER'

            # Extract IV from mid price
            iv = extract_iv(mid, S, K, T)

            # Compute delta
            if not np.isnan(iv) and iv > 0:
                delta = bs_delta(S, K, T, iv)
            else:
                delta = np.nan

            results.append({
                'day': day_idx,
                'timestamp': ts,
                'product': voucher,
                'strike': K,
                'S': S,
                'bid': bid_1,
                'mid': mid,
                'ask': ask_1,
                'spread': ask_1 - bid_1,
                'T': T,
                'lower_bound': lower_bound,
                'upper_bound': upper_bound,
                'violation': violation,
                'IV': iv,
                'delta': delta,
            })

    return pd.DataFrame(results)

def analyze_underlying_vol(day_idx):
    """Compute realized vol of underlying."""
    price_file = DATA_DIR / f'prices_round_3_day_{day_idx}.csv'
    df = pd.read_csv(price_file, sep=';')

    underlying_df = df[df['product'] == 'VELVETFRUIT_EXTRACT'].copy()
    underlying_df = underlying_df.sort_values('timestamp')

    mid_prices = underlying_df['mid_price'].values
    log_returns = np.diff(np.log(mid_prices + 1e-6))  # avoid log(0)

    realized_vol = np.std(log_returns) * np.sqrt(250)  # annualized

    return {
        'day': day_idx,
        'realized_vol': realized_vol,
        'num_ticks': len(mid_prices),
    }

if __name__ == '__main__':
    print("=" * 80)
    print("ROUND 3 VOUCHER ANALYSIS")
    print("=" * 80)

    all_data = []
    for day_idx in [0, 1, 2]:
        print(f"\nDay {day_idx}:")
        day_data = load_and_analyze_day(day_idx)
        all_data.append(day_data)

        # Summary stats
        print(f"  Total rows: {len(day_data)}")
        print(f"  Unique strikes: {day_data['strike'].nunique()}")
        print(f"  Unique timestamps: {day_data['timestamp'].nunique()}")

        # Bounds violations
        violations = day_data[day_data['violation'].notna()]
        if len(violations) > 0:
            print(f"  BOUND VIOLATIONS: {len(violations)}")
            print(violations[['timestamp', 'product', 'mid', 'lower_bound', 'upper_bound', 'violation']].head(20))
        else:
            print(f"  Bounds: OK (all calls within [max(S-K,0), S])")

        # IV smile
        print("\n  IV Smile (per strike):")
        iv_by_strike = day_data.groupby('strike')['IV'].agg(['count', 'mean', 'std', 'min', 'max'])
        print(iv_by_strike)

        # Realized vol
        vol_stats = analyze_underlying_vol(day_idx)
        print(f"\n  Underlying realized vol: {vol_stats['realized_vol']:.4f}")
        print(f"    (annualized, from {vol_stats['num_ticks']} tick log-returns)")

        # Spreads
        print("\n  Bid-Ask Spreads (per strike):")
        spread_by_strike = day_data.groupby('strike')['spread'].agg(['mean', 'std', 'min', 'max'])
        print(spread_by_strike)

    # Consolidate
    all_df = pd.concat(all_data, ignore_index=True)

    # Check monotonicity in K (call prices should be decreasing in strike)
    print("\n" + "=" * 80)
    print("MONOTONICITY CHECK (C(K) should decrease in K)")
    print("=" * 80)

    for ts_sample in all_df['timestamp'].sample(min(10, len(all_df['timestamp'].unique()))):
        ts_group = all_df[all_df['timestamp'] == ts_sample]
        if len(ts_group) >= 3:
            sorted_group = ts_group.sort_values('strike')
            mid_prices = sorted_group['mid'].values
            strikes = sorted_group['strike'].values
            is_decreasing = all(mid_prices[i] >= mid_prices[i+1] - 0.1 for i in range(len(mid_prices)-1))
            print(f"  ts={ts_sample}: {strikes} -> mids={mid_prices} -> decreasing: {is_decreasing}")

    # Check convexity: C(K_low) - 2*C(K_mid) + C(K_high) should be > 0 (convex)
    print("\n" + "=" * 80)
    print("CONVEXITY CHECK (butterfly test)")
    print("=" * 80)

    convexity_tests = []
    strikes_list = sorted(all_df['strike'].unique())

    for day in [0, 1, 2]:
        day_df = all_df[all_df['day'] == day]

        for ts in day_df['timestamp'].unique():
            ts_group = day_df[day_df['timestamp'] == ts].set_index('strike')

            # Test all triplets (K_low, K_mid, K_high)
            for i in range(len(strikes_list) - 2):
                K_low, K_mid, K_high = strikes_list[i:i+3]

                if K_low not in ts_group.index or K_mid not in ts_group.index or K_high not in ts_group.index:
                    continue

                C_low = ts_group.loc[K_low, 'mid']
                C_mid = ts_group.loc[K_mid, 'mid']
                C_high = ts_group.loc[K_high, 'mid']

                convexity = C_low - 2*C_mid + C_high

                # Store convexity for stats
                convexity_tests.append({
                    'day': day,
                    'timestamp': ts,
                    'triplet': (K_low, K_mid, K_high),
                    'C_low': C_low,
                    'C_mid': C_mid,
                    'C_high': C_high,
                    'convexity': convexity,
                    'is_violated': convexity < -0.01,  # Negative = arb opportunity (buy fly, get paid)
                })

    convexity_df = pd.DataFrame(convexity_tests)
    print(f"Total butterfly triplets tested: {len(convexity_df)}")
    print(f"Convex (normal, convexity > 0): {(convexity_df['convexity'] > 0).sum()}")
    print(f"Linear (convexity ≈ 0): {((convexity_df['convexity'].abs() <= 0.01)).sum()}")
    print(f"VIOLATED (convexity < 0, potential arb): {(convexity_df['convexity'] < -0.01).sum()}")

    if (convexity_df['convexity'] < -0.01).sum() > 0:
        print("\nBUTTERFLY ARB OPPORTUNITIES FOUND:")
        violations = convexity_df[convexity_df['convexity'] < -0.01].sort_values('convexity')
        print(violations[['day', 'timestamp', 'triplet', 'convexity']].head(20))

    print("\nConvexity distribution (all tests):")
    print(convexity_df['convexity'].describe())
