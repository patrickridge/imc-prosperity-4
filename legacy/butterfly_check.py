#!/usr/bin/env python3
"""
Butterfly convexity violation check for all timestamps.
Violation: C(K_low) - 2*C(K_mid) + C(K_high) < 0 (negative = BUY butterfly, GET PAID)
"""

import pandas as pd
import numpy as np

DATA_DIR = '/sessions/amazing-upbeat-volta/mnt/imc-prosperity-4/data/round3'

def check_day_butterflies(day_idx):
    df = pd.read_csv(f'{DATA_DIR}/prices_round_3_day_{day_idx}.csv', sep=';')

    vouchers = sorted([c for c in df['product'].unique() if c.startswith('VEV_')])
    strikes = sorted([int(v.split('_')[1]) for v in vouchers])

    print(f"\n{'='*80}")
    print(f"DAY {day_idx}")
    print(f"{'='*80}")

    violations = []

    # For each timestamp
    for ts in sorted(df['timestamp'].unique()):
        ts_data = df[df['timestamp'] == ts].set_index('product')

        # Build price dict
        prices = {}
        for voucher in vouchers:
            if voucher in ts_data.index:
                prices[int(voucher.split('_')[1])] = ts_data.loc[voucher, 'mid_price']

        if len(prices) < 3:
            continue

        # Check all consecutive triplets
        for i in range(len(strikes) - 2):
            K_low = strikes[i]
            K_mid = strikes[i + 1]
            K_high = strikes[i + 2]

            if K_low in prices and K_mid in prices and K_high in prices:
                C_low = prices[K_low]
                C_mid = prices[K_mid]
                C_high = prices[K_high]

                convexity = C_low - 2 * C_mid + C_high

                if convexity < -0.05:  # Significant violation
                    violations.append({
                        'day': day_idx,
                        'ts': ts,
                        'K_low': K_low,
                        'K_mid': K_mid,
                        'K_high': K_high,
                        'C_low': C_low,
                        'C_mid': C_mid,
                        'C_high': C_high,
                        'convexity': convexity,
                    })

    if violations:
        print(f"VIOLATIONS FOUND: {len(violations)}")
        for v in violations[:10]:  # Show first 10
            print(f"  ts={v['ts']}: ({v['K_low']}, {v['K_mid']}, {v['K_high']}) "
                  f"prices=({v['C_low']:.2f}, {v['C_mid']:.2f}, {v['C_high']:.2f}) "
                  f"convexity={v['convexity']:.4f}")
        return violations
    else:
        print(f"No butterfly violations detected.")
        return []

# Check all days
all_violations = []
for day in [0, 1, 2]:
    day_violations = check_day_butterflies(day)
    all_violations.extend(day_violations)

print(f"\n{'='*80}")
print(f"SUMMARY: {len(all_violations)} total violations across all days")
print(f"{'='*80}")

if len(all_violations) > 0:
    print("\nTop 20 violations (most negative convexity):")
    vdf = pd.DataFrame(all_violations).sort_values('convexity')
    for _, v in vdf.head(20).iterrows():
        print(f"  Day {int(v['day'])}, ts={int(v['ts'])}: "
              f"({int(v['K_low'])}, {int(v['K_mid'])}, {int(v['K_high'])}) "
              f"prices=({v['C_low']:.2f}, {v['C_mid']:.2f}, {v['C_high']:.2f}) "
              f"CONV={v['convexity']:.6f}")
else:
    print("\nAll butterfly triplets respect convexity (no arbitrage from this structure).")
