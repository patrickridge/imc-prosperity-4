#!/usr/bin/env python3
"""
Analyze actual market trades and bid-ask data to find trading opportunities.
Focus on: (1) mean reversion of IV smile, (2) spread scalping.
"""

import pandas as pd
import numpy as np

DATA_DIR = '/sessions/amazing-upbeat-volta/mnt/imc-prosperity-4/data/round3'

trades = pd.read_csv(f'{DATA_DIR}/trades_round_3_day_0.csv', sep=';')
prices = pd.read_csv(f'{DATA_DIR}/prices_round_3_day_0.csv', sep=';')

# Filter vouchers
voucher_strikes = [4000, 4500, 5000, 5100, 5200, 5300, 5400, 5500, 6000, 6500]
voucher_products = [f'VEV_{k}' for k in voucher_strikes]

print("=" * 80)
print("ACTUAL TRADES - DAY 0")
print("=" * 80)

for product in voucher_products:
    product_trades = trades[trades['symbol'] == product]
    if len(product_trades) > 0:
        prices_list = product_trades['price'].values
        print(f"\n{product}: {len(product_trades)} trades")
        print(f"  Price range: {prices_list.min():.1f} - {prices_list.max():.1f}")
        print(f"  Mean price: {prices_list.mean():.2f}")
        print(f"  Traded at: {sorted(prices_list.tolist())}")

print("\n" + "=" * 80)
print("BID-ASK SPREADS (ALL TIMESTAMPS)")
print("=" * 80)

# Compute average spread per product
for product in voucher_products:
    product_prices = prices[prices['product'] == product].copy()
    product_prices['spread'] = product_prices['ask_price_1'] - product_prices['bid_price_1']

    spreads = product_prices['spread'].dropna()
    if len(spreads) > 0:
        print(f"\n{product}:")
        print(f"  Spread: mean={spreads.mean():.2f}, std={spreads.std():.2f}, "
              f"min={spreads.min():.1f}, max={spreads.max():.1f}")

print("\n" + "=" * 80)
print("IV SMILE ANALYSIS")
print("=" * 80)

# Get underlying prices and compute IVs
from scipy.stats import norm
from scipy.optimize import brentq

def bs_call(S, K, T, sigma):
    if T <= 0 or sigma <= 0:
        return max(S - K, 0)
    d1 = (np.log(S / K) + (sigma ** 2 / 2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    return S * norm.cdf(d1) - K * norm.cdf(d2)

def extract_iv(market_price, S, K, T):
    if T <= 0.001:
        return np.nan
    try:
        def objective(sigma):
            return bs_call(S, K, T, sigma) - market_price
        low_price = max(S - K, 0)
        if market_price < low_price - 0.01:
            return np.nan
        if objective(0.01) > 0 or objective(10.0) < 0:
            return np.nan
        return brentq(objective, 0.01, 10.0, xtol=1e-6)
    except:
        return np.nan

# Sample timestamps to compute IV smile
sample_timestamps = sorted(prices['timestamp'].unique())[::100]

iv_smiles = []
for ts in sample_timestamps[:5]:  # Just first 5 samples
    ts_prices = prices[prices['timestamp'] == ts]
    underlying = ts_prices[ts_prices['product'] == 'VELVETFRUIT_EXTRACT']['mid_price'].values

    if len(underlying) == 0:
        continue

    S = underlying[0]
    T = 3 / 365  # 3 days
    ivs = []

    for strike in voucher_strikes:
        product = f'VEV_{strike}'
        prod_price = ts_prices[ts_prices['product'] == product]['mid_price'].values
        if len(prod_price) > 0:
            iv = extract_iv(prod_price[0], S, strike, T)
            ivs.append((strike, iv))

    if any(not np.isnan(iv) for _, iv in ivs):
        print(f"\nTimestamp {ts}, S={S:.1f}:")
        for strike, iv in ivs:
            if not np.isnan(iv):
                print(f"  K={strike}: IV={iv:.4f}")

print("\n" + "=" * 80)
print("LIQUIDITY ANALYSIS")
print("=" * 80)

# When do we have both wide spreads AND good market trades?
for product in ['VEV_5000', 'VEV_5200', 'VEV_5400']:
    prod_prices = prices[prices['product'] == product].copy()
    prod_prices['spread'] = prod_prices['ask_price_1'] - prod_prices['bid_price_1']

    # Times with wide spreads
    wide_spread = prod_prices[prod_prices['spread'] >= 3]

    # Check if trades happened at those times
    prod_trades = trades[trades['symbol'] == product]

    print(f"\n{product}:")
    print(f"  Total timestamps: {prod_prices['timestamp'].nunique()}")
    print(f"  Timestamps with spread >= 3: {wide_spread['timestamp'].nunique()}")

    # Trade timing vs spread
    trade_times = set(prod_trades['timestamp'].values)
    wide_times = set(wide_spread['timestamp'].values)
    overlap = len(trade_times & wide_times)
    print(f"  Trades during wide spreads: {overlap}")
