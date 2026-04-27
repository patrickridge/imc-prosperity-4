---
product: AETHER_CRYSTAL (Round 4 Manual)
date: 2026-04-26
status: active
hypothesis: Several exotic options are mispriced relative to a 251% vol GBM simulation
test: Monte Carlo (2M paths, two seeds) + Black-Scholes cross-check
result: confirmed
---

## Setup

The market gives us 12 contracts on AETHER_CRYSTAL (spot = 50).
The underlying follows GBM with **zero drift** and **251% annualized vol**,
simulated on a discrete grid of 4 steps/day over 252 trading days/year.
PnL = average payoff across 100 sims, multiplied by contract size 3,000.

We priced every contract via Monte Carlo (2M paths, seeds 42 and 123)
and cross-checked vanillas against Black-Scholes closed-form. All MC values
fell within 1–2 standard errors of BS. Scripts are in `research/`.

## Where the edges are

### 1. AC_45_KO — Knock-Out Put (BUY at 0.175, fair ≈ 0.206)

**What it is.** A put with strike 45 that dies if the price ever drops below 35.

**Why it's cheap.** The market underprices this because intuition says
"high vol = barrier gets hit easily." That's half-true: 61% of paths do
breach the barrier. But we only check at 60 discrete steps, not continuously.
Fewer checkpoints = fewer chances to knock out = option is worth more than
a continuous-barrier model would suggest.

**Edge per contract:** +0.031. At 500 volume × 3,000 size = **~46k profit.**

**Robustness:** BUY signal holds at 240%, 251%, and 260% vol.
This is our safest trade.

### 2. AC_50_CO — Chooser Option (SELL at 22.20, fair ≈ 21.90)

**What it is.** At T+14 days, it becomes whichever of a call or put is
in the money, then expires as a standard option at T+21.

**Why it's expensive.** People may confuse this with a straddle (which
costs 24.05). A straddle pays on *both* sides. The chooser only pays on
the side that was ITM at the choice point — if the price reverses in the
final week, you're stuck with the wrong leg. That gap is worth ~2.15.
The market prices the chooser at 22.20, but fair is 21.90.

Closed-form confirms: Chooser = Call(K,T) + Put(K,t_choice) = 12.03 + 9.87 = 21.90.

**Edge per contract:** +0.30. At 50 volume × 3,000 size = **~45k profit.**

**Robustness:** This is the most vol-sensitive trade. At 256% vol the edge
disappears; at 260% it flips. The wiki says "fixed 251%", so we trust it,
but this is our riskiest position.

### 3. AC_40_BP — Binary Put (SELL at 5.00, fair ≈ 4.77)

**What it is.** Pays exactly 10 if the price ends below 40. Otherwise zero.

**Why it's expensive.** Fair value = 10 × P(S < 40 at expiry).
With 251% vol over 3 weeks, P(S < 40) ≈ 47.7%, so fair = 4.77.
The market bids 5.00 — they're overestimating the probability of landing
below 40 by about 2.3 percentage points.

**Edge per contract:** +0.23. At 50 volume × 3,000 size = **~35k profit.**

**Robustness:** 65 standard errors from the flip threshold. Very safe.

### 4���5. AC_50_P_2 and AC_50_C_2 — 2-Week Vanillas (BUY both at 9.75, fair ≈ 9.87)

**What they are.** Standard ATM put and call, strike 50, 2-week expiry.

**Why they're cheap.** With r = 0 and S = K = 50, put-call parity forces
both to be worth the same. BS gives 9.87 for each. Market asks 9.75 —
a clean 0.12 underprice.

**Edge per contract:** +0.12 each. At 50 vol × 3,000 size = **~18k each, ~36k total.**

**Robustness:** BS-confirmed, parity holds to 6 decimal places.

## Contracts with no edge

AC_50_P, AC_50_C, AC_45_P, AC_60_C, AC_35_P, AC_40_P — all priced
within the bid-ask spread. Skip them.

## Recommended Portfolio

| Contract | Side | Volume | Expected Profit |
|----------|------|--------|-----------------|
| AC_45_KO | BUY | 500 | ~46k |
| AC_50_CO | SELL | 50 | ~45k |
| AC_40_BP | SELL | 50 | ~35k |
| AC_50_C_2 | BUY | 50 | ~18k |
| AC_50_P_2 | BUY | 50 | ~18k |
| **Total** | | | **~162k** |

## When to retire

- If the wiki changes the stated vol from 251%
- If the chooser interpretation is clarified differently (max-value vs ITM check)
- If contract prices update between submissions (re-run the pricer)
