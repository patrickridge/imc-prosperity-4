"""Verify Lev's R4 manual challenge positions via Monte Carlo on the IMC GBM."""

import numpy as np

S0 = 50.0
SIGMA_ANNUAL = 2.51
DRIFT = 0.0
TRADING_DAYS_PER_YEAR = 252
STEPS_PER_DAY = 4

T_2W_DAYS = 10
T_3W_DAYS = 15
T_2W_STEPS = T_2W_DAYS * STEPS_PER_DAY
T_3W_STEPS = T_3W_DAYS * STEPS_PER_DAY

CONTRACT_SIZE = 3000
N_SIMS = 100_000


def simulate_paths(n_sims, n_steps, sigma_annual):
    dt = 1.0 / (TRADING_DAYS_PER_YEAR * STEPS_PER_DAY)
    sqrt_dt = np.sqrt(dt)
    drift_term = -0.5 * sigma_annual ** 2 * dt
    diffusion_term = sigma_annual * sqrt_dt
    increments = np.random.standard_normal((n_sims, n_steps)) * diffusion_term + drift_term
    log_paths = np.cumsum(increments, axis=1)
    paths = S0 * np.exp(log_paths)
    return np.column_stack([np.full(n_sims, S0), paths])


def vanilla_call_payoff(spot, strike):
    return np.maximum(spot - strike, 0)


def vanilla_put_payoff(spot, strike):
    return np.maximum(strike - spot, 0)


def chooser_payoff_3w(s_2w, s_3w, strike):
    payoff = np.where(s_2w > strike,
                      np.maximum(s_3w - strike, 0),
                      np.maximum(strike - s_3w, 0))
    return payoff


def binary_put_payoff(spot, strike, payout=10):
    return np.where(spot < strike, payout, 0)


def knockout_put_payoff(min_path, end_spot, strike, barrier):
    return np.where(min_path < barrier, 0, np.maximum(strike - end_spot, 0))


def evaluate_position(positions, paths_3w):
    s_2w = paths_3w[:, T_2W_STEPS]
    s_3w = paths_3w[:, T_3W_STEPS]
    min_path = paths_3w.min(axis=1)

    pnl = np.zeros(paths_3w.shape[0])

    for instr, qty, price in positions:
        if instr == "AC_50_P_2":
            value = vanilla_put_payoff(s_2w, 50)
        elif instr == "AC_50_C_2":
            value = vanilla_call_payoff(s_2w, 50)
        elif instr == "AC_50_C":
            value = vanilla_call_payoff(s_3w, 50)
        elif instr == "AC_50_P":
            value = vanilla_put_payoff(s_3w, 50)
        elif instr == "AC_50_CO":
            value = chooser_payoff_3w(s_2w, s_3w, 50)
        elif instr == "AC_40_BP":
            value = binary_put_payoff(s_3w, 40, payout=10)
        elif instr == "AC_45_KO":
            value = knockout_put_payoff(min_path, s_3w, 45, 35)
        else:
            raise ValueError(f"Unknown instrument: {instr}")
        pnl += qty * (value - price)

    return pnl * CONTRACT_SIZE


def summarize(name, pnl):
    score_stddev = pnl.std() / np.sqrt(100)
    p_score_loss = float(((pnl.reshape(-1, 100).mean(axis=1)) < 0).mean()) if pnl.size >= 100 else None
    print(f"\n=== {name} ===")
    print(f"Single-path mean: {pnl.mean():,.0f}")
    print(f"Single-path stddev: {pnl.std():,.0f}")
    print(f"100-sim score expected stddev: {score_stddev:,.0f}")
    print(f"P(single-path loss): {(pnl < 0).mean() * 100:.1f}%")
    if p_score_loss is not None:
        print(f"P(100-sim SCORE loss): {p_score_loss * 100:.1f}%   <- IMC's actual score")


def run():
    np.random.seed(42)
    paths = simulate_paths(N_SIMS, T_3W_STEPS, SIGMA_ANNUAL)

    lev_positions = [
        ("AC_50_P_2", 50, 9.75),
        ("AC_50_C_2", 50, 9.75),
        ("AC_50_CO", -50, 22.20),
        ("AC_40_BP", -50, 5.00),
        ("AC_45_KO", 500, 0.175),
    ]
    summarize("Lev's setup (current)", evaluate_position(lev_positions, paths))

    fixed_positions = [
        ("AC_50_P_2", 50, 9.75),
        ("AC_50_C", 50, 12.05),
        ("AC_50_CO", -50, 22.20),
        ("AC_40_BP", -50, 5.00),
        ("AC_45_KO", 500, 0.175),
    ]
    summarize("Fixed (3w call instead of 2w call)", evaluate_position(fixed_positions, paths))

    fixed_no_ko_positions = [
        ("AC_50_P_2", 50, 9.75),
        ("AC_50_C", 50, 12.05),
        ("AC_50_CO", -50, 22.20),
        ("AC_40_BP", -50, 5.00),
    ]
    summarize("Fixed + drop KO put", evaluate_position(fixed_no_ko_positions, paths))

    just_chooser_arb = [
        ("AC_50_P_2", 50, 9.75),
        ("AC_50_C", 50, 12.05),
        ("AC_50_CO", -50, 22.20),
    ]
    summarize("Just chooser arb (3w call replication)", evaluate_position(just_chooser_arb, paths))

    just_binary = [("AC_40_BP", -50, 5.00)]
    summarize("Just binary put short (50 contracts)", evaluate_position(just_binary, paths))


if __name__ == "__main__":
    run()
