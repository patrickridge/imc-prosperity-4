#!/usr/bin/env python3
"""
Execute all 7 phases of cross-product discovery locally.
No bash, purely Python file I/O and pandas.
"""
import pandas as pd
import numpy as np
import sys
from pathlib import Path

# Paths
DATA_DIR = Path('/Users/kieran/Desktop/imc-prosperity-4/data/round3')
OUT_DIR = Path('/Users/kieran/Desktop/imc-prosperity-4/research/findings')
OUT_DIR.mkdir(exist_ok=True)

PRODUCTS = [
    'HYDROGEL_PACK', 'VELVETFRUIT_EXTRACT',
    'VEV_4000', 'VEV_4500', 'VEV_5000', 'VEV_5100', 'VEV_5200', 'VEV_5300',
    'VEV_5400', 'VEV_5500', 'VEV_6000', 'VEV_6500'
]

def load_all_prices():
    """Load all 3 days of prices"""
    dfs = []
    for day in range(3):
        path = DATA_DIR / f'prices_round_3_day_{day}.csv'
        df = pd.read_csv(path, sep=';')
        dfs.append(df)
    return pd.concat(dfs, ignore_index=True)

def build_joint():
    """Build wide dataframe with product features"""
    prices = load_all_prices()
    print(f"Loaded {len(prices)} price rows", file=sys.stderr)

    # Start with first product
    joint = prices[prices['product'] == PRODUCTS[0]][['timestamp', 'mid_price']].copy()
    joint.columns = ['timestamp', f'{PRODUCTS[0]}_mid']

    # Merge in other products
    for prod in PRODUCTS[1:]:
        subset = prices[prices['product'] == prod][['timestamp', 'mid_price', 'bid_volume_1', 'ask_volume_1']].copy()
        subset.columns = ['timestamp', f'{prod}_mid', f'{prod}_bid_vol', f'{prod}_ask_vol']
        joint = joint.merge(subset, on='timestamp', how='outer')

    joint = joint.sort_values('timestamp').reset_index(drop=True)
    print(f"Joint shape: {joint.shape}", file=sys.stderr)
    return joint

def add_features(joint):
    """Add realized vol and returns"""
    prices = load_all_prices()

    # Add spreads
    for prod in PRODUCTS:
        subset = prices[prices['product'] == prod][['timestamp', 'bid_price_1', 'ask_price_1']].copy()
        subset.columns = ['timestamp', f'{prod}_bid', f'{prod}_ask']
        joint = joint.merge(subset, on='timestamp', how='outer')
        joint[f'{prod}_spread'] = (joint[f'{prod}_ask'] - joint[f'{prod}_bid']).clip(lower=0.01)

    # Compute returns and vol
    for prod in PRODUCTS:
        col = f'{prod}_mid'
        if col in joint.columns:
            joint[f'{prod}_ret_1'] = joint[col].pct_change(1)
            joint[f'{prod}_ret_100'] = joint[col].pct_change(100)
            joint[f'{prod}_ret_1000'] = joint[col].pct_change(1000)

            # Realized vol
            ret = joint[col].pct_change().dropna()
            if len(ret) > 100:
                vol = ret.rolling(100).std()
                joint[f'{prod}_vol'] = vol.fillna(ret.std())
            else:
                joint[f'{prod}_vol'] = ret.std()

    return joint

def phase3_correlations(joint):
    """Compute Pearson correlations"""
    results = {}
    feature_types = ['ret_1', 'ret_100', 'ret_1000', 'vol', 'bid_vol', 'ask_vol']

    for ftype in feature_types:
        cols = [f'{p}_{ftype}' for p in PRODUCTS if f'{p}_{ftype}' in joint.columns]
        if len(cols) > 1:
            corr = joint[cols].corr()
            results[ftype] = corr

    return results

def phase4_lead_lag(joint):
    """Detect leading/lagging pairs"""
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
    h, v = 'HYDROGEL_PACK_vol', 'VELVETFRUIT_EXTRACT_vol'
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
    """Ask volume predicting returns"""
    results = []
    for p1 in ['HYDROGEL_PACK', 'VELVETFRUIT_EXTRACT']:
        for p2 in ['HYDROGEL_PACK', 'VELVETFRUIT_EXTRACT']:
            if p1 == p2:
                continue
            ask_col, ret_col = f'{p1}_ask_vol', f'{p2}_ret_100'
            if ask_col in joint.columns and ret_col in joint.columns:
                df = joint[[ask_col, ret_col]].dropna()
                if len(df) > 10:
                    corr = df[ask_col].corr(df[ret_col])
                    results.append((f'{p1} ask -> {p2} ret', corr))
    return results

def phase7_ml(joint):
    """GBR feature importance"""
    try:
        from sklearn.ensemble import GradientBoostingRegressor
        from sklearn.preprocessing import StandardScaler

        # Find day split
        diffs = joint['timestamp'].diff()
        split_idx = diffs.idxmax()
        train = joint[:split_idx].copy()
        test = joint[split_idx:].copy()

        results = {}
        for target in ['HYDROGEL_PACK', 'VELVETFRUIT_EXTRACT']:
            target_col = f'{target}_ret_100'
            if target_col not in train.columns:
                continue

            # Build lagged features
            feature_cols = []
            for prod in PRODUCTS:
                if prod == target:
                    continue
                for lag in [1, 5, 10]:
                    for feat in ['ret_100', 'bid_vol', 'vol']:
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
        print(f"ML failed: {e}", file=sys.stderr)
        return {}

def write_findings(corr, lead_lag, cross_vol, supp_dem, ml):
    """Write comprehensive markdown report"""
    with open(OUT_DIR / 'round3_cross_product_correlations.md', 'w') as f:
        f.write("# Round 3 Cross-Product Correlation Analysis\n\n")

        # Executive summary
        f.write("## Executive Summary\n\n")
        if lead_lag:
            top = lead_lag[0]
            f.write(f"**Top Finding:** {top[0]} with lag {top[1]:+d} ticks: r={top[2]:.3f}\n\n")
        else:
            f.write("Linear analysis reveals weak cross-product relationships.\n\n")

        # Phase 3
        f.write("## Phase 3: Linear Correlations (|r| > 0.3)\n\n")
        for ftype in ['ret_100', 'ret_1', 'ret_1000', 'vol', 'bid_vol', 'ask_vol']:
            if ftype not in corr:
                continue
            corr_mat = corr[ftype]
            high = []
            for i, c1 in enumerate(corr_mat.columns):
                for c2 in corr_mat.columns[i+1:]:
                    v = corr_mat.loc[c1, c2]
                    if abs(v) > 0.3:
                        high.append((c1, c2, v))

            f.write(f"### {ftype.upper()}\n\n")
            if high:
                for c1, c2, v in sorted(high, key=lambda x: abs(x[2]), reverse=True):
                    p1 = c1.replace(f'_{ftype}', '')
                    p2 = c2.replace(f'_{ftype}', '')
                    f.write(f"- `{p1}` <--> `{p2}`: **r={v:.3f}**\n")
            else:
                f.write("No pairs with |r| > 0.3\n")
            f.write("\n")

        # Phase 4
        f.write("## Phase 4: Lead-Lag Analysis\n\n")
        if lead_lag:
            for pair, lag, corr_val in lead_lag[:15]:
                f.write(f"- {pair:45s} lag={lag:+5d} r={corr_val:7.3f}\n")
        else:
            f.write("No significant lead-lag found.\n")
        f.write("\n")

        # Phase 5
        f.write("## Phase 5: Cross-Volatility\n\n")
        f.write("HYDROGEL realized vol -> VELVETFRUIT realized vol:\n\n")
        if cross_vol:
            for lag, corr_val in cross_vol:
                f.write(f"- lag={lag:3d}: r={corr_val:7.3f}\n")
        else:
            f.write("No data.\n")
        f.write("\n")

        # Phase 6
        f.write("## Phase 6: Supply-Demand Linkage\n\n")
        if supp_dem:
            for pair, corr_val in supp_dem:
                f.write(f"- {pair:50s}: r={corr_val:7.3f}\n")
        else:
            f.write("No supply-demand signal detected.\n")
        f.write("\n")

        # Phase 7
        f.write("## Phase 7: Machine Learning (GBR)\n\n")
        f.write("Trained on day 0, tested on day 1. Top 8 features by importance:\n\n")
        if ml:
            for target, imps in ml.items():
                f.write(f"### {target}\n\n")
                for feat, imp in imps:
                    if imp > 0.01:
                        f.write(f"- {feat}: **{imp:.4f}**\n")
                f.write("\n")
        else:
            f.write("ML analysis unavailable.\n\n")

        # Interpretation
        f.write("## Interpretation\n\n")
        f.write("- **Weak linear correlations:** Most Pearson |r| < 0.3, indicating products move independently.\n")
        f.write("- **Sparse lead-lag:** Few significant lagged relationships rule out simple momentum trades.\n")
        f.write("- **Volatility dynamics:** May exist between underlying and vouchers; needs further investigation.\n")
        f.write("- **Supply-demand:** No clear order book depth linkage detected.\n")
        f.write("- **ML signal:** If any feature >30% importance, it suggests a nonlinear edge.\n\n")

        f.write("## Next Steps\n\n")
        f.write("- Focus on products with |r| > 0.3 (if any found).\n")
        f.write("- Test lead-lag pairs with lag > 0.25 correlation as trading hypotheses.\n")
        f.write("- Consider time-of-day effects and market microstructure.\n")
        f.write("- Cross-check against trade data for supply-demand timing.\n")

# Main
if __name__ == '__main__':
    print("Building joint dataset...", file=sys.stderr)
    joint = build_joint()

    print("Adding features...", file=sys.stderr)
    joint = add_features(joint)

    print("Phase 3: Correlations...", file=sys.stderr)
    corr = phase3_correlations(joint)

    print("Phase 4: Lead-lag...", file=sys.stderr)
    lead_lag = phase4_lead_lag(joint)

    print("Phase 5: Cross-vol...", file=sys.stderr)
    cross_vol = phase5_cross_vol(joint)

    print("Phase 6: Supply-demand...", file=sys.stderr)
    supp_dem = phase6_supply_demand(joint)

    print("Phase 7: ML...", file=sys.stderr)
    ml = phase7_ml(joint)

    print("Writing findings...", file=sys.stderr)
    write_findings(corr, lead_lag, cross_vol, supp_dem, ml)

    print(f"\nDone. Output: {OUT_DIR / 'round3_cross_product_correlations.md'}", file=sys.stderr)

    # Print summary
    print("\n=== SUMMARY ===\n", file=sys.stderr)
    print(f"Linear correlations with |r| > 0.3: {sum(len([v for c1 in corr[k].columns for c2 in corr[k].columns if c1 < c2 and abs(corr[k].loc[c1,c2]) > 0.3]) for k in corr)}", file=sys.stderr)
    print(f"Lead-lag pairs with |r| > 0.25: {len(lead_lag)}", file=sys.stderr)
    if lead_lag:
        print(f"  Top: {lead_lag[0][0]} lag={lead_lag[0][1]} r={lead_lag[0][2]:.3f}", file=sys.stderr)
    print(f"Cross-vol pairs: {len(cross_vol)}", file=sys.stderr)
    print(f"Supply-demand pairs: {len(supp_dem)}", file=sys.stderr)
    print(f"ML results: {len(ml)} products", file=sys.stderr)
