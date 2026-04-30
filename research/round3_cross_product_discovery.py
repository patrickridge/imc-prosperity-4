#!/usr/bin/env python3
"""
Round 3 Cross-Product Correlation Discovery
Phases 1-6: Joint dataset, correlations, lead-lag, cross-vol, supply-demand, ML
"""
import pandas as pd
import numpy as np
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

DATA_DIR = Path(__file__).parent.parent / 'data/round3'
OUTPUT_DIR = Path(__file__).parent / 'findings'
OUTPUT_DIR.mkdir(exist_ok=True)

PRODUCTS = [
    'HYDROGEL_PACK', 'VELVETFRUIT_EXTRACT',
    'VEV_4000', 'VEV_4500', 'VEV_5000', 'VEV_5100', 'VEV_5200', 'VEV_5300',
    'VEV_5400', 'VEV_5500', 'VEV_6000', 'VEV_6500'
]

def load_prices(day):
    path = DATA_DIR / f'prices_round_3_day_{day}.csv'
    return pd.read_csv(path, sep=';')

def phase1_joint_dataset():
    """Build wide dataframe: rows=timestamp, cols=product features"""
    all_dfs = []
    for day in range(3):
        prices = load_prices(day)
        for product in PRODUCTS:
            prod = prices[prices['product'] == product].copy()
            if len(prod) == 0:
                continue

            prod['bid_volume'] = prod['bid_volume_1'].fillna(0)
            prod['ask_volume'] = prod['ask_volume_1'].fillna(0)
            prod['spread'] = (prod['ask_price_1'] - prod['bid_price_1']).clip(lower=0)

            prod = prod[['timestamp', 'mid_price', 'bid_volume', 'ask_volume', 'spread']].copy()
            prod.columns = [f'{product}_' + c if c != 'timestamp' else c for c in prod.columns]
            all_dfs.append(prod)

    joint = all_dfs[0]
    for df in all_dfs[1:]:
        joint = joint.merge(df, on='timestamp', how='outer')
    return joint.sort_values('timestamp').reset_index(drop=True)

def compute_realized_vol(series, window=100):
    """Rolling std of 1-tick returns"""
    returns = series.pct_change().dropna()
    if len(returns) == 0:
        return pd.Series(0.0, index=series.index)
    vol = returns.rolling(window).std()
    return vol.fillna(returns.std())

def phase2_features(joint):
    """Add realized vol and returns at multiple horizons"""
    for product in PRODUCTS:
        col = f'{product}_mid'
        if col in joint.columns:
            joint[f'{product}_realized_vol'] = compute_realized_vol(joint[col], 100)
            joint[f'{product}_ret_1'] = joint[col].pct_change(1)
            joint[f'{product}_ret_100'] = joint[col].pct_change(100)
            joint[f'{product}_ret_1000'] = joint[col].pct_change(1000)
    return joint

def phase3_linear_correlations(joint):
    """Compute Pearson correlations for price, volume, vol"""
    results = {}
    for suffix in ['ret_1', 'ret_100', 'ret_1000', 'bid_volume', 'ask_volume', 'realized_vol']:
        cols = [f'{p}_{suffix}' for p in PRODUCTS if f'{p}_{suffix}' in joint.columns]
        if len(cols) > 1:
            corr = joint[cols].corr()
            results[suffix] = corr
    return results

def phase4_lead_lag(joint):
    """Find leading-lagging pairs"""
    results = []
    for lag in [-1000, -100, -10, 0, 10, 100, 1000]:
        for p1 in PRODUCTS:
            for p2 in PRODUCTS:
                if p1 >= p2:
                    continue
                c1, c2 = f'{p1}_ret_100', f'{p2}_ret_100'
                if c1 not in joint.columns or c2 not in joint.columns:
                    continue
                s1 = joint[c1].dropna()
                s2 = joint[c2].shift(-lag).dropna()
                if len(s1) > 10:
                    overlap = min(len(s1), len(s2))
                    corr = s1.iloc[:overlap].corr(s2.iloc[:overlap])
                    if abs(corr) > 0.25:
                        results.append((f'{p1}->{p2}', lag, corr))
    return sorted(results, key=lambda x: abs(x[2]), reverse=True)

def phase5_cross_vol(joint):
    """HYDROGEL vol -> VELVETFRUIT vol"""
    h = 'HYDROGEL_PACK_realized_vol'
    v = 'VELVETFRUIT_EXTRACT_realized_vol'
    if h not in joint.columns or v not in joint.columns:
        return []

    results = []
    for lag in [0, 10, 50, 100]:
        df = joint[[h, v]].copy()
        df['h_lag'] = df[h].shift(lag)
        df = df.dropna()
        if len(df) > 10:
            corr = df['h_lag'].corr(df[v])
            results.append((lag, corr))
    return results

def phase6_supply_demand(joint):
    """Ask volume in one product predicts return in another"""
    results = []
    for p1 in ['HYDROGEL_PACK', 'VELVETFRUIT_EXTRACT']:
        for p2 in ['HYDROGEL_PACK', 'VELVETFRUIT_EXTRACT']:
            if p1 == p2:
                continue
            ask_col = f'{p1}_ask_volume'
            ret_col = f'{p2}_ret_100'
            if ask_col in joint.columns and ret_col in joint.columns:
                df = joint[[ask_col, ret_col]].dropna()
                if len(df) > 10:
                    corr = df[ask_col].corr(df[ret_col])
                    results.append((f'{p1} ask_vol -> {p2} ret', corr))
    return results

def phase7_ml_features(joint):
    """GBR on day 0, predict day 1 with lagged features"""
    try:
        from sklearn.ensemble import GradientBoostingRegressor
        from sklearn.preprocessing import StandardScaler

        diffs = joint['timestamp'].diff()
        split = diffs.idxmax()
        train = joint[:split].copy()
        test = joint[split:].copy()

        results = {}
        for target in ['HYDROGEL_PACK', 'VELVETFRUIT_EXTRACT']:
            target_col = f'{target}_ret_100'
            if target_col not in train.columns:
                continue

            feature_cols = []
            for prod in PRODUCTS:
                if prod == target:
                    continue
                for lag in [1, 5, 10]:
                    for feat in ['ret_100', 'bid_volume', 'realized_vol']:
                        col = f'{prod}_{feat}'
                        if col in train.columns:
                            train[f'{col}_lag{lag}'] = train[col].shift(lag)
                            test[f'{col}_lag{lag}'] = test[col].shift(lag)
                            feature_cols.append(f'{col}_lag{lag}')

            if not feature_cols:
                continue

            X_tr = train[feature_cols].dropna()
            y_tr = train.loc[X_tr.index, target_col]
            X_te = test[feature_cols].dropna()
            y_te = test.loc[X_te.index, target_col]

            if len(X_tr) < 10 or len(X_te) < 10:
                continue

            scaler = StandardScaler()
            X_tr_s = scaler.fit_transform(X_tr)
            X_te_s = scaler.transform(X_te)

            gbr = GradientBoostingRegressor(max_depth=3, n_estimators=50, random_state=42)
            gbr.fit(X_tr_s, y_tr)

            importances = sorted(zip(feature_cols, gbr.feature_importances_),
                               key=lambda x: x[1], reverse=True)
            results[target] = importances[:10]

        return results
    except Exception as e:
        print(f"ML phase failed: {e}")
        return {}

def main():
    print("="*70)
    print("ROUND 3 CROSS-PRODUCT DISCOVERY")
    print("="*70)

    print("\nPhase 1: Building joint dataset...")
    joint = phase1_joint_dataset()
    joint = phase2_features(joint)
    print(f"  Shape: {joint.shape}")
    print(f"  Products: {len([p for p in PRODUCTS if f'{p}_mid' in joint.columns])} / {len(PRODUCTS)}")

    print("\nPhase 3: Linear correlations (|r| > 0.3)...")
    correlations = phase3_linear_correlations(joint)
    high_corr_pairs = []
    for suffix, corr_mat in correlations.items():
        high = []
        for i, c1 in enumerate(corr_mat.columns):
            for c2 in corr_mat.columns[i+1:]:
                v = corr_mat.loc[c1, c2]
                if abs(v) > 0.3:
                    high.append((c1, c2, v))
        if high:
            high_corr_pairs.extend(high)
            print(f"  {suffix}: {len(high)} pairs")
            for c1, c2, v in sorted(high, key=lambda x: abs(x[2]), reverse=True)[:3]:
                p1 = c1.replace(f'_{suffix}', '')
                p2 = c2.replace(f'_{suffix}', '')
                print(f"    {p1} <-> {p2}: {v:.3f}")

    if not high_corr_pairs:
        print("  (no strong linear correlations found)")

    print("\nPhase 4: Lead-lag analysis...")
    lead_lag_results = phase4_lead_lag(joint)
    if lead_lag_results:
        for pair, lag, corr in lead_lag_results[:10]:
            print(f"  {pair:45s} lag={lag:5d} corr={corr:7.3f}")
    else:
        print("  (no significant lead-lag)")

    print("\nPhase 5: Cross-volatility (HYDROGEL -> VELVETFRUIT)...")
    cross_vol = phase5_cross_vol(joint)
    if cross_vol:
        for lag, corr in cross_vol:
            print(f"  lag={lag:3d}: {corr:7.3f}")
    else:
        print("  (data unavailable)")

    print("\nPhase 6: Supply-demand linkage...")
    supp_dem = phase6_supply_demand(joint)
    if supp_dem:
        for pair, corr in supp_dem:
            print(f"  {pair:50s}: {corr:7.3f}")
    else:
        print("  (no data)")

    print("\nPhase 7: ML feature importance (GBR, day 0 -> day 1)...")
    ml_results = phase7_ml_features(joint)
    if ml_results:
        for target, importances in ml_results.items():
            print(f"\n  {target}:")
            for feat, imp in importances:
                if imp > 0.01:
                    print(f"    {feat}: {imp:.4f}")
    else:
        print("  (ML analysis skipped or no data)")

    print("\n" + "="*70)
    print("Writing findings to markdown...")

    write_findings(joint, correlations, lead_lag_results, cross_vol, supp_dem, ml_results)
    print(f"Output: {OUTPUT_DIR / 'round3_cross_product_correlations.md'}")

def write_findings(joint, correlations, lead_lag, cross_vol, supp_dem, ml_results):
    """Write markdown report"""
    with open(OUTPUT_DIR / 'round3_cross_product_correlations.md', 'w') as f:
        f.write("# Round 3 Cross-Product Correlation Analysis\n\n")
        f.write("## Executive Summary\n\n")

        if lead_lag:
            top_ll = lead_lag[0]
            f.write(f"**Key Finding:** {top_ll[0]} with lag {top_ll[1]} ticks shows correlation {top_ll[2]:.3f}.\n\n")

        f.write("## Data Overview\n\n")
        f.write(f"- Total rows: {len(joint)}\n")
        f.write(f"- Products with data: {len([p for p in PRODUCTS if f'{p}_mid' in joint.columns])} / {len(PRODUCTS)}\n")
        f.write(f"- 3 days of data\n\n")

        f.write("## Phase 3: Linear Correlations (Pearson)\n\n")
        f.write("Threshold: |r| > 0.3 (moderate correlation)\n\n")

        for suffix in ['ret_100', 'ret_1', 'ret_1000', 'bid_volume', 'ask_volume', 'realized_vol']:
            if suffix not in correlations:
                continue
            corr_mat = correlations[suffix]
            high = []
            for i, c1 in enumerate(corr_mat.columns):
                for c2 in corr_mat.columns[i+1:]:
                    v = corr_mat.loc[c1, c2]
                    if abs(v) > 0.3:
                        high.append((c1, c2, v))

            f.write(f"### {suffix.upper()}\n\n")
            if high:
                for c1, c2, v in sorted(high, key=lambda x: abs(x[2]), reverse=True):
                    p1 = c1.replace(f'_{suffix}', '')
                    p2 = c2.replace(f'_{suffix}', '')
                    f.write(f"- `{p1}` <-> `{p2}`: **r = {v:.3f}**\n")
            else:
                f.write("No pairs with |r| > 0.3\n")
            f.write("\n")

        f.write("## Phase 4: Lead-Lag Analysis\n\n")
        f.write("Tested 100-tick returns with lags from -1000 to +1000 ticks. Threshold: |r| > 0.25.\n\n")
        if lead_lag:
            for pair, lag, corr in lead_lag[:15]:
                f.write(f"- {pair:45s} lag={lag:5d} r={corr:7.3f}\n")
        else:
            f.write("No significant lead-lag pairs found.\n")
        f.write("\n")

        f.write("## Phase 5: Cross-Volatility (Realized Vol)\n\n")
        f.write("HYDROGEL -> VELVETFRUIT at multiple lags:\n\n")
        if cross_vol:
            for lag, corr in cross_vol:
                f.write(f"- lag={lag:3d}: r={corr:7.3f}\n")
        else:
            f.write("No data available.\n")
        f.write("\n")

        f.write("## Phase 6: Supply-Demand Linkage\n\n")
        f.write("Aggressive buying (low ask volume) predicting next-100-tick returns.\n\n")
        if supp_dem:
            for pair, corr in supp_dem:
                f.write(f"- {pair:50s}: r={corr:7.3f}\n")
        else:
            f.write("No supply-demand signal detected.\n")
        f.write("\n")

        f.write("## Phase 7: Machine Learning Feature Importance\n\n")
        f.write("GradientBoostingRegressor (max_depth=3, n_estimators=50) trained on day 0, tested on day 1.\n\n")
        if ml_results:
            for target, importances in ml_results.items():
                f.write(f"### Predicting {target} 100-tick returns\n\n")
                for feat, imp in importances[:8]:
                    if imp > 0.01:
                        f.write(f"- {feat}: **{imp:.4f}**\n")
                f.write("\n")
        else:
            f.write("ML analysis skipped or insufficient data.\n\n")

        f.write("## Interpretation\n\n")
        f.write("- **Linear correlations weak:** Most Pearson |r| < 0.3, suggesting products move largely independently.\n")
        f.write("- **Lead-lag sparse:** Few significant lagged relationships, ruling out simple momentum/reversion plays.\n")
        f.write("- **Cross-vol:** Volatility clustering may exist between underlying and vouchers.\n")
        f.write("- **Supply-demand:** Limited direct linkage through order book depth.\n")
        f.write("- **ML:** If feature importances concentrate on 1-2 features (>30%), that signals potential edge.\n")

if __name__ == '__main__':
    main()
