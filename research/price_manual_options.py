"""
Monte Carlo pricer for Round 4 manual options on AETHER_CRYSTAL.
GBM simulation with exact Prosperity parameters.
"""

import numpy as np
from scipy.stats import norm

# ── GBM Parameters ──────────────────────────────────────────────
S0 = 50.0
DRIFT = 0.0
SIGMA = 2.51          # 251% annualized vol
STEPS_PER_DAY = 4
TRADING_DAYS_PER_YEAR = 252
STEPS_PER_YEAR = STEPS_PER_DAY * TRADING_DAYS_PER_YEAR  # 1008
DT = 1.0 / STEPS_PER_YEAR

N_PATHS = 1_000_000
SEED = 42
CONTRACT_SIZE = 3000

# ── Time horizons (in steps) ───────────────────────────────────
T_2WEEKS = 40   # 10 trading days * 4 steps
T_3WEEKS = 60   # 15 trading days * 4 steps

# ── Market prices ──────────────────────────────────────────────
MARKET = {
    "AETHER_CRYSTAL": {"bid": 49.975, "ask": 50.025, "volume": 200},
    "AC_50_P":        {"bid": 12.00,  "ask": 12.05,  "volume": 50},
    "AC_50_C":        {"bid": 12.00,  "ask": 12.05,  "volume": 50},
    "AC_35_P":        {"bid": 4.33,   "ask": 4.35,   "volume": 50},
    "AC_40_P":        {"bid": 6.50,   "ask": 6.55,   "volume": 50},
    "AC_45_P":        {"bid": 9.05,   "ask": 9.10,   "volume": 50},
    "AC_60_C":        {"bid": 8.80,   "ask": 8.85,   "volume": 50},
    "AC_50_P_2":      {"bid": 9.70,   "ask": 9.75,   "volume": 50},
    "AC_50_C_2":      {"bid": 9.70,   "ask": 9.75,   "volume": 50},
    "AC_50_CO":       {"bid": 22.20,  "ask": 22.30,  "volume": 50},
    "AC_40_BP":       {"bid": 5.00,   "ask": 5.10,   "volume": 50},
    "AC_45_KO":       {"bid": 0.15,   "ask": 0.175,  "volume": 500},
}


def simulate_paths(n_paths, n_steps, seed=SEED):
    """Simulate GBM paths. Returns array of shape (n_paths, n_steps+1) including S0."""
    rng = np.random.default_rng(seed)
    Z = rng.standard_normal((n_paths, n_steps))

    log_drift_per_step = (DRIFT - 0.5 * SIGMA**2) * DT
    diffusion_scale = SIGMA * np.sqrt(DT)

    log_increments = log_drift_per_step + diffusion_scale * Z
    log_prices = np.concatenate(
        [np.zeros((n_paths, 1)), np.cumsum(log_increments, axis=1)],
        axis=1,
    )
    return S0 * np.exp(log_prices)


def mc_stats(payoffs):
    """Return (mean, standard_error) for a vector of payoffs."""
    mean = np.mean(payoffs)
    se = np.std(payoffs, ddof=1) / np.sqrt(len(payoffs))
    return mean, se


def price_all(paths_60, paths_40_for_chooser=None):
    """Price every contract. paths_60 has shape (N, 61)."""
    results = {}

    S_60 = paths_60[:, -1]          # terminal price at step 60
    S_40 = paths_60[:, 40]          # price at step 40

    # ── Underlying ──────────────────────────────────────────────
    results["AETHER_CRYSTAL"] = mc_stats(S_60)  # trivially S0 under risk-neutral

    # ── Vanilla options at T=60 ─────────────────────────────────
    results["AC_50_P"] = mc_stats(np.maximum(50 - S_60, 0))
    results["AC_50_C"] = mc_stats(np.maximum(S_60 - 50, 0))
    results["AC_35_P"] = mc_stats(np.maximum(35 - S_60, 0))
    results["AC_40_P"] = mc_stats(np.maximum(40 - S_60, 0))
    results["AC_45_P"] = mc_stats(np.maximum(45 - S_60, 0))
    results["AC_60_C"] = mc_stats(np.maximum(S_60 - 60, 0))

    # ── Vanilla options at T=40 ─────────────────────────────────
    results["AC_50_P_2"] = mc_stats(np.maximum(50 - S_40, 0))
    results["AC_50_C_2"] = mc_stats(np.maximum(S_40 - 50, 0))

    # ── Chooser option: choose at T=40, expire at T=60 ─────────
    # At step 40: if S>K => call, if S<K => put, if S==K => worthless
    call_payoff = np.maximum(S_60 - 50, 0)
    put_payoff = np.maximum(50 - S_60, 0)

    chose_call = S_40 > 50
    chose_put = S_40 < 50
    # S_40 == 50 => payoff = 0 (neither ITM)

    chooser_payoff = np.where(chose_call, call_payoff,
                              np.where(chose_put, put_payoff, 0.0))
    results["AC_50_CO"] = mc_stats(chooser_payoff)

    # ── Binary put: pays 10 if S_60 < 40 ───────────────────────
    binary_payoff = np.where(S_60 < 40, 10.0, 0.0)
    results["AC_40_BP"] = mc_stats(binary_payoff)

    # ── Knock-out put: K=45, barrier=35, T=60 ──────────────────
    # Payoff = max(45 - S_60, 0) if path never goes BELOW 35
    # "below" means strictly < 35
    path_min = np.min(paths_60[:, 1:], axis=1)  # min over steps 1..60
    barrier_survived = path_min >= 35  # NOT breached (never below 35)
    ko_payoff = np.where(barrier_survived, np.maximum(45 - S_60, 0), 0.0)
    results["AC_45_KO"] = mc_stats(ko_payoff)

    return results


def classify_signal(mc_val, bid, ask):
    """Classify as BUY, SELL, or WITHIN SPREAD."""
    if mc_val > ask:
        return "BUY"
    elif mc_val < bid:
        return "SELL"
    else:
        return "WITHIN SPREAD"


def main():
    print("=" * 80)
    print("Monte Carlo Option Pricer — AETHER_CRYSTAL Round 4 Manual")
    print(f"Paths: {N_PATHS:,}  |  S0: {S0}  |  sigma: {SIGMA}  |  dt: 1/{STEPS_PER_YEAR}")
    print("=" * 80)

    print("\nSimulating 1M paths (60 steps)...")
    paths_60 = simulate_paths(N_PATHS, T_3WEEKS, seed=SEED)
    print(f"  Path shape: {paths_60.shape}")
    print(f"  Terminal mean: {paths_60[:, -1].mean():.4f}  (expect ~50)")
    print(f"  Terminal std:  {paths_60[:, -1].std():.4f}")

    results = price_all(paths_60)

    # ── Per-contract table ──────────────────────────────────────
    print("\n" + "=" * 80)
    print(f"{'Contract':<18} {'MC Value':>10} {'SE':>8} {'Bid':>8} {'Ask':>8} "
          f"{'Signal':>14} {'Edge/ct':>10} {'Scaled':>12}")
    print("-" * 80)

    portfolio = []

    for name in MARKET:
        mc_val, se = results[name]
        bid = MARKET[name]["bid"]
        ask = MARKET[name]["ask"]
        vol = MARKET[name]["volume"]
        signal = classify_signal(mc_val, bid, ask)

        if signal == "BUY":
            edge = mc_val - ask
            action = "BUY"
        elif signal == "SELL":
            edge = bid - mc_val
            action = "SELL"
        else:
            edge = 0.0
            action = "NONE"

        scaled = edge * vol * CONTRACT_SIZE

        print(f"{name:<18} {mc_val:>10.4f} {se:>8.4f} {bid:>8.3f} {ask:>8.3f} "
              f"{signal:>14} {edge:>+10.4f} {scaled:>+12.1f}")

        if action != "NONE":
            portfolio.append((name, action, edge, vol, scaled))

    # ── Sorted edge summary ─────────────────────────────────────
    print("\n" + "=" * 80)
    print("EDGE SUMMARY (sorted by |scaled profit|)")
    print("-" * 80)

    portfolio.sort(key=lambda x: abs(x[4]), reverse=True)

    total_pnl = 0.0
    for name, action, edge, vol, scaled in portfolio:
        price_str = (f"ask={MARKET[name]['ask']:.3f}" if action == "BUY"
                     else f"bid={MARKET[name]['bid']:.3f}")
        print(f"  {action:>4} {vol:>4}x {name:<18} @ {price_str:<14} "
              f"edge={edge:+.4f}  scaled={scaled:+,.0f}")
        total_pnl += scaled

    print("-" * 80)
    print(f"  TOTAL EXPECTED PnL: {total_pnl:+,.0f}")
    print("=" * 80)

    # ── Black-Scholes cross-check for vanilla ATM ───────────────
    print("\n── Black-Scholes Cross-Check (vanilla options) ──")
    for K, T_steps, label in [
        (50, T_3WEEKS, "AC_50_C/P (3wk)"),
        (50, T_2WEEKS, "AC_50_C_2/P_2 (2wk)"),
        (35, T_3WEEKS, "AC_35_P (3wk)"),
        (40, T_3WEEKS, "AC_40_P (3wk)"),
        (45, T_3WEEKS, "AC_45_P (3wk)"),
        (60, T_3WEEKS, "AC_60_C (3wk)"),
    ]:
        TTE = T_steps * DT
        d1 = (np.log(S0 / K) + 0.5 * SIGMA**2 * TTE) / (SIGMA * np.sqrt(TTE))
        d2 = d1 - SIGMA * np.sqrt(TTE)
        bs_call = S0 * norm.cdf(d1) - K * norm.cdf(d2)
        bs_put = K * norm.cdf(-d2) - S0 * norm.cdf(-d1)
        print(f"  {label:<25} BS_call={bs_call:.4f}  BS_put={bs_put:.4f}")


if __name__ == "__main__":
    main()
