#!/usr/bin/env python3
import pandas as pd
import numpy as np
from pathlib import Path

DATA_DIR = '/sessions/amazing-upbeat-volta/mnt/imc-prosperity-4/data/round3'

# Load day 0 prices only
df = pd.read_csv(f'{DATA_DIR}/prices_round_3_day_0.csv', sep=';')

print("Products:", sorted(df['product'].unique()))
print("\nData shape:", df.shape)

# Get strikes
vouchers = sorted([c for c in df['product'].unique() if c.startswith('VEV_')])
print("\nVouchers (strikes):", vouchers)

# Sample some prices
sample = df[df['timestamp'].isin([0, 1, 2])].copy()
print("\nSample data (first 3 timestamps):")

for product in ['VELVETFRUIT_EXTRACT', 'VEV_5000', 'VEV_5200']:
    prod_sample = sample[sample['product'] == product]
    if not prod_sample.empty:
        print(f"\n{product}:")
        prod_sample['spread'] = prod_sample['ask_price_1'] - prod_sample['bid_price_1']
        print(prod_sample[['timestamp', 'bid_price_1', 'mid_price', 'ask_price_1', 'spread']].to_string())

# Realized vol of underlying
underlying = df[df['product'] == 'VELVETFRUIT_EXTRACT'].sort_values('timestamp')
prices = underlying['mid_price'].values
returns = np.diff(np.log(prices + 1e-6))
realized_vol = np.std(returns) * np.sqrt(250)
print(f"\n\nUnderlying realized vol (day 0): {realized_vol:.4f}")
print(f"Underlying price range: {prices.min():.1f} to {prices.max():.1f}")

# Check bounds for VEV_5000
print("\n\nCall option bounds check for VEV_5000 (K=5000):")
vev_5000 = df[df['product'] == 'VEV_5000'].sort_values('timestamp')
underlying_prices = df[df['product'] == 'VELVETFRUIT_EXTRACT'].set_index('timestamp')['mid_price']

samples = vev_5000.head(10)
for _, row in samples.iterrows():
    ts = row['timestamp']
    if ts in underlying_prices.index:
        S = underlying_prices[ts]
        K = 5000
        mid = row['mid_price']
        lower = max(S - K, 0)
        upper = S
        violation = "VIOLATED" if mid < lower - 0.1 or mid > upper + 0.1 else "OK"
        print(f"ts={ts}: S={S:.1f}, mid={mid:.1f}, bounds=[{lower:.1f}, {upper:.1f}] {violation}")
