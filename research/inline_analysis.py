#!/usr/bin/env python3
import pandas as pd
import numpy as np
from pathlib import Path

DATA_DIR = Path('/Users/kieran/Desktop/imc-prosperity-4/data/round3')
OUT = Path('/Users/kieran/Desktop/imc-prosperity-4/research/findings')
OUT.mkdir(exist_ok=True)

# Load all 3 days
dfs = []
for day in range(3):
    df = pd.read_csv(DATA_DIR / f'prices_round_3_day_{day}.csv', sep=';')
    dfs.append(df)

prices = pd.concat(dfs, ignore_index=True)

# Build joint
products = ['HYDROGEL_PACK', 'VELVETFRUIT_EXTRACT', 'VEV_4000', 'VEV_4500', 'VEV_5000',
            'VEV_5100', 'VEV_5200', 'VEV_5300', 'VEV_5400', 'VEV_5500', 'VEV_6000', 'VEV_6500']

joint = prices[prices['product'] == products[0]][['timestamp', 'mid_price']].copy()
joint.columns = ['timestamp', f'{products[0]}_mid']

for prod in products[1:]:
    subset = prices[prices['product'] == prod][['timestamp', 'mid_price', 'bid_volume_1', 'ask_volume_1']].copy()
    subset.columns = ['timestamp', f'{prod}_mid', f'{prod}_bid_vol', f'{prod}_ask_vol']
    joint = joint.merge(subset, on='timestamp', how='outer')

joint = joint.sort_values('timestamp').reset_index(drop=True)

# Add spread
for prod in products:
    bid = f'bid_price_{prod}'
    ask = f'ask_price_{prod}'
    subset = prices[prices['product'] == prod][['timestamp', 'bid_price_1', 'ask_price_1']].copy()
    subset.columns = ['timestamp', bid, ask]
    joint = joint.merge(subset, on='timestamp', how='outer')
    joint[f'{prod}_spread'] = (joint[ask] - joint[bid]).clip(lower=0)

print(f"Joint dataset shape: {joint.shape}")
print(f"Columns: {list(joint.columns)[:20]}")

# Compute features
for prod in products:
    col = f'{prod}_mid'
    if col in joint.columns:
        # Returns
        joint[f'{prod}_ret_1'] = joint[col].pct_change(1)
        joint[f'{prod}_ret_100'] = joint[col].pct_change(100)
        joint[f'{prod}_ret_1000'] = joint[col].pct_change(1000)

        # Realized vol
        ret = joint[col].pct_change().dropna()
        vol = ret.rolling(100).std()
        joint[f'{prod}_vol'] = vol.fillna(ret.std())

# Phase 2: Correlations
print("\n=== PHASE 2: LINEAR CORRELATIONS ===\n")

feature_types = ['ret_1', 'ret_100', 'ret_1000', 'vol', 'bid_vol', 'ask_vol']

for ftype in feature_types:
    cols = [f'{p}_{ftype}' for p in products if f'{p}_{ftype}' in joint.columns]
    if len(cols) < 2:
        continue

    corr = joint[cols].corr()

    high_pairs = []
    for i, c1 in enumerate(corr.columns):
        for c2 in corr.columns[i+1:]:
            v = corr.loc[c1, c2]
            if abs(v) > 0.3:
                p1 = c1.replace(f'_{ftype}', '')
                p2 = c2.replace(f'_{ftype}', '')
                high_pairs.append((p1, p2, v))

    print(f"{ftype.upper()}: {len(high_pairs)} pairs with |r| > 0.3")
    for p1, p2, v in sorted(high_pairs, key=lambda x: abs(x[2]), reverse=True)[:5]:
        print(f"  {p1} <-> {p2}: {v:.3f}")

# Phase 3: Lead-lag
print("\n=== PHASE 3: LEAD-LAG ===\n")

lead_lag_results = []
for lag in [-1000, -100, -10, 0, 10, 100, 1000]:
    for p1 in products:
        for p2 in products:
            if p1 >= p2:
                continue
            c1 = f'{p1}_ret_100'
            c2 = f'{p2}_ret_100'
            if c1 not in joint.columns or c2 not in joint.columns:
                continue

            s1 = joint[c1].dropna()
            s2 = joint[c2].shift(-lag).dropna()

            if len(s1) > 10:
                overlap = min(len(s1), len(s2))
                corr = s1.iloc[:overlap].corr(s2.iloc[:overlap])
                if abs(corr) > 0.25:
                    lead_lag_results.append((f'{p1}->{p2}', lag, corr))

if lead_lag_results:
    for pair, lag, corr in sorted(lead_lag_results, key=lambda x: abs(x[2]), reverse=True)[:12]:
        print(f"{pair:40s} lag={lag:5d} r={corr:7.3f}")
else:
    print("No significant lead-lag found")

# Phase 4: Cross-vol
print("\n=== PHASE 4: CROSS-VOL ===\n")

h_vol = 'HYDROGEL_PACK_vol'
v_vol = 'VELVETFRUIT_EXTRACT_vol'
if h_vol in joint.columns and v_vol in joint.columns:
    for lag in [0, 10, 50, 100]:
        data = joint[[h_vol, v_vol]].copy()
        data['h_lag'] = data[h_vol].shift(lag)
        data = data.dropna()
        if len(data) > 10:
            corr = data['h_lag'].corr(data[v_vol])
            print(f"HYDROGEL vol -> VELVETFRUIT vol (lag={lag:3d}): {corr:7.3f}")

# Phase 5: Supply-demand
print("\n=== PHASE 5: SUPPLY-DEMAND ===\n")

for p1 in ['HYDROGEL_PACK', 'VELVETFRUIT_EXTRACT']:
    for p2 in ['HYDROGEL_PACK', 'VELVETFRUIT_EXTRACT']:
        if p1 == p2:
            continue
        ask_col = f'{p1}_ask_vol'
        ret_col = f'{p2}_ret_100'
        if ask_col in joint.columns and ret_col in joint.columns:
            data = joint[[ask_col, ret_col]].dropna()
            if len(data) > 10:
                corr = data[ask_col].corr(data[ret_col])
                print(f"{p1} ask_vol -> {p2} ret_100: {corr:7.3f}")

print("\n=== DONE ===\n")
