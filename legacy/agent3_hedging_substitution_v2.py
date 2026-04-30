#!/usr/bin/env python3
"""
Round 3: Flow/Volume/Volatility Analysis — Hedging & Substitution Signals

Direction: Hunt for hedging behavior (vol spike → volume spike) and substitution
(one product volume down → other up). Test per-product price-volume, LOB imbalance.

Key tests:
1. VELVETFRUIT vol spike → voucher volume spike (hedging)
2. HYDROGEL vol ↔ voucher volume (substitution)
3. Per-product: volume predicts realized vol
4. LOB imbalance predicts realized vol
"""

import pandas as pd
import numpy as np
from pathlib import Path
from scipy.stats import pearsonr
import warnings

warnings.filterwarnings('ignore')

DATA_DIR = Path('/sessions/amazing-upbeat-volta/mnt/imc-prosperity-4/data/round3')

WINDOW_SIZE = 100  # ticks for rolling metrics (vol, volume aggregation)

# ============================================================================
# LOAD DATA
# ============================================================================

def load_day_data(day_idx):
    """Load prices and trades for a single day."""
    price_file = DATA_DIR / f'prices_round_3_day_{day_idx}.csv'
    trades_file = DATA_DIR / f'trades_round_3_day_{day_idx}.csv'

    prices = pd.read_csv(price_file, sep=';')
    trades = pd.read_csv(trades_file, sep=';')

    # Sort by timestamp
    prices = prices.sort_values('timestamp').reset_index(drop=True)
    trades = trades.sort_values('timestamp').reset_index(drop=True)

    return prices, trades

def get_products(prices):
    """Extract product list and classify."""
    all_prods = prices['product'].unique()
    non_vouchers = [p for p in all_prods if not p.startswith('VEV_')]
    vouchers = sorted([p for p in all_prods if p.startswith('VEV_')])
    return non_vouchers, vouchers, all_prods

# ============================================================================
# FEATURE EXTRACTION: Per-Product Rolling Metrics
# ============================================================================

def compute_product_features(prices, product):
    """
    For a single product, compute rolling features:
    - mid_price
    - returns at 1, 100, 1000 ticks
    - realized volatility (100-tick rolling std of 1-tick returns)
    - bid/ask volumes (top level)
    - bid-ask spread
    - LOB imbalance: (bid_vol - ask_vol) / (bid_vol + ask_vol)
    """
    subset = prices[prices['product'] == product].copy()
    subset = subset.reset_index(drop=True)

    if len(subset) < 2:
        return None

    # Mid-price
    mid = subset['mid_price'].values

    # 1-tick returns
    ret_1 = np.diff(mid) / (mid[:-1] + 0.001)
    ret_1 = np.concatenate([[0], ret_1])  # pad for alignment

    # Realized volatility: rolling std of 1-tick returns
    realized_vol = pd.Series(ret_1).rolling(WINDOW_SIZE, min_periods=1).std().values

    # Aggregate volume: sum of bid_volume_1 + ask_volume_1 (top level)
    bid_vol = subset['bid_volume_1'].fillna(0).values
    ask_vol = subset['ask_volume_1'].fillna(0).values
    total_vol = bid_vol + ask_vol

    # Rolling total volume (100-tick windows)
    rolling_vol = pd.Series(total_vol).rolling(WINDOW_SIZE, min_periods=1).sum().values

    # Bid-ask spread
    bid_1 = subset['bid_price_1'].values
    ask_1 = subset['ask_price_1'].values
    spread = np.where((bid_1 > 0) & (ask_1 > 0), ask_1 - bid_1, np.nan)

    # LOB imbalance
    lob_imbal = np.where(
        (bid_vol + ask_vol) > 0,
        (bid_vol - ask_vol) / (bid_vol + ask_vol),
        0
    )

    # Higher-lag returns
    ret_100 = np.concatenate([np.zeros(100), np.diff(mid, n=100) / (mid[:-100] + 0.001)])
    ret_1000 = np.concatenate([np.zeros(1000), np.diff(mid, n=1000) / (mid[:-1000] + 0.001)])

    df = pd.DataFrame({
        'timestamp': subset['timestamp'].values,
        'product': product,
        'mid_price': mid,
        'ret_1': ret_1,
        'ret_100': ret_100,
        'ret_1000': ret_1000,
        'realized_vol': realized_vol,
        'total_vol': total_vol,
        'rolling_vol': rolling_vol,
        'bid_vol': bid_vol,
        'ask_vol': ask_vol,
        'spread': spread,
        'lob_imbal': lob_imbal,
    })

    return df

# ============================================================================
# TEST 1: HEDGING BEHAVIOR
# VELVETFRUIT vol spike → Voucher volume spike
# ============================================================================

def test_hedging_behavior(prices):
    """
    Hypothesis: When VELVETFRUIT_EXTRACT realized vol spikes,
    voucher volumes spike (traders hedge).

    Test: Correlation between VELVETFRUIT realized vol and each voucher's
    rolling volume, at multiple lags.
    """
    print("\n" + "="*70)
    print("TEST 1: HEDGING BEHAVIOR (VELVETFRUIT vol → voucher volume)")
    print("="*70)

    non_vouchers, vouchers, _ = get_products(prices)

    # Compute features for VELVETFRUIT
    velvet_feat = compute_product_features(prices, 'VELVETFRUIT_EXTRACT')
    if velvet_feat is None or len(velvet_feat) < WINDOW_SIZE:
        print("  Insufficient VELVETFRUIT data")
        return []

    results = []

    for voucher in vouchers:
        vouch_feat = compute_product_features(prices, voucher)
        if vouch_feat is None or len(vouch_feat) < WINDOW_SIZE:
            continue

        # Align on timestamp
        merged = velvet_feat.merge(
            vouch_feat[['timestamp', 'rolling_vol']],
            on='timestamp',
            suffixes=('_velvet', '_vouch')
        )

        if len(merged) < WINDOW_SIZE:
            continue

        # Test lags: 0, 10, 50, 100 (VELVETFRUIT vol leading)
        for lag in [0, 10, 50, 100]:
            if lag > 0:
                x = merged['realized_vol'].iloc[:-lag].values
                y = merged['rolling_vol'].iloc[lag:].values
            else:
                x = merged['realized_vol'].values
                y = merged['rolling_vol'].values

            if len(x) < 20:
                continue

            # Remove NaNs and zero-volumes
            mask = ~(np.isnan(x) | np.isnan(y)) & (y > 0)
            x = x[mask]
            y = y[mask]

            if len(x) < 20:
                continue

            r, pval = pearsonr(x, y)

            results.append({
                'relationship': voucher,
                'lag_ticks': lag,
                'correlation': r,
                'n': len(x),
                'p_value': pval,
            })

    # Sort by absolute correlation
    results = sorted(results, key=lambda x: abs(x['correlation']), reverse=True)

    for r in results[:10]:
        asterisk = ' *' if r['p_value'] < 0.05 else ''
        print(f"  {r['relationship']:15s} lag={r['lag_ticks']:3d}  r={r['correlation']:7.3f}  p={r['p_value']:.4f}{asterisk}")

    if not results:
        print("  No signals found")

    return results

# ============================================================================
# TEST 2: SUBSTITUTION BEHAVIOR
# HYDROGEL volume ↔ Voucher volume (inverse correlation = substitution)
# ============================================================================

def test_substitution_behavior(prices):
    """
    Hypothesis: When HYDROGEL_PACK volume drops, traders shift to vouchers.
    Or vice versa: voucher demand substitutes for HYDROGEL demand.

    Test: Correlation between HYDROGEL rolling volume and each voucher's
    rolling volume (expect negative for substitution).
    """
    print("\n" + "="*70)
    print("TEST 2: SUBSTITUTION BEHAVIOR (HYDROGEL volume ↔ voucher volume)")
    print("="*70)

    non_vouchers, vouchers, _ = get_products(prices)

    hydrogel_feat = compute_product_features(prices, 'HYDROGEL_PACK')
    if hydrogel_feat is None or len(hydrogel_feat) < WINDOW_SIZE:
        print("  HYDROGEL_PACK not found or insufficient data")
        return []

    results = []

    for voucher in vouchers:
        vouch_feat = compute_product_features(prices, voucher)
        if vouch_feat is None or len(vouch_feat) < WINDOW_SIZE:
            continue

        merged = hydrogel_feat.merge(
            vouch_feat[['timestamp', 'rolling_vol']],
            on='timestamp',
            suffixes=('_hydro', '_vouch')
        )

        if len(merged) < WINDOW_SIZE:
            continue

        x = merged['rolling_vol_hydro'].values
        y = merged['rolling_vol'].values

        mask = ~(np.isnan(x) | np.isnan(y)) & (x > 0) & (y > 0)
        x = x[mask]
        y = y[mask]

        if len(x) < 20:
            continue

        r, pval = pearsonr(x, y)

        results.append({
            'relationship': voucher,
            'correlation': r,
            'n': len(x),
            'p_value': pval,
        })

    results = sorted(results, key=lambda x: abs(x['correlation']), reverse=True)

    for r in results[:10]:
        interp = 'substitution' if r['correlation'] < -0.15 else 'co-move' if r['correlation'] > 0.15 else 'neutral'
        asterisk = ' *' if r['p_value'] < 0.05 else ''
        print(f"  {r['relationship']:15s} r={r['correlation']:7.3f}  ({interp:12s})  p={r['p_value']:.4f}{asterisk}")

    if not results:
        print("  No signals found")

    return results

# ============================================================================
# TEST 3: PER-PRODUCT PRICE-VOLUME RELATIONSHIP
# Does volume predict realized volatility (or vice versa)?
# ============================================================================

def test_price_volume_relationships(prices):
    """
    Hypothesis: For each product, volume may predict realized volatility
    (Klueger/Karpoff style: informed trading → vol spike).
    Or vol may predict volume (volatility attracts traders).

    Test: Correlation between rolling volume and realized vol, at multiple lags.
    """
    print("\n" + "="*70)
    print("TEST 3: PER-PRODUCT PRICE-VOLUME RELATIONSHIPS")
    print("="*70)

    non_vouchers, vouchers, all_prods = get_products(prices)

    # Focus on the most liquid: VELVETFRUIT, HYDROGEL, and a few vouchers
    key_prods = ['VELVETFRUIT_EXTRACT', 'HYDROGEL_PACK', 'VEV_5000', 'VEV_5500']

    results = []

    for prod in key_prods:
        feat = compute_product_features(prices, prod)
        if feat is None or len(feat) < WINDOW_SIZE:
            continue

        x = feat['rolling_vol'].values
        y = feat['realized_vol'].values

        # Test lags: volume → vol (lag 0, 10, 50), vol → volume (lag -10, -50)
        for lag in [-50, -10, 0, 10, 50]:
            if lag < 0:
                idx_x = slice(None, len(x) + lag)
                idx_y = slice(-lag, None)
            elif lag > 0:
                idx_x = slice(None, len(x) - lag)
                idx_y = slice(lag, None)
            else:
                idx_x = slice(None)
                idx_y = slice(None)

            x_seg = x[idx_x]
            y_seg = y[idx_y]

            mask = ~(np.isnan(x_seg) | np.isnan(y_seg)) & (x_seg > 0) & (y_seg > 0)
            x_seg = x_seg[mask]
            y_seg = y_seg[mask]

            if len(x_seg) < 20:
                continue

            r, pval = pearsonr(x_seg, y_seg)

            results.append({
                'product': prod,
                'lag': lag,
                'correlation': r,
                'n': len(x_seg),
                'p_value': pval,
            })

    results = sorted(results, key=lambda x: abs(x['correlation']), reverse=True)

    for r in results[:12]:
        direction = "vol→vol" if r['lag'] <= 0 else "vol←vol"
        asterisk = ' *' if r['p_value'] < 0.05 else ''
        print(f"  {r['product']:25s} lag={r['lag']:4d}  r={r['correlation']:7.3f}  p={r['p_value']:.4f}{asterisk}")

    if not results:
        print("  No signals found")

    return results

# ============================================================================
# TEST 4: ORDER-BOOK IMBALANCE vs REALIZED VOL
# Does LOB imbalance predict realized volatility within the same product?
# ============================================================================

def test_lob_imbalance_vs_vol(prices):
    """
    Hypothesis: Asymmetric LOB (more bids than asks, or vice versa)
    predicts near-term realized volatility.

    Test: Correlation between LOB imbalance and realized vol at lags.
    """
    print("\n" + "="*70)
    print("TEST 4: ORDER-BOOK IMBALANCE vs REALIZED VOL")
    print("="*70)

    non_vouchers, vouchers, all_prods = get_products(prices)

    key_prods = ['VELVETFRUIT_EXTRACT', 'HYDROGEL_PACK', 'VEV_5000', 'VEV_5500']

    results = []

    for prod in key_prods:
        feat = compute_product_features(prices, prod)
        if feat is None or len(feat) < WINDOW_SIZE:
            continue

        x = feat['lob_imbal'].values
        y = feat['realized_vol'].values

        for lag in [0, 10, 50]:
            if lag > 0:
                idx_x = slice(None, len(x) - lag)
                idx_y = slice(lag, None)
            else:
                idx_x = slice(None)
                idx_y = slice(None)

            x_seg = x[idx_x]
            y_seg = y[idx_y]

            mask = ~(np.isnan(x_seg) | np.isnan(y_seg))
            x_seg = x_seg[mask]
            y_seg = y_seg[mask]

            if len(x_seg) < 20:
                continue

            r, pval = pearsonr(x_seg, y_seg)

            results.append({
                'product': prod,
                'lag': lag,
                'correlation': r,
                'n': len(x_seg),
                'p_value': pval,
            })

    results = sorted(results, key=lambda x: abs(x['correlation']), reverse=True)

    for r in results[:10]:
        asterisk = ' *' if r['p_value'] < 0.05 else ''
        print(f"  {r['product']:25s} lag={r['lag']:3d}  r={r['correlation']:7.3f}  p={r['p_value']:.4f}{asterisk}")

    if not results:
        print("  No signals found")

    return results

# ============================================================================
# MAIN
# ============================================================================

def main():
    print("\n" + "="*70)
    print("ROUND 3: HEDGING & SUBSTITUTION ANALYSIS")
    print("="*70)

    # Load data for all 3 days
    prices_day0, _ = load_day_data(0)
    prices_day1, _ = load_day_data(1)
    prices_day2, _ = load_day_data(2)

    print(f"\nData loaded:")
    print(f"  Day 0: {len(prices_day0)} records, {len(get_products(prices_day0)[2])} products")
    print(f"  Day 1: {len(prices_day1)} records, {len(get_products(prices_day1)[2])} products")
    print(f"  Day 2: {len(prices_day2)} records, {len(get_products(prices_day2)[2])} products")

    # Run tests on all days, aggregate results
    hedging_results_all = []
    substitution_results_all = []
    pricevol_results_all = []
    lob_results_all = []

    for day_idx, prices in enumerate([prices_day0, prices_day1, prices_day2]):
        print(f"\n{'='*70}")
        print(f"ANALYZING DAY {day_idx}")
        print(f"{'='*70}")

        hedging_results_all.extend(test_hedging_behavior(prices))
        substitution_results_all.extend(test_substitution_behavior(prices))
        pricevol_results_all.extend(test_price_volume_relationships(prices))
        lob_results_all.extend(test_lob_imbalance_vs_vol(prices))

    # Summary
    print("\n\n" + "="*70)
    print("AGGREGATE SUMMARY ACROSS ALL 3 DAYS")
    print("="*70)

    # Group by relationship and compute averages
    from collections import defaultdict

    # Hedging summary
    print("\nHEDGING (VELVETFRUIT vol → voucher volume):")
    by_voucher_hedging = defaultdict(list)
    for r in hedging_results_all:
        by_voucher_hedging[r['relationship']].append(r['correlation'])

    for voucher in sorted(by_voucher_hedging.keys()):
        avg = np.mean(by_voucher_hedging[voucher])
        print(f"  {voucher:15s} avg_r={avg:7.3f}  (from {len(by_voucher_hedging[voucher])} tests)")

    # Substitution summary
    print("\nSUBSTITUTION (HYDROGEL volume ↔ voucher volume):")
    by_voucher_subst = defaultdict(list)
    for r in substitution_results_all:
        by_voucher_subst[r['relationship']].append(r['correlation'])

    for voucher in sorted(by_voucher_subst.keys()):
        avg = np.mean(by_voucher_subst[voucher])
        interp = 'SUBSTITUTION!' if avg < -0.15 else 'co-movement' if avg > 0.15 else 'independent'
        print(f"  {voucher:15s} avg_r={avg:7.3f}  ({interp:15s})")

    # Price-volume summary
    print("\nPRICE-VOLUME (within-product correlations):")
    by_prod_pricevol = defaultdict(list)
    for r in pricevol_results_all:
        by_prod_pricevol[r['product']].append(r['correlation'])

    for prod in sorted(by_prod_pricevol.keys()):
        avg = np.mean(by_prod_pricevol[prod])
        print(f"  {prod:25s} avg_r={avg:7.3f}  (from {len(by_prod_pricevol[prod])} tests)")

    # LOB summary
    print("\nLOB IMBALANCE (within-product):")
    by_prod_lob = defaultdict(list)
    for r in lob_results_all:
        by_prod_lob[r['product']].append(r['correlation'])

    for prod in sorted(by_prod_lob.keys()):
        avg = np.mean(by_prod_lob[prod])
        print(f"  {prod:25s} avg_r={avg:7.3f}  (from {len(by_prod_lob[prod])} tests)")

    print("\n" + "="*70)
    print("INTERPRETATION")
    print("="*70)

    # Find strongest signals
    all_avg = []
    for voucher, corrs in by_voucher_hedging.items():
        all_avg.append(('HEDGING: ' + voucher, np.mean(corrs)))
    for voucher, corrs in by_voucher_subst.items():
        all_avg.append(('SUBST: ' + voucher, np.mean(corrs)))
    for prod, corrs in by_prod_pricevol.items():
        all_avg.append(('PRICEVOL: ' + prod, np.mean(corrs)))
    for prod, corrs in by_prod_lob.items():
        all_avg.append(('LOB: ' + prod, np.mean(corrs)))

    all_avg = sorted(all_avg, key=lambda x: abs(x[1]), reverse=True)

    print("\nTop 10 signals by average absolute correlation:")
    for sig, avg_r in all_avg[:10]:
        flag = '*** ACTIONABLE ***' if abs(avg_r) > 0.20 else ('** interesting **' if abs(avg_r) > 0.15 else '')
        print(f"  {sig:40s} avg_r={avg_r:7.3f}  {flag}")

    print("\n" + "="*70)

if __name__ == '__main__':
    main()
