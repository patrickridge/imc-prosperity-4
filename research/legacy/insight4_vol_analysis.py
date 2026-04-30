"""
IV vs Realized Vol analysis for VEV options.
Answers: are we overpaying or underpaying for options?
"""

import numpy as np
import pandas as pd
from scipy.stats import norm
from scipy.optimize import brentq

# ─── Config ───────────────────────────────────────────────────────────────────
DATA_DIR = "data/round4"
STRIKES = [4000, 4500, 5000, 5100, 5200, 5300, 5400, 5500, 6000, 6500]
TICKS_PER_DAY = 10_000
TRADING_DAYS_PER_YEAR = 252
TICKS_PER_YEAR = TICKS_PER_DAY * TRADING_DAYS_PER_YEAR
RISK_FREE = 0.0

PRIOR_IVS = {
    4000: 0.828,
    5000: None,
    5100: None,
    5200: 0.268,
    5300: 0.279,
    5400: 0.252,
    5500: 0.271,
}


# ─── Black-Scholes (vectorized) ──────────────────────────────────────────────
def bs_call_price_vec(S, K, T, sigma):
    """Vectorized BS call price. S, sigma can be arrays."""
    S = np.asarray(S, dtype=float)
    sigma = np.asarray(sigma, dtype=float)
    sqrt_T = np.sqrt(T)
    d1 = (np.log(S / K) + 0.5 * sigma**2 * T) / (sigma * sqrt_T)
    d2 = d1 - sigma * sqrt_T
    return S * norm.cdf(d1) - K * norm.cdf(d2)


def bs_call_price_scalar(S, K, T, sigma):
    """Scalar BS call price."""
    if T <= 0 or sigma <= 0:
        return max(S - K, 0.0)
    d1 = (np.log(S / K) + 0.5 * sigma**2 * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    return S * norm.cdf(d1) - K * norm.cdf(d2)


def implied_vol_scalar(market_price, S, K, T):
    """Back out IV from market price using Brent's method."""
    intrinsic = max(S - K, 0.0)
    if market_price <= intrinsic + 0.01:
        return np.nan
    if T <= 0:
        return np.nan

    def objective(sigma):
        return bs_call_price_scalar(S, K, T, sigma) - market_price

    try:
        low_val = objective(0.01)
        high_val = objective(5.0)
        if low_val * high_val > 0:
            return np.nan
        return brentq(objective, 0.01, 5.0, xtol=1e-6)
    except (ValueError, RuntimeError):
        return np.nan


def implied_vol_vec(market_prices, spots, K, T):
    """Compute IV for arrays of market_prices and spots at fixed K and T.
    Uses vectorized Newton-Raphson for speed.
    """
    S = np.asarray(spots, dtype=float)
    C_mkt = np.asarray(market_prices, dtype=float)
    n = len(S)

    intrinsic = np.maximum(S - K, 0.0)
    valid = C_mkt > intrinsic + 0.01

    result = np.full(n, np.nan)
    if not valid.any():
        return result

    S_v = S[valid]
    C_v = C_mkt[valid]
    sqrt_T = np.sqrt(T)

    # Initial guess via Brenner-Subrahmanyam approximation
    sigma = np.sqrt(2 * np.pi / T) * C_v / S_v
    sigma = np.clip(sigma, 0.05, 4.0)

    for _ in range(50):
        d1 = (np.log(S_v / K) + 0.5 * sigma**2 * T) / (sigma * sqrt_T)
        d2 = d1 - sigma * sqrt_T
        C_bs = S_v * norm.cdf(d1) - K * norm.cdf(d2)
        vega = S_v * norm.pdf(d1) * sqrt_T

        # Avoid division by tiny vega
        vega_safe = np.where(vega > 1e-10, vega, 1e-10)
        sigma_new = sigma - (C_bs - C_v) / vega_safe
        sigma_new = np.clip(sigma_new, 0.01, 5.0)

        converged = np.abs(sigma_new - sigma) < 1e-6
        sigma = sigma_new
        if converged.all():
            break

    # Mark non-converged or out-of-bounds as NaN
    sigma[(sigma <= 0.011) | (sigma >= 4.99)] = np.nan

    result[valid] = sigma
    return result


# ─── Load Data ────────────────────────────────────────────────────────────────
def load_prices():
    """Load all 3 days of price data."""
    frames = []
    for day in [1, 2, 3]:
        df = pd.read_csv(f"{DATA_DIR}/prices_round_4_day_{day}.csv", sep=";")
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


# ─── Part 1: Realized Volatility ─────────────────────────────────────────────
def compute_realized_vol(prices_df):
    """Compute realized vol of VE spot from tick-level returns."""
    print("=" * 70)
    print("PART 1: REALIZED VOLATILITY OF VELVETFRUIT_EXTRACT")
    print("=" * 70)

    ve = prices_df[prices_df["product"] == "VELVETFRUIT_EXTRACT"].copy()
    ve = ve.sort_values(["day", "timestamp"]).reset_index(drop=True)

    # Per-tick log returns
    ve["log_return"] = np.log(ve["mid_price"] / ve["mid_price"].shift(1))
    # Remove cross-day returns
    ve.loc[ve["day"] != ve["day"].shift(1), "log_return"] = np.nan

    # Per-day stats
    print("\nPer-day realized vol (annualized = tick_std * sqrt(ticks_per_year)):")
    print(f"{'Day':<6} {'Ticks':<8} {'Tick Std':<12} {'Daily Vol':<12} {'Annual Vol':<12} {'Mean Px':<10}")
    print("-" * 62)

    daily_ann_vols = []
    for day in [1, 2, 3]:
        day_data = ve[ve["day"] == day]
        returns = day_data["log_return"].dropna()
        n_ticks = len(returns)
        ret_std = returns.std()
        daily_vol = ret_std * np.sqrt(TICKS_PER_DAY)
        ann_vol = ret_std * np.sqrt(TICKS_PER_YEAR)
        mean_price = day_data["mid_price"].mean()
        daily_ann_vols.append(ann_vol)
        print(f"{day:<6} {n_ticks:<8} {ret_std:.6f}     {daily_vol:.4f}       "
              f"{ann_vol:.4f}       {mean_price:.1f}")

    # Overall
    all_returns = ve["log_return"].dropna()
    overall_std = all_returns.std()
    overall_daily_vol = overall_std * np.sqrt(TICKS_PER_DAY)
    overall_ann_vol = overall_std * np.sqrt(TICKS_PER_YEAR)
    print(f"\nOverall tick_std={overall_std:.6f}")
    print(f"  Daily vol  (tick_std * sqrt(10000)):          {overall_daily_vol:.4f}")
    print(f"  Annual vol (tick_std * sqrt(10000 * 252)):    {overall_ann_vol:.4f}")
    print(f"  Avg of per-day annual vols:                   {np.mean(daily_ann_vols):.4f}")

    # Rolling vol (annualized)
    print("\nRolling realized vol (ANNUALIZED) — intraday variation:")
    print(f"{'Window':<10} {'Min':<10} {'Max':<10} {'Mean':<10} {'Std':<10}")
    print("-" * 50)
    for window in [500, 1000, 2000]:
        rolling_std = ve["log_return"].rolling(window).std()
        rolling_ann = rolling_std * np.sqrt(TICKS_PER_YEAR)
        valid = rolling_ann.dropna()
        print(f"{window:<10} {valid.min():.4f}     {valid.max():.4f}     "
              f"{valid.mean():.4f}     {valid.std():.4f}")

    return overall_ann_vol, daily_ann_vols


# ─── Part 2: Implied Volatility ──────────────────────────────────────────────
def calibrate_tte(prices_df):
    """
    Estimate TTE by trying values and seeing which produces IVs
    closest to prior IVs for VEV_5300.
    Also try with VEV_5200 as cross-check.
    """
    print("\n" + "=" * 70)
    print("PART 2: TTE CALIBRATION")
    print("=" * 70)

    ve = prices_df[prices_df["product"] == "VELVETFRUIT_EXTRACT"][["day", "timestamp", "mid_price"]]
    vev5300 = prices_df[prices_df["product"] == "VEV_5300"][["day", "timestamp", "mid_price"]]

    merged = vev5300.merge(ve, on=["day", "timestamp"], suffixes=("_opt", "_spot"))

    print("\nTrying TTE values (in days). Reporting avg IV for VEV_5300:")
    print(f"{'TTE (days)':<12} {'Avg IV':<10} {'Diff from prior (0.279)':<25}")
    print("-" * 50)

    best_tte_days = None
    best_diff = 999

    for tte_days in range(1, 11):
        T = tte_days / 252.0
        ivs = implied_vol_vec(
            merged["mid_price_opt"].values,
            merged["mid_price_spot"].values,
            5300, T
        )
        valid_ivs = ivs[~np.isnan(ivs)]
        if len(valid_ivs) > 0:
            avg_iv = valid_ivs.mean()
            diff = abs(avg_iv - 0.279)
            if diff < best_diff:
                best_diff = diff
                best_tte_days = tte_days
            print(f"{tte_days:<12} {avg_iv:.4f}     {diff:.4f}")

    print(f"\nBest TTE estimate: {best_tte_days} days (T={best_tte_days/252:.6f} years)")

    # Cross-check with VEV_5200
    vev5200 = prices_df[prices_df["product"] == "VEV_5200"][["day", "timestamp", "mid_price"]]
    merged52 = vev5200.merge(ve, on=["day", "timestamp"], suffixes=("_opt", "_spot"))
    T_best = best_tte_days / 252.0
    ivs52 = implied_vol_vec(merged52["mid_price_opt"].values, merged52["mid_price_spot"].values, 5200, T_best)
    valid52 = ivs52[~np.isnan(ivs52)]
    if len(valid52) > 0:
        print(f"Cross-check: VEV_5200 avg IV at TTE={best_tte_days}d: {valid52.mean():.4f} (prior: 0.268)")

    return best_tte_days


def compute_implied_vols(prices_df, tte_days):
    """Compute IV for each strike at each timestamp (vectorized)."""
    print("\n" + "=" * 70)
    print("PART 2 (cont): IMPLIED VOLATILITY PER STRIKE")
    print("=" * 70)

    T = tte_days / 252.0
    ve = prices_df[prices_df["product"] == "VELVETFRUIT_EXTRACT"][["day", "timestamp", "mid_price"]]

    all_results = []

    for strike in STRIKES:
        product = f"VEV_{strike}"
        opt = prices_df[prices_df["product"] == product][["day", "timestamp", "mid_price"]]
        if opt.empty:
            continue

        merged = opt.merge(ve, on=["day", "timestamp"], suffixes=("_opt", "_spot"))

        ivs = implied_vol_vec(
            merged["mid_price_opt"].values,
            merged["mid_price_spot"].values,
            strike, T
        )

        df_chunk = pd.DataFrame({
            "day": merged["day"].values,
            "timestamp": merged["timestamp"].values,
            "strike": strike,
            "spot": merged["mid_price_spot"].values,
            "opt_mid": merged["mid_price_opt"].values,
            "iv": ivs,
            "moneyness": strike / merged["mid_price_spot"].values,
        })
        all_results.append(df_chunk)

    iv_df = pd.concat(all_results, ignore_index=True)

    # Summary per strike per day
    print(f"\nAvg IV per strike per day (TTE={tte_days} days):")
    print(f"{'Strike':<8} {'Day 1':<10} {'Day 2':<10} {'Day 3':<10} {'All':<10} {'Prior':<10}")
    print("-" * 60)

    for strike in STRIKES:
        sdata = iv_df[iv_df["strike"] == strike]
        if sdata.empty:
            continue
        vals = []
        for day in [1, 2, 3]:
            ddata = sdata[sdata["day"] == day]["iv"].dropna()
            vals.append(f"{ddata.mean():.4f}" if len(ddata) > 0 else "  N/A ")
        all_iv = sdata["iv"].dropna().mean()
        prior = PRIOR_IVS.get(strike)
        prior_str = f"{prior:.3f}" if prior else "  -  "
        print(f"{strike:<8} {vals[0]:<10} {vals[1]:<10} {vals[2]:<10} {all_iv:.4f}     {prior_str}")

    return iv_df


# ─── Part 3: IV vs Realized Vol ──────────────────────────────────────────────
def compare_iv_vs_realized(iv_df, realized_vol, daily_vols):
    """Compare implied vol to realized vol."""
    print("\n" + "=" * 70)
    print("PART 3: IV vs REALIZED VOL COMPARISON")
    print("=" * 70)

    print(f"\nRealized vol (annualized): {realized_vol:.4f}")
    print(f"Per-day realized: Day1={daily_vols[0]:.4f}, Day2={daily_vols[1]:.4f}, Day3={daily_vols[2]:.4f}")

    print(f"\n{'Strike':<8} {'Avg IV':<10} {'RV':<10} {'IV - RV':<10} {'IV/RV':<10} {'Status':<15}")
    print("-" * 65)

    for strike in STRIKES:
        sdata = iv_df[iv_df["strike"] == strike]["iv"].dropna()
        if len(sdata) == 0:
            continue
        avg_iv = sdata.mean()
        diff = avg_iv - realized_vol
        ratio = avg_iv / realized_vol
        status = "EXPENSIVE" if diff > 0 else "CHEAP"
        print(f"{strike:<8} {avg_iv:.4f}     {realized_vol:.4f}     "
              f"{diff:+.4f}    {ratio:.3f}     {status}")

    # ATM options (5200, 5300) are most relevant
    atm_strikes = [5200, 5300]
    atm_ivs = iv_df[iv_df["strike"].isin(atm_strikes)]["iv"].dropna()
    if len(atm_ivs) > 0:
        atm_avg = atm_ivs.mean()
        print(f"\nATM avg IV (5200/5300): {atm_avg:.4f}")
        print(f"Realized vol:           {realized_vol:.4f}")
        print(f"Gap (IV - RV):          {atm_avg - realized_vol:+.4f}")
        if atm_avg > realized_vol:
            print(">>> OPTIONS ARE EXPENSIVE relative to realized movement")
            print(">>> Strategy implication: should be NET SELLER, not buyer")
        else:
            print(">>> OPTIONS ARE CHEAP relative to realized movement")
            print(">>> Strategy implication: buying is correct")


# ─── Part 4: Smile Shape ─────────────────────────────────────────────────────
def analyze_smile(iv_df):
    """Analyze IV smile/skew structure."""
    print("\n" + "=" * 70)
    print("PART 4: IV SMILE / SKEW SHAPE")
    print("=" * 70)

    print("\nIV vs Moneyness (K/S) per day:")
    print(f"{'Strike':<8} {'Avg K/S':<10} {'Day1 IV':<10} {'Day2 IV':<10} {'Day3 IV':<10}")
    print("-" * 50)

    for strike in STRIKES:
        sdata = iv_df[iv_df["strike"] == strike]
        if sdata.empty:
            continue
        avg_moneyness = sdata["moneyness"].mean()
        day_ivs = []
        for day in [1, 2, 3]:
            ddata = sdata[sdata["day"] == day]["iv"].dropna()
            day_ivs.append(f"{ddata.mean():.4f}" if len(ddata) > 0 else "  N/A ")
        print(f"{strike:<8} {avg_moneyness:.4f}     {day_ivs[0]:<10} {day_ivs[1]:<10} {day_ivs[2]:<10}")

    # Check for smile: is IV higher at extremes vs ATM?
    atm_iv = iv_df[iv_df["strike"].isin([5200, 5300])]["iv"].dropna().mean()
    otm_iv = iv_df[iv_df["strike"].isin([5500, 6000, 6500])]["iv"].dropna().mean()
    itm_iv = iv_df[iv_df["strike"].isin([4000, 4500])]["iv"].dropna().mean()

    print(f"\nSmile diagnostics:")
    print(f"  ITM avg IV (4000, 4500):   {itm_iv:.4f}")
    print(f"  ATM avg IV (5200, 5300):   {atm_iv:.4f}")
    print(f"  OTM avg IV (5500+):        {otm_iv:.4f}")

    if itm_iv > atm_iv and otm_iv > atm_iv:
        print("  Shape: SMILE (both wings elevated)")
    elif itm_iv > atm_iv:
        print("  Shape: PUT SKEW (left wing elevated)")
    elif otm_iv > atm_iv:
        print("  Shape: CALL SKEW (right wing elevated)")
    else:
        print("  Shape: FLAT or inverted")

    # Day-over-day consistency
    print("\nDay-over-day IV change (ATM strikes 5200/5300):")
    for day in [1, 2, 3]:
        ddata = iv_df[(iv_df["strike"].isin([5200, 5300])) & (iv_df["day"] == day)]["iv"].dropna()
        if len(ddata) > 0:
            print(f"  Day {day}: mean={ddata.mean():.4f}, std={ddata.std():.4f}, n={len(ddata)}")


# ─── Part 5: Strategy Implication ─────────────────────────────────────────────
def strategy_implication(iv_df, realized_vol, tte_days):
    """Quantify overpay/underpay in ticks per option."""
    print("\n" + "=" * 70)
    print("PART 5: STRATEGY IMPLICATION — TICK-LEVEL OVERPAY/UNDERPAY")
    print("=" * 70)

    T = tte_days / 252.0

    print("\nComparing option price at market IV vs price at realized vol:")
    print(f"{'Strike':<8} {'Avg Spot':<10} {'Mkt Price':<12} {'RV Price':<12} "
          f"{'Overpay/tick':<14} {'Status':<10}")
    print("-" * 70)

    for strike in STRIKES:
        sdata = iv_df[iv_df["strike"] == strike].dropna(subset=["iv"])
        if len(sdata) == 0:
            continue

        avg_spot = sdata["spot"].mean()
        avg_mkt_price = sdata["opt_mid"].mean()
        # Price at realized vol
        rv_price = bs_call_price_scalar(avg_spot, strike, T, realized_vol)
        overpay = avg_mkt_price - rv_price
        status = "EXPENSIVE" if overpay > 0 else "CHEAP"

        print(f"{strike:<8} {avg_spot:.1f}     {avg_mkt_price:.1f}       "
              f"{rv_price:.1f}       {overpay:+.1f}         {status}")

    # If we are net BUYER and options are expensive, how much are we losing?
    print("\n--- Strategy Recommendation ---")
    atm_data = iv_df[iv_df["strike"].isin([5200, 5300])].dropna(subset=["iv"])
    if len(atm_data) > 0:
        avg_iv = atm_data["iv"].mean()
        avg_spot = atm_data["spot"].mean()
        avg_mkt = atm_data["opt_mid"].mean()
        rv_price_5200 = bs_call_price_scalar(avg_spot, 5200, T, realized_vol)
        rv_price_5300 = bs_call_price_scalar(avg_spot, 5300, T, realized_vol)
        avg_rv_price = (rv_price_5200 + rv_price_5300) / 2

        print(f"\nATM options (5200/5300):")
        print(f"  Avg market mid:   {avg_mkt:.1f}")
        print(f"  Fair value at RV: {avg_rv_price:.1f}")
        print(f"  Vol gap:          IV={avg_iv:.4f} vs RV={realized_vol:.4f}")

        if avg_iv > realized_vol:
            print(f"\n  CONCLUSION: Options are OVERPRICED by ~{avg_mkt - avg_rv_price:.1f} ticks")
            print(f"  Current strategy is a NET BUYER → losing edge on vol")
            print(f"  Recommendation: become a NET SELLER or at minimum reduce bid aggression")
        else:
            print(f"\n  CONCLUSION: Options are UNDERPRICED by ~{avg_rv_price - avg_mkt:.1f} ticks")
            print(f"  Current strategy as NET BUYER is CORRECT")


# ─── Part 6: Per-Day Consistency ──────────────────────────────────────────────
def per_day_consistency(iv_df, daily_vols):
    """Check if the IV-RV gap is consistent across days."""
    print("\n" + "=" * 70)
    print("PART 6: PER-DAY CONSISTENCY")
    print("=" * 70)

    print(f"\n{'Day':<6} {'RV':<10} {'ATM IV':<10} {'Gap':<10} {'Signal':<15}")
    print("-" * 50)

    for i, day in enumerate([1, 2, 3]):
        rv = daily_vols[i]
        day_iv = iv_df[(iv_df["strike"].isin([5200, 5300])) & (iv_df["day"] == day)]["iv"].dropna()
        if len(day_iv) > 0:
            avg_iv = day_iv.mean()
            gap = avg_iv - rv
            signal = "SELL OPTIONS" if gap > 0 else "BUY OPTIONS"
            print(f"{day:<6} {rv:.4f}     {avg_iv:.4f}     {gap:+.4f}    {signal}")

    print("\nIs the signal consistent across all 3 days?")
    signals = []
    for i, day in enumerate([1, 2, 3]):
        rv = daily_vols[i]
        day_iv = iv_df[(iv_df["strike"].isin([5200, 5300])) & (iv_df["day"] == day)]["iv"].dropna()
        if len(day_iv) > 0:
            signals.append(day_iv.mean() - rv)

    if all(s > 0 for s in signals):
        print("YES — IV > RV on ALL days. Consistent signal: sell options.")
    elif all(s < 0 for s in signals):
        print("YES — IV < RV on ALL days. Consistent signal: buy options.")
    else:
        print("MIXED — signal differs across days. Proceed with caution.")


# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    print("Loading data...")
    prices_df = load_prices()
    print(f"Loaded {len(prices_df)} rows across 3 days")

    # Part 1
    realized_vol, daily_vols = compute_realized_vol(prices_df)

    # Part 2
    tte_days = calibrate_tte(prices_df)
    iv_df = compute_implied_vols(prices_df, tte_days)

    # Part 3
    compare_iv_vs_realized(iv_df, realized_vol, daily_vols)

    # Part 4
    analyze_smile(iv_df)

    # Part 5
    strategy_implication(iv_df, realized_vol, tte_days)

    # Part 6
    per_day_consistency(iv_df, daily_vols)

    print("\n" + "=" * 70)
    print("ANALYSIS COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
