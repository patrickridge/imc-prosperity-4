"""
Monte Carlo verification of chooser option fair value.

Parameters from P4 wiki:
  S0=50, K=50, sigma=2.51, r=0, drift=0
  dt = 1/1008 (4 steps/day, 252 days)
  Choice at step 40 (T+14 days), expiry at step 60 (T+21 days)
"""

import numpy as np
from scipy.stats import norm

# ── Constants ──────────────────────────────────────────────────────────
S0 = 50.0
STRIKE = 50.0
SIGMA = 2.51          # 251% annualized vol
RISK_FREE = 0.0
DRIFT = 0.0
DT = 1.0 / 1008.0    # 4 steps/day, 252 days/year
CHOICE_STEP = 40      # step 40 = T+14 days
EXPIRY_STEP = 60      # step 60 = T+21 days

T_CHOICE = CHOICE_STEP * DT   # time to choice in years
T_EXPIRY = EXPIRY_STEP * DT   # time to expiry in years


# ── Black-Scholes helpers ──────────────────────────────────────────────
def bs_call(S, K, T, sigma, r=0.0):
    if T <= 0:
        return max(S - K, 0.0)
    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    return S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)


def bs_put(S, K, T, sigma, r=0.0):
    if T <= 0:
        return max(K - S, 0.0)
    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    return K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)


# ── Monte Carlo engine ────────────────────────────────────────────────
def simulate_chooser(n_paths, seed, equal_handling="worthless"):
    """
    Simulate chooser option payoffs.

    equal_handling:
      "worthless" — S_40 == K → payoff = 0
      "call"      — S_40 == K → becomes call
      "max_value" — S_40 == K → pick whichever of call/put is worth more
    """
    rng = np.random.default_rng(seed)

    # GBM: S_{t+1} = S_t * exp((drift - 0.5*sigma^2)*dt + sigma*sqrt(dt)*Z)
    drift_term = (DRIFT - 0.5 * SIGMA**2) * DT
    vol_term = SIGMA * np.sqrt(DT)

    # Generate all random increments: steps 1..60
    Z = rng.standard_normal((n_paths, EXPIRY_STEP))
    log_returns = drift_term + vol_term * Z
    log_price_paths = np.cumsum(log_returns, axis=1)

    # S at choice point (step 40) and expiry (step 60)
    S_choice = S0 * np.exp(log_price_paths[:, CHOICE_STEP - 1])
    S_expiry = S0 * np.exp(log_price_paths[:, EXPIRY_STEP - 1])

    # Payoffs
    call_payoff = np.maximum(S_expiry - STRIKE, 0.0)
    put_payoff = np.maximum(STRIKE - S_expiry, 0.0)

    # Decision at choice point
    is_call = S_choice > STRIKE
    is_put = S_choice < STRIKE
    is_equal = np.isclose(S_choice, STRIKE, atol=1e-12)

    payoffs = np.where(is_call, call_payoff, 0.0)
    payoffs = np.where(is_put, put_payoff, payoffs)

    n_equal = int(np.sum(is_equal))

    if equal_handling == "worthless":
        payoffs = np.where(is_equal, 0.0, payoffs)
    elif equal_handling == "call":
        payoffs = np.where(is_equal, call_payoff, payoffs)
    elif equal_handling == "max_value":
        payoffs = np.where(is_equal, np.maximum(call_payoff, put_payoff), payoffs)

    # With r=0, no discounting needed
    fair_value = np.mean(payoffs)
    std_err = np.std(payoffs, ddof=1) / np.sqrt(n_paths)
    ci_lower = fair_value - 1.96 * std_err
    ci_upper = fair_value + 1.96 * std_err

    return fair_value, std_err, ci_lower, ci_upper, n_equal


def bs_chooser_closed_form():
    """
    Closed-form simple chooser with r=0, no dividends:
      Chooser = Call(S, K, T_expiry) + Put(S, K, T_choice)
    """
    call_value = bs_call(S0, STRIKE, T_EXPIRY, SIGMA, RISK_FREE)
    put_at_choice = bs_put(S0, STRIKE, T_CHOICE, SIGMA, RISK_FREE)
    return call_value, put_at_choice, call_value + put_at_choice


def run_straddle_comparison():
    """ATM straddle = Call(K, T_expiry) + Put(K, T_expiry)."""
    call_val = bs_call(S0, STRIKE, T_EXPIRY, SIGMA, RISK_FREE)
    put_val = bs_put(S0, STRIKE, T_EXPIRY, SIGMA, RISK_FREE)
    return call_val, put_val, call_val + put_val


def run_sensitivity(vols, n_paths=500_000):
    """Fair value at different vol levels."""
    print(f"\n{'='*60}")
    print(f"SENSITIVITY ANALYSIS ({n_paths:,} paths, seed=42)")
    print(f"{'='*60}")
    print(f"  {'Vol':>8}  {'Fair Value':>12}  {'Std Err':>10}  {'95% CI':>22}")
    print(f"  {'-'*8}  {'-'*12}  {'-'*10}  {'-'*22}")
    for vol in vols:
        global SIGMA
        original_sigma = SIGMA
        SIGMA = vol
        fv, se, lo, hi, _ = simulate_chooser(n_paths, seed=42, equal_handling="call")
        print(f"  {vol:>8.2%}  {fv:>12.4f}  {se:>10.4f}  [{lo:>8.4f}, {hi:>8.4f}]")
        SIGMA = original_sigma


# ── Main ───────────────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("CHOOSER OPTION — MONTE CARLO VERIFICATION")
    print("=" * 60)
    print(f"  S0 = {S0}, K = {STRIKE}, sigma = {SIGMA} ({SIGMA:.0%})")
    print(f"  r = {RISK_FREE}, drift = {DRIFT}")
    print(f"  dt = 1/{int(1/DT)}, choice step = {CHOICE_STEP}, expiry step = {EXPIRY_STEP}")
    print(f"  T_choice = {T_CHOICE:.6f} yr ({T_CHOICE*252:.1f} days)")
    print(f"  T_expiry = {T_EXPIRY:.6f} yr ({T_EXPIRY*252:.1f} days)")

    # ── 1. MC with two seeds, three interpretations ────────────────────
    seeds = [42, 123]
    handlings = [
        ("worthless", "S40==K → worthless"),
        ("call", "S40==K → call"),
        ("max_value", "S40==K → max(call,put)"),
    ]
    n_paths = 2_000_000

    for seed in seeds:
        print(f"\n{'='*60}")
        print(f"MC SIMULATION — {n_paths:,} paths, seed={seed}")
        print(f"{'='*60}")
        print(f"  {'Interpretation':<28} {'FV':>8} {'SE':>8} {'95% CI':>22} {'#exact':>8}")
        print(f"  {'-'*28} {'-'*8} {'-'*8} {'-'*22} {'-'*8}")
        for handling, label in handlings:
            fv, se, lo, hi, n_eq = simulate_chooser(n_paths, seed, handling)
            print(f"  {label:<28} {fv:>8.4f} {se:>8.4f} [{lo:>8.4f}, {hi:>8.4f}] {n_eq:>8}")

    # ── 2. Closed-form simple chooser ──────────────────────────────────
    print(f"\n{'='*60}")
    print("CLOSED-FORM SIMPLE CHOOSER (BS, r=0)")
    print(f"{'='*60}")
    call_T, put_t, chooser_cf = bs_chooser_closed_form()
    print(f"  Call(S, K, T_expiry) = {call_T:.4f}")
    print(f"  Put(S, K, T_choice)  = {put_t:.4f}")
    print(f"  Chooser = Call + Put  = {chooser_cf:.4f}")

    # ── 3. Straddle comparison ─────────────────────────────────────────
    print(f"\n{'='*60}")
    print("STRADDLE COMPARISON (BS, r=0)")
    print(f"{'='*60}")
    call_s, put_s, straddle = run_straddle_comparison()
    print(f"  Call(S, K, T_expiry) = {call_s:.4f}")
    print(f"  Put(S, K, T_expiry)  = {put_s:.4f}")
    print(f"  Straddle             = {straddle:.4f}")
    print(f"  Chooser CF           = {chooser_cf:.4f}")
    print(f"  Straddle - Chooser   = {straddle - chooser_cf:.4f}")
    print(f"  Chooser is {(1 - chooser_cf/straddle)*100:.2f}% cheaper than straddle")

    # ── 4. Market comparison ───────────────────────────────────────────
    market_bid = 22.20
    print(f"\n{'='*60}")
    print("MARKET COMPARISON")
    print(f"{'='*60}")
    print(f"  Market bid           = {market_bid:.2f}")
    print(f"  MC fair value (call) ~ see above")
    print(f"  Closed-form          = {chooser_cf:.4f}")
    print(f"  Difference (mkt-CF)  = {market_bid - chooser_cf:.4f}")
    if market_bid > chooser_cf:
        print(f"  → Market OVERPRICES by {market_bid - chooser_cf:.4f} → SELL signal")
    else:
        print(f"  → Market UNDERPRICES by {chooser_cf - market_bid:.4f} → BUY signal")

    # ── 5. Sensitivity ─────────────────────────────────────────────────
    run_sensitivity([2.40, 2.51, 2.60])

    print(f"\n{'='*60}")
    print("DONE")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
