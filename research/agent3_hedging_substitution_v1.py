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
5. ML: GradientBoosting on above relationships
"""

import pandas as pd
import numpy as np
from pathlib import Path
from scipy.stats import pearsonr, spearmanr
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.preprocessing import StandardScaler
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
    vouchers = [p for p in all_prods if p.startswith('VEV_')]
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
    ret_1 = np.diff(mid) / mid[:-1]
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
    ret_100 = np.concatenate([np.zeros(100), np.diff(mid, n=100) / mid[:-100]])
    ret_1000 = np.concatenate([np.zeros(1000), np.diff(mid, n=1000) / mid[:-1000]])

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
    print("TEST 1: HEDGING BEHAVIOR")
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

            # Remove NaNs
            mask = ~(np.isnan(x) | np.isnan(y))
            x = x[mask]
            y = y[mask]

            if len(x) < 20:
                continue

            r, pval = pearsonr(x, y)

            if abs(r) > 0.15:  # Note threshold is lower for vol-volume
                results.append({
                    'relationship': 'VELVETFRUIT_vol → ' + voucher,
                    'lag_ticks': lag,
                    'correlation': r,
                    'n': len(x),
                    'p_value': pval,
                })

    # Sort by absolute correlation
    results = sorted(results, key=lambda x: abs(x['correlation']), reverse=True)

    for r in results[:10]:
        print(f"  {r['relationship']:35s} r={r['correlation']:7.3f}  lag={r['lag_ticks']:3d}  p={r['p_value']:.4f}")

    if not results:
        print("  No significant hedging signals (|r| > 0.15)")

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
    print("TEST 2: SUBSTITUTION BEHAVIOR")
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

        # Substitution → negative correlation; report all with |r| > 0.10
        if abs(r) > 0.10:
            results.append({
                'relationship': 'HYDROGEL_vol ↔ ' + voucher,
                'correlation': r,
                'n': len(x),
                'p_value': pval,
                'interpretation': 'substitution' if r < -0.10 else 'co-movement',
            })

    results = sorted(results, key=lambda x: abs(x['correlation']), reverse=True)

    for r in results[:10]:
        print(f"  {r['relationship']:35s} r={r['correlation']:7.3f}  ({r['interpretation']:15s})  p={r['p_value']:.4f}")

    if not results:
        print("  No significant substitution signals (|r| > 0.10)")

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

            if abs(r) > 0.10:
                direction = "vol→vol" if lag <= 0 else "vol←vol"
                results.append({
                    'product': prod,
                    'metric': 'volume ↔ realized_vol',
                    'lag': lag,
                    'correlation': r,
                    'n': len(x_seg),
                    'p_value': pval,
                })

    results = sorted(results, key=lambda x: abs(x['correlation']), reverse=True)

    for r in results[:12]:
        print(f"  {r['product']:25s} lag={r['lag']:4d}  r={r['correlation']:7.3f}  p={r['p_value']:.4f}")

    if not results:
        print("  No significant price-volume signals (|r| > 0.10)")

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

            if abs(r) > 0.10:
                results.append({
                    'product': prod,
                    'lag': lag,
                    'correlation': r,
                    'n': len(x_seg),
                    'p_value': pval,
                })

    results = sorted(results, key=lambda x: abs(x['correlation']), reverse=True)

    for r in results[:10]:
        print(f"  {r['product']:25s} lag={r['lag']:3d}  r={r['correlation']:7.3f}  p={r['p_value']:.4f}")

    if not results:
        print("  No significant LOB-vol signals (|r| > 0.10)")

    return results

# ============================================================================
# TEST 5: MACHINE LEARNING (GradientBoosting)
# Train on day 0, validate on day 1, test on day 2
# ============================================================================

def prepare_ml_features(prices_list, product, target_metric='realized_vol'):
    """
    Prepare features for ML: lagged metrics from all products.
    Returns X (features), y (target), and timestamps.
    """
    non_vouchers, vouchers, all_prods = get_products(prices_list[0])

    # Compute features for all products
    feat_dict = {}
    for prod in all_prods:
        feat_list = [compute_product_features(p, prod) for p in prices_list]
        feat_dict[prod] = pd.concat(feat_list, ignore_index=True)

    # Get target product
    target_feat = feat_dict[product]

    # Build feature matrix: lagged metrics from all other products
    X_list = []
    ts_list = []

    for idx in range(len(target_feat)):
        ts = target_feat.iloc[idx]['timestamp']
        ts_list.append(ts)

        row = []

        # For each other product, add lagged (1, 5, 10 ticks) metrics
        for other_prod in all_prods:
            if other_prod == product:
                continue  # Skip self

            other_feat = feat_dict[other_prod]

            # Find corresponding rows (same timestamps, with lag)
            for lag in [1, 5, 10]:
                target_ts_idx = idx - lag
                if target_ts_idx < 0:
                    # Pad with NaN
                    row.extend([np.nan, np.nan, np.nan])
                else:
                    # Get metrics at lagged timestamp
                    if target_ts_idx < len(other_feat):
                        ret_100 = other_feat.iloc[target_ts_idx]['ret_100']
                        rolling_vol = other_feat.iloc[target_ts_idx]['rolling_vol']
                        realized_vol = other_feat.iloc[target_ts_idx]['realized_vol']
                        row.extend([ret_100, rolling_vol, realized_vol])
                    else:
                        row.extend([np.nan, np.nan, np.nan])

        X_list.append(row)

    X = np.array(X_list)
    y = target_feat[target_metric].values

    # Remove rows with NaN
    mask = ~np.any(np.isnan(X), axis=1) & ~np.isnan(y)
    X = X[mask]
    y = y[mask]
    ts_arr = np.array(ts_list)[mask]

    return X, y, ts_arr

def test_ml_hedging_substitution(prices_day0, prices_day1, prices_day2):
    """
    Train GradientBoosting model on day 0 to predict realized vol.
    Features: lagged ret_100, rolling_vol, realized_vol from other products.
    Validate on day 1, test on day 2.
    """
    print("\n" + "="*70)
    print("TEST 5: MACHINE LEARNING (GradientBoosting)")
    print("="*70)

    prices_list = [prices_day0, prices_day1, prices_day2]
    non_vouchers, vouchers, all_prods = get_products(prices_day0)

    key_prods = ['VELVETFRUIT_EXTRACT', 'HYDROGEL_PACK', 'VEV_5000', 'VEV_5500']

    results = []

    for prod in key_prods:
        try:
            X, y, ts = prepare_ml_features(prices_list, prod, target_metric='realized_vol')

            if len(X) < 100:
                continue

            # Split: day 0 ~ first 1/3, day 1 ~ middle 1/3, day 2 ~ last 1/3
            n = len(X)
            train_size = n // 3
            val_size = n // 3

            X_train = X[:train_size]
            y_train = y[:train_size]

            X_val = X[train_size:train_size + val_size]
            y_val = y[train_size:train_size + val_size]

            X_test = X[train_size + val_size:]
            y_test = y[train_size + val_size:]

            if len(X_train) < 50 or len(X_test) < 30:
                continue

            # Standardize
            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_val_scaled = scaler.transform(X_val)
            X_test_scaled = scaler.transform(X_test)

            # Train GradientBoosting
            model = GradientBoostingRegressor(
                max_depth=3,
                n_estimators=50,
                learning_rate=0.1,
                random_state=42
            )
            model.fit(X_train_scaled, y_train)

            # Evaluate
            r2_train = model.score(X_train_scaled, y_train)
            r2_val = model.score(X_val_scaled, y_val)
            r2_test = model.score(X_test_scaled, y_test)

            # Top features
            top_feat_idx = np.argsort(model.feature_importances_)[-3:][::-1]
            top_feat_imp = model.feature_importances_[top_feat_idx]

            results.append({
                'product': prod,
                'r2_train': r2_train,
                'r2_val': r2_val,
                'r2_test': r2_test,
                'n_train': len(X_train),
                'n_test': len(X_test),
                'top_feature_importance': top_feat_imp[0] if len(top_feat_imp) > 0 else 0,
            })

        except Exception as e:
            print(f"  Error training model for {prod}: {e}")

    results = sorted(results, key=lambda x: x['r2_test'], reverse=True)

    print(f"\n  {'Product':25s}  R²_train  R²_val  R²_test  Top Feature Imp")
    for r in results:
        print(f"  {r['product']:25s}  {r['r2_train']:8.4f}  {r['r2_val']:7.4f}  {r['r2_test']:8.4f}  {r['top_feature_importance']:6.3f}")

    if not results:
        print("  No successful ML training")

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
    print(f"  Day 0: {len(prices_day0)} records")
    print(f"  Day 1: {len(prices_day1)} records")
    print(f"  Day 2: {len(prices_day2)} records")

    # Run tests on all days, aggregate results
    hedging_results_all = []
    substitution_results_all = []
    pricevol_results_all = []
    lob_results_all = []

    for day_idx, prices in enumerate([prices_day0, prices_day1, prices_day2]):
        print(f"\n\n{'='*70}")
        print(f"ANALYZING DAY {day_idx}")
        print(f"{'='*70}")

        hedging_results_all.extend(test_hedging_behavior(prices))
        substitution_results_all.extend(test_substitution_behavior(prices))
        pricevol_results_all.extend(test_price_volume_relationships(prices))
        lob_results_all.extend(test_lob_imbalance_vs_vol(prices))

    # ML test (uses all 3 days)
    ml_results = test_ml_hedging_substitution(prices_day0, prices_day1, prices_day2)

    # Aggregate results
    print("\n\n" + "="*70)
    print("SUMMARY: STRONGEST SIGNALS ACROSS ALL DAYS")
    print("="*70)

    all_results = hedging_results_all + substitution_results_all + pricevol_results_all + lob_results_all

    # Average by relationship type
    from collections import defaultdict
    by_rel = defaultdict(list)
    for r in all_results:
        rel = r.get('relationship') or r.get('metric') or f"{r.get('product', '?')} {r.get('lag', '')}"
        by_rel[rel].append(r['correlation'])

    averaged = []
    for rel, corrs in by_rel.items():
        avg_corr = np.mean(corrs)
        if abs(avg_corr) > 0.12:
            averaged.append((rel, avg_corr, len(corrs)))

    averaged = sorted(averaged, key=lambda x: abs(x[1]), reverse=True)

    print("\nTop relationships (avg |r| > 0.12 across all days):")
    for rel, avg_r, count in averaged[:15]:
        print(f"  {rel:50s}  avg_r={avg_r:7.3f}  (n={count} tests)")

    print("\n\nML Results (GradientBoosting):")
    for r in ml_results:
        print(f"  {r['product']:25s}  R²_test={r['r2_test']:6.4f}  (n={r['n_test']:3d})")

    print("\n" + "="*70)

if __name__ == '__main__':
    main()
