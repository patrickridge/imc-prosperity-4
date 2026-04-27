"""
Insight 5: Cross-product relationship check between VE and HP.
Expected: independence confirmed. Looking for subtle vol/spread links.
"""

import pandas as pd
import numpy as np
from scipy import stats

DATA_DIR = "data/round4"
DAYS = [1, 2, 3]


def load_mid_prices():
    """Load mid prices for VE and HP, indexed by (day, timestamp)."""
    frames = []
    for d in DAYS:
        df = pd.read_csv(f"{DATA_DIR}/prices_round_4_day_{d}.csv", sep=";")
        frames.append(df)
    all_data = pd.concat(frames)
    ve = all_data[all_data["product"] == "VELVETFRUIT_EXTRACT"][["day", "timestamp", "mid_price", "bid_price_1", "ask_price_1"]].copy()
    hp = all_data[all_data["product"] == "HYDROGEL_PACK"][["day", "timestamp", "mid_price", "bid_price_1", "ask_price_1"]].copy()
    ve.columns = ["day", "timestamp", "ve_mid", "ve_bid", "ve_ask"]
    hp.columns = ["day", "timestamp", "hp_mid", "hp_bid", "hp_ask"]
    merged = ve.merge(hp, on=["day", "timestamp"], how="inner")
    return merged


def check_return_correlation(df):
    """1. Per-tick return correlation."""
    print("=" * 60)
    print("1. RETURN CORRELATION (per-tick)")
    print("=" * 60)
    for day in DAYS:
        subset = df[df["day"] == day].copy()
        subset["ve_ret"] = subset["ve_mid"].diff()
        subset["hp_ret"] = subset["hp_mid"].diff()
        subset = subset.dropna()
        corr, pval = stats.pearsonr(subset["ve_ret"], subset["hp_ret"])
        print(f"  Day {day}: corr={corr:.4f}, p={pval:.4f}, n={len(subset)}")

    # All days combined
    df_all = df.copy()
    df_all["ve_ret"] = df_all.groupby("day")["ve_mid"].diff()
    df_all["hp_ret"] = df_all.groupby("day")["hp_mid"].diff()
    df_all = df_all.dropna()
    corr, pval = stats.pearsonr(df_all["ve_ret"], df_all["hp_ret"])
    print(f"  ALL:   corr={corr:.4f}, p={pval:.4f}, n={len(df_all)}")
    print()


def check_volatility_correlation(df):
    """2. Rolling absolute return (vol proxy) correlation."""
    print("=" * 60)
    print("2. VOLATILITY CORRELATION (rolling |return|)")
    print("=" * 60)
    df_all = df.copy()
    df_all["ve_ret"] = df_all.groupby("day")["ve_mid"].diff()
    df_all["hp_ret"] = df_all.groupby("day")["hp_mid"].diff()
    df_all["ve_abs_ret"] = df_all["ve_ret"].abs()
    df_all["hp_abs_ret"] = df_all["hp_ret"].abs()

    for window in [100, 500, 1000]:
        df_all[f"ve_vol_{window}"] = df_all.groupby("day")["ve_abs_ret"].transform(
            lambda x: x.rolling(window, min_periods=window).mean()
        )
        df_all[f"hp_vol_{window}"] = df_all.groupby("day")["hp_abs_ret"].transform(
            lambda x: x.rolling(window, min_periods=window).mean()
        )
        valid = df_all[[f"ve_vol_{window}", f"hp_vol_{window}"]].dropna()
        if len(valid) > 10:
            corr, pval = stats.pearsonr(valid[f"ve_vol_{window}"], valid[f"hp_vol_{window}"])
            print(f"  Window {window:>4}: corr={corr:.4f}, p={pval:.4f}, n={len(valid)}")
        else:
            print(f"  Window {window:>4}: insufficient data")
    print()


def check_spread_correlation(df):
    """3. Spread correlation — does one widening predict the other?"""
    print("=" * 60)
    print("3. SPREAD CORRELATION")
    print("=" * 60)
    df_all = df.copy()
    df_all["ve_spread"] = df_all["ve_ask"] - df_all["ve_bid"]
    df_all["hp_spread"] = df_all["hp_ask"] - df_all["hp_bid"]

    # Contemporaneous
    valid = df_all[["ve_spread", "hp_spread"]].dropna()
    corr, pval = stats.pearsonr(valid["ve_spread"], valid["hp_spread"])
    print(f"  Contemporaneous: corr={corr:.4f}, p={pval:.4f}")

    # Lead-lag: VE spread -> HP spread (1-tick lag)
    df_all["hp_spread_next"] = df_all.groupby("day")["hp_spread"].shift(-1)
    df_all["ve_spread_next"] = df_all.groupby("day")["ve_spread"].shift(-1)
    valid = df_all[["ve_spread", "hp_spread_next"]].dropna()
    corr, pval = stats.pearsonr(valid["ve_spread"], valid["hp_spread_next"])
    print(f"  VE spread -> HP spread (1 tick): corr={corr:.4f}, p={pval:.4f}")

    valid = df_all[["hp_spread", "ve_spread_next"]].dropna()
    corr, pval = stats.pearsonr(valid["hp_spread"], valid["ve_spread_next"])
    print(f"  HP spread -> VE spread (1 tick): corr={corr:.4f}, p={pval:.4f}")
    print()


def check_delta_hedge(df):
    """4. Does HP hedge VE delta exposure?"""
    print("=" * 60)
    print("4. DELTA HEDGE CHECK (HP as hedge for VE exposure)")
    print("=" * 60)
    df_all = df.copy()
    df_all["ve_ret"] = df_all.groupby("day")["ve_mid"].diff()
    df_all["hp_ret"] = df_all.groupby("day")["hp_mid"].diff()
    df_all = df_all.dropna(subset=["ve_ret", "hp_ret"])

    # Portfolio: long 1 unit VE, short h units HP
    # Variance of portfolio = var(ve) + h^2*var(hp) - 2*h*cov(ve, hp)
    # Optimal h = cov(ve, hp) / var(hp)
    cov = np.cov(df_all["ve_ret"], df_all["hp_ret"])
    var_ve = cov[0, 0]
    var_hp = cov[1, 1]
    cov_ve_hp = cov[0, 1]
    optimal_h = cov_ve_hp / var_hp

    var_unhedged = var_ve
    var_hedged = var_ve + optimal_h**2 * var_hp - 2 * optimal_h * cov_ve_hp
    reduction_pct = (1 - var_hedged / var_unhedged) * 100

    print(f"  Var(VE returns):   {var_ve:.4f}")
    print(f"  Var(HP returns):   {var_hp:.4f}")
    print(f"  Cov(VE, HP):       {cov_ve_hp:.4f}")
    print(f"  Optimal hedge ratio (h): {optimal_h:.4f}")
    print(f"  Variance reduction from hedging: {reduction_pct:.4f}%")
    print()
    if abs(reduction_pct) < 1:
        print("  => HP provides NO meaningful hedge for VE delta exposure.")
    else:
        print(f"  => HP provides {reduction_pct:.2f}% variance reduction. Worth investigating.")
    print()


if __name__ == "__main__":
    print("Cross-product analysis: VELVETFRUIT_EXTRACT vs HYDROGEL_PACK")
    print()
    df = load_mid_prices()
    print(f"Loaded {len(df)} paired observations across {len(DAYS)} days")
    print()
    check_return_correlation(df)
    check_volatility_correlation(df)
    check_spread_correlation(df)
    check_delta_hedge(df)
    print("CONCLUSION: See above. If all correlations are near zero,")
    print("treating VE and HP independently remains correct.")
