"""
Monte Carlo verification of knock-out put option pricing.

Parameters (from P4 wiki):
  S0=50, sigma=2.51, drift=0, r=0
  dt=1/1008, Strike=45, Barrier=35, T=60 steps
  Knock-out if S_t < 35 at ANY step t=1..60
  Payoff = max(45 - S_60, 0) if not knocked out
"""

import numpy as np
import time

# ── Parameters ──────────────────────────────────────────────────────
S0 = 50.0
STRIKE = 45.0
BARRIER = 35.0
T_STEPS = 60
DT = 1.0 / 1008.0
DRIFT = 0.0
R = 0.0
SIGMA = 2.51  # 251% annualized


def simulate_paths(n_paths, sigma, seed):
    """Simulate GBM paths and return terminal prices + knocked-out mask."""
    rng = np.random.default_rng(seed)
    z = rng.standard_normal((n_paths, T_STEPS))

    log_s = np.full(n_paths, np.log(S0))
    knocked_out = np.zeros(n_paths, dtype=bool)

    for t in range(T_STEPS):
        log_s += (DRIFT - 0.5 * sigma**2) * DT + sigma * np.sqrt(DT) * z[:, t]
        s_t = np.exp(log_s)
        # Strictly less than barrier (not <=)
        knocked_out |= s_t < BARRIER

    terminal_price = np.exp(log_s)
    return terminal_price, knocked_out


def compute_payoffs(terminal_price, knocked_out):
    """Compute option payoffs."""
    raw_payoff = np.maximum(STRIKE - terminal_price, 0.0)
    payoff = np.where(knocked_out, 0.0, raw_payoff)
    return payoff, raw_payoff


def report_run(label, n_paths, seed, sigma=SIGMA):
    """Run MC and print results."""
    start = time.time()
    terminal_price, knocked_out = simulate_paths(n_paths, sigma, seed)
    payoff, raw_payoff = compute_payoffs(terminal_price, knocked_out)
    elapsed = time.time() - start

    fair_value = payoff.mean()
    std_err = payoff.std(ddof=1) / np.sqrt(n_paths)
    ci_lo = fair_value - 1.96 * std_err
    ci_hi = fair_value + 1.96 * std_err

    p_knocked_out = knocked_out.mean()
    alive = ~knocked_out
    itm_and_alive = alive & (raw_payoff > 0)
    p_itm_alive = itm_and_alive.mean()

    if itm_and_alive.sum() > 0:
        avg_payoff_when_pays = payoff[itm_and_alive].mean()
    else:
        avg_payoff_when_pays = 0.0

    print(f"\n{'=' * 60}")
    print(f"  {label}")
    print(f"  sigma={sigma:.3f}, paths={n_paths:,}, seed={seed}, {elapsed:.1f}s")
    print(f"{'=' * 60}")
    print(f"  Fair value:           {fair_value:.6f}")
    print(f"  Std error:            {std_err:.6f}")
    print(f"  95% CI:               [{ci_lo:.6f}, {ci_hi:.6f}]")
    print(f"  P(knocked out):       {p_knocked_out:.4%}")
    print(f"  P(ITM & alive):       {p_itm_alive:.4%}")
    print(f"  E[payoff | pays]:     {avg_payoff_when_pays:.4f}")
    print()

    return fair_value


# ── Main runs (2M paths each) ──────────────────────────────────────
print("=" * 60)
print("  KNOCK-OUT PUT OPTION — MONTE CARLO VERIFICATION")
print("  S0=50, K=45, Barrier=35, T=60 steps, dt=1/1008")
print("  sigma=2.51 (251%), drift=0, r=0")
print("  Knock-out: S_t < 35 (strictly less than)")
print("=" * 60)

v1 = report_run("Run 1 (seed=42)", 2_000_000, seed=42)
v2 = report_run("Run 2 (seed=123)", 2_000_000, seed=123)

print(f"  Average of two runs:  {(v1 + v2) / 2:.6f}")
print(f"  Market ask:           0.175")
print(f"  Claimed MC value:     ~0.206")
print()

# ── Sensitivity: vol ────────────────────────────────────────────────
print("=" * 60)
print("  VOLATILITY SENSITIVITY (500k paths, seed=42)")
print("=" * 60)

for vol in [2.40, 2.51, 2.60]:
    report_run(f"Vol = {vol:.2f} ({vol*100:.0f}%)", 500_000, seed=42, sigma=vol)

# ── Barrier edge case: strictly < vs <= ─────────────────────────────
print("=" * 60)
print("  BARRIER EDGE CASE: < 35 vs <= 35")
print("=" * 60)

n_edge = 2_000_000
seed_edge = 42
terminal_price, ko_strict = simulate_paths(n_edge, SIGMA, seed_edge)

# Re-simulate to check <= barrier
rng = np.random.default_rng(seed_edge)
z = rng.standard_normal((n_edge, T_STEPS))
log_s = np.full(n_edge, np.log(S0))
ko_inclusive = np.zeros(n_edge, dtype=bool)
touched_exact = np.zeros(n_edge, dtype=bool)

for t in range(T_STEPS):
    log_s += (DRIFT - 0.5 * SIGMA**2) * DT + SIGMA * np.sqrt(DT) * z[:, t]
    s_t = np.exp(log_s)
    ko_inclusive |= s_t <= BARRIER
    touched_exact |= (s_t == BARRIER)

payoff_strict, _ = compute_payoffs(terminal_price, ko_strict)
payoff_inclusive, _ = compute_payoffs(np.exp(log_s), ko_inclusive)

print(f"  P(knocked out, strict < 35):    {ko_strict.mean():.6%}")
print(f"  P(knocked out, inclusive <= 35): {ko_inclusive.mean():.6%}")
print(f"  Paths touching exactly 35.0:    {touched_exact.sum()} / {n_edge:,}")
print(f"  Fair value (strict < ):          {payoff_strict.mean():.6f}")
print(f"  Fair value (inclusive <=):        {payoff_inclusive.mean():.6f}")
print(f"  Difference:                      {payoff_strict.mean() - payoff_inclusive.mean():.6f}")
print()

# ── Final verdict ───────────────────────────────────────────────────
avg = (v1 + v2) / 2
print("=" * 60)
print("  VERDICT")
print("=" * 60)
if avg > 0.175:
    print(f"  MC fair value ({avg:.4f}) > market ask (0.175) => BUY signal")
else:
    print(f"  MC fair value ({avg:.4f}) <= market ask (0.175) => NO BUY")
print(f"  Edge = {avg - 0.175:.4f} ({(avg - 0.175) / 0.175 * 100:.1f}% of ask)")
print()
