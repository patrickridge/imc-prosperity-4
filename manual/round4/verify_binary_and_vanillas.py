"""
Verify Monte Carlo pricing for binary put and 2-week vanilla options.
Compares MC estimates against Black-Scholes closed-form solutions.
"""

import numpy as np
from scipy.stats import norm

# ─── Parameters (from P4 wiki) ───────────────────────────────────────────────
S0 = 50.0
SIGMA_ANN = 2.51          # 251% annualized volatility
DRIFT = 0.0
R = 0.0                   # risk-free rate
DT = 1.0 / 1008.0        # 4 steps/day, 252 days/year
SEEDS = [42, 123]
N_PATHS = 2_000_000

# Contract specs
BINARY_PUT_STRIKE = 40
BINARY_PUT_STEPS = 60
BINARY_PUT_PAYOUT = 10

VANILLA_STRIKE = 50
VANILLA_STEPS = 40

# Market prices
MARKET_BINARY_PUT_BID = 5.00
MARKET_VANILLA_ASK = 9.75


# ─── Black-Scholes helpers ───────────────────────────────────────────────────

def bs_d1(S, K, T, sigma, r=0.0):
    return (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))

def bs_d2(S, K, T, sigma, r=0.0):
    return bs_d1(S, K, T, sigma, r) - sigma * np.sqrt(T)

def bs_call(S, K, T, sigma, r=0.0):
    d1 = bs_d1(S, K, T, sigma, r)
    d2 = bs_d2(S, K, T, sigma, r)
    return S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)

def bs_put(S, K, T, sigma, r=0.0):
    d1 = bs_d1(S, K, T, sigma, r)
    d2 = bs_d2(S, K, T, sigma, r)
    return K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)

def bs_binary_put_prob(S, K, T, sigma, r=0.0):
    """P(S_T < K) under risk-neutral measure = N(-d2)."""
    d2 = bs_d2(S, K, T, sigma, r)
    return norm.cdf(-d2)


# ─── Monte Carlo engine ─────────────────────────────────────────────────────

def simulate_terminal_prices(S0, sigma, dt, n_steps, n_paths, seed):
    rng = np.random.default_rng(seed)
    # GBM: S_T = S0 * exp(sum of log-returns)
    # Each step: dlog(S) = (drift - 0.5*sigma^2)*dt + sigma*sqrt(dt)*Z
    # With drift=0, r=0: dlog(S) = -0.5*sigma^2*dt + sigma*sqrt(dt)*Z
    total_drift = (-0.5 * sigma**2 * dt) * n_steps
    total_vol = sigma * np.sqrt(dt) * rng.standard_normal((n_paths,))
    # Sum of n_steps independent normals ~ N(0, n_steps)
    # But we need sum of n_steps standard normals, not one scaled by sqrt(n_steps)
    # Correct: sum of n_steps iid N(0,1) ~ N(0, n_steps), so sigma*sqrt(dt)*sum ~ N(0, sigma^2*dt*n_steps)
    # Shortcut: generate one draw from N(0, sigma^2 * dt * n_steps) directly
    z = rng.standard_normal(n_paths)
    log_return = total_drift + sigma * np.sqrt(dt * n_steps) * z
    return S0 * np.exp(log_return)


def mc_binary_put(S0, K, payout, sigma, dt, n_steps, n_paths, seed):
    S_T = simulate_terminal_prices(S0, sigma, dt, n_steps, n_paths, seed)
    payoffs = np.where(S_T < K, payout, 0.0)
    mean_val = payoffs.mean()
    std_err = payoffs.std(ddof=1) / np.sqrt(n_paths)
    prob_below = (S_T < K).mean()
    return mean_val, std_err, prob_below, S_T


def mc_vanilla(S0, K, sigma, dt, n_steps, n_paths, seed, option_type="call"):
    S_T = simulate_terminal_prices(S0, sigma, dt, n_steps, n_paths, seed)
    if option_type == "call":
        payoffs = np.maximum(S_T - K, 0.0)
    else:
        payoffs = np.maximum(K - S_T, 0.0)
    mean_val = payoffs.mean()
    std_err = payoffs.std(ddof=1) / np.sqrt(n_paths)
    return mean_val, std_err, S_T


# ─── Pretty printing ────────────────────────────────────────────────────────

def print_header(title):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")

def print_ci(label, mean, se):
    lo = mean - 1.96 * se
    hi = mean + 1.96 * se
    print(f"  {label}: {mean:.4f}  (SE={se:.4f}, 95% CI=[{lo:.4f}, {hi:.4f}])")


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    T_binary = BINARY_PUT_STEPS * DT
    T_vanilla = VANILLA_STEPS * DT

    print_header("PARAMETERS")
    print(f"  S0={S0}, sigma={SIGMA_ANN} (annualized), drift={DRIFT}, r={R}")
    print(f"  dt={DT:.6f} (1/1008)")
    print(f"  Binary put: K={BINARY_PUT_STRIKE}, T={BINARY_PUT_STEPS} steps = {T_binary:.6f} years")
    print(f"  Vanilla:    K={VANILLA_STRIKE}, T={VANILLA_STEPS} steps = {T_vanilla:.6f} years")
    print(f"  Paths: {N_PATHS:,} per seed, seeds={SEEDS}")

    # ── 1. MC pricing for all contracts ──────────────────────────────────────

    print_header("1. MONTE CARLO PRICING")

    for seed in SEEDS:
        print(f"\n  --- Seed {seed} ---")

        fv, se, prob, _ = mc_binary_put(
            S0, BINARY_PUT_STRIKE, BINARY_PUT_PAYOUT, SIGMA_ANN, DT,
            BINARY_PUT_STEPS, N_PATHS, seed
        )
        print_ci(f"AC_40_BP (binary put, payout={BINARY_PUT_PAYOUT})", fv, se)
        print(f"    P(S_60 < 40) = {prob:.6f}")

        fv_put, se_put, _ = mc_vanilla(
            S0, VANILLA_STRIKE, SIGMA_ANN, DT, VANILLA_STEPS, N_PATHS, seed, "put"
        )
        print_ci("AC_50_P_2 (2wk put)", fv_put, se_put)

        fv_call, se_call, _ = mc_vanilla(
            S0, VANILLA_STRIKE, SIGMA_ANN, DT, VANILLA_STEPS, N_PATHS, seed, "call"
        )
        print_ci("AC_50_C_2 (2wk call)", fv_call, se_call)

    # ── 2. Black-Scholes closed-form comparison ─────────────────────────────

    print_header("2. BLACK-SCHOLES CLOSED-FORM COMPARISON")

    prob_bs = bs_binary_put_prob(S0, BINARY_PUT_STRIKE, T_binary, SIGMA_ANN, R)
    fv_bs_binary = BINARY_PUT_PAYOUT * prob_bs
    print(f"  Binary put BS:")
    print(f"    d2 = {bs_d2(S0, BINARY_PUT_STRIKE, T_binary, SIGMA_ANN, R):.6f}")
    print(f"    P(S_T < 40) = N(-d2) = {prob_bs:.6f}")
    print(f"    Fair value = 10 * {prob_bs:.6f} = {fv_bs_binary:.4f}")

    fv_bs_put = bs_put(S0, VANILLA_STRIKE, T_vanilla, SIGMA_ANN, R)
    fv_bs_call = bs_call(S0, VANILLA_STRIKE, T_vanilla, SIGMA_ANN, R)
    print(f"\n  Vanilla BS:")
    print(f"    AC_50_P_2 (put)  = {fv_bs_put:.4f}")
    print(f"    AC_50_C_2 (call) = {fv_bs_call:.4f}")

    print(f"\n  Put-call parity check (r=0, S=K=50):")
    print(f"    C - P = {fv_bs_call - fv_bs_put:.6f}  (should be S-K = 0)")

    # ── 3. Binary put deep dive ──────────────────────────────────────────────

    print_header("3. BINARY PUT DEEP DIVE")

    # 3a: Tail probabilities
    print("\n  --- Tail probabilities (BS closed-form) ---")
    for K in [40, 35, 30, 25, 20]:
        p = bs_binary_put_prob(S0, K, T_binary, SIGMA_ANN, R)
        print(f"    P(S_60 < {K}) = {p:.6f}  (binary put FV = {BINARY_PUT_PAYOUT * p:.4f})")

    # 3b: Vol sensitivity
    print("\n  --- Binary put vol sensitivity ---")
    for vol in [2.40, 2.51, 2.60]:
        p = bs_binary_put_prob(S0, BINARY_PUT_STRIKE, T_binary, vol, R)
        fv = BINARY_PUT_PAYOUT * p
        print(f"    sigma={vol:.2f}: P(S<40)={p:.6f}, FV={fv:.4f}")

    # 3c: Edge calculation
    edge_per_contract = MARKET_BINARY_PUT_BID - fv_bs_binary
    volume = 50
    contract_size = 3000
    total_edge = edge_per_contract * volume * contract_size
    print(f"\n  --- Edge calculation (SELL at bid={MARKET_BINARY_PUT_BID}) ---")
    print(f"    Fair value (BS) = {fv_bs_binary:.4f}")
    print(f"    Edge/contract   = {MARKET_BINARY_PUT_BID} - {fv_bs_binary:.4f} = {edge_per_contract:.4f}")
    print(f"    Volume          = {volume}")
    print(f"    Contract size   = {contract_size}")
    print(f"    Total edge      = {edge_per_contract:.4f} * {volume} * {contract_size} = {total_edge:,.0f}")

    # ── 4. 2-week vanillas deep dive ─────────────────────────────────────────

    print_header("4. 2-WEEK VANILLAS DEEP DIVE")

    # 4a: MC vs BS comparison (average across seeds)
    put_mc_vals = []
    call_mc_vals = []
    for seed in SEEDS:
        fv_put, _, _ = mc_vanilla(S0, VANILLA_STRIKE, SIGMA_ANN, DT, VANILLA_STEPS, N_PATHS, seed, "put")
        fv_call, _, _ = mc_vanilla(S0, VANILLA_STRIKE, SIGMA_ANN, DT, VANILLA_STEPS, N_PATHS, seed, "call")
        put_mc_vals.append(fv_put)
        call_mc_vals.append(fv_call)

    avg_put_mc = np.mean(put_mc_vals)
    avg_call_mc = np.mean(call_mc_vals)

    print(f"\n  MC vs BS comparison:")
    print(f"    Put:  MC avg={avg_put_mc:.4f}, BS={fv_bs_put:.4f}, diff={avg_put_mc - fv_bs_put:.4f}")
    print(f"    Call: MC avg={avg_call_mc:.4f}, BS={fv_bs_call:.4f}, diff={avg_call_mc - fv_bs_call:.4f}")

    # 4b: Put-call parity from MC
    print(f"\n  Put-call parity (MC avg):")
    print(f"    C - P = {avg_call_mc:.4f} - {avg_put_mc:.4f} = {avg_call_mc - avg_put_mc:.4f}  (should be 0)")

    # 4c: Vol sensitivity
    print(f"\n  --- Vanilla vol sensitivity ---")
    for vol in [2.40, 2.51, 2.60]:
        p = bs_put(S0, VANILLA_STRIKE, T_vanilla, vol, R)
        c = bs_call(S0, VANILLA_STRIKE, T_vanilla, vol, R)
        print(f"    sigma={vol:.2f}: put={p:.4f}, call={c:.4f}")

    # 4d: Edge for vanillas
    print(f"\n  --- Edge calculation (BUY at ask={MARKET_VANILLA_ASK}) ---")
    put_edge = fv_bs_put - MARKET_VANILLA_ASK
    call_edge = fv_bs_call - MARKET_VANILLA_ASK
    print(f"    Put edge  = {fv_bs_put:.4f} - {MARKET_VANILLA_ASK} = {put_edge:.4f}")
    print(f"    Call edge = {fv_bs_call:.4f} - {MARKET_VANILLA_ASK} = {call_edge:.4f}")

    # ── 5. Signal reliability ────────────────────────────────────────────────

    print_header("5. SIGNAL RELIABILITY — PROBABILITY MC IS WRONG ENOUGH TO FLIP")

    # For binary put (SELL signal): we need P(true_value > market_bid)
    # i.e., P(true FV > 5.00) which would mean selling is wrong
    # MC estimate ~ N(fv_bs_binary, se^2). Use BS as truth and MC SE.
    # Actually, the question is about the MC estimate's uncertainty.
    # Use the SE from a representative MC run.
    _, se_bp, _, _ = mc_binary_put(
        S0, BINARY_PUT_STRIKE, BINARY_PUT_PAYOUT, SIGMA_ANN, DT,
        BINARY_PUT_STEPS, N_PATHS, seed=42
    )
    # P(true value > 5.00) assuming MC estimate is unbiased with given SE
    # Use BS value as point estimate, SE from MC
    z_bp = (MARKET_BINARY_PUT_BID - fv_bs_binary) / se_bp
    p_flip_bp = norm.cdf(z_bp)  # P(true < market bid) — but we want P(true > bid)
    p_flip_bp = 1.0 - norm.cdf(-z_bp)  # actually: P(X > bid) where X ~ N(fv_bs, se^2)
    # Clearer: P(true > 5) = P(Z > (5 - fv_bs) / se)
    z_bp = (MARKET_BINARY_PUT_BID - fv_bs_binary) / se_bp
    p_wrong_bp = 1.0 - norm.cdf(z_bp)
    print(f"\n  Binary put (SELL at {MARKET_BINARY_PUT_BID}):")
    print(f"    BS fair = {fv_bs_binary:.4f}, MC SE = {se_bp:.4f}")
    print(f"    z = (bid - fair) / SE = ({MARKET_BINARY_PUT_BID} - {fv_bs_binary:.4f}) / {se_bp:.4f} = {z_bp:.2f}")
    print(f"    P(true value > {MARKET_BINARY_PUT_BID}) = {p_wrong_bp:.6f}")
    print(f"    → Signal flip probability: {p_wrong_bp*100:.2f}%")

    # For vanillas (BUY signal): P(true_value < market_ask)
    _, se_put_mc, _ = mc_vanilla(S0, VANILLA_STRIKE, SIGMA_ANN, DT, VANILLA_STEPS, N_PATHS, seed=42, option_type="put")
    _, se_call_mc, _ = mc_vanilla(S0, VANILLA_STRIKE, SIGMA_ANN, DT, VANILLA_STEPS, N_PATHS, seed=42, option_type="call")

    z_put = (MARKET_VANILLA_ASK - fv_bs_put) / se_put_mc
    p_wrong_put = norm.cdf(z_put)  # P(true < ask) means BUY signal is wrong
    print(f"\n  AC_50_P_2 (BUY at {MARKET_VANILLA_ASK}):")
    print(f"    BS fair = {fv_bs_put:.4f}, MC SE = {se_put_mc:.4f}")
    print(f"    z = (ask - fair) / SE = ({MARKET_VANILLA_ASK} - {fv_bs_put:.4f}) / {se_put_mc:.4f} = {z_put:.2f}")
    print(f"    P(true value < {MARKET_VANILLA_ASK}) = {p_wrong_put:.6f}")
    print(f"    → Signal flip probability: {p_wrong_put*100:.2f}%")

    z_call = (MARKET_VANILLA_ASK - fv_bs_call) / se_call_mc
    p_wrong_call = norm.cdf(z_call)
    print(f"\n  AC_50_C_2 (BUY at {MARKET_VANILLA_ASK}):")
    print(f"    BS fair = {fv_bs_call:.4f}, MC SE = {se_call_mc:.4f}")
    print(f"    z = (ask - fair) / SE = ({MARKET_VANILLA_ASK} - {fv_bs_call:.4f}) / {se_call_mc:.4f} = {z_call:.2f}")
    print(f"    P(true value < {MARKET_VANILLA_ASK}) = {p_wrong_call:.6f}")
    print(f"    → Signal flip probability: {p_wrong_call*100:.2f}%")

    # ── Summary ──────────────────────────────────────────────────────────────

    print_header("SUMMARY: SIGNAL VERIFICATION")
    print(f"\n  Contract     | BS Fair | Market | Signal | Edge   | Flip prob")
    print(f"  {'-'*65}")
    print(f"  AC_40_BP     | {fv_bs_binary:.4f}  | bid {MARKET_BINARY_PUT_BID:.2f} | SELL   | {MARKET_BINARY_PUT_BID - fv_bs_binary:.4f} | {p_wrong_bp*100:.2f}%")
    print(f"  AC_50_P_2    | {fv_bs_put:.4f}  | ask {MARKET_VANILLA_ASK:.2f} | BUY    | {fv_bs_put - MARKET_VANILLA_ASK:.4f} | {p_wrong_put*100:.2f}%")
    print(f"  AC_50_C_2    | {fv_bs_call:.4f}  | ask {MARKET_VANILLA_ASK:.2f} | BUY    | {fv_bs_call - MARKET_VANILLA_ASK:.4f} | {p_wrong_call*100:.2f}%")


if __name__ == "__main__":
    main()
