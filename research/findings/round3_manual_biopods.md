---
product: ORNAMENTAL_BIO_POD
date: 2026-04-24
status: active
hypothesis: Optimal bids in a two-stage sealed auction with reserve price and global-average threshold
test: Game theory analysis — no data to backtest (one-shot manual challenge)
result: confirmed
---

## Challenge Description (Round 3 Manual)

The Celestial Gardeners' Guild offers Ornamental Bio-Pods in a one-time sealed auction.
Each team submits TWO bids (range: 670–920 XIRECs).

### Bid 1 (Lowest Bid)
- Accepted if it exceeds the Guild's unknown **reserve price**.
- Pure optimization — no game theory component.

### Bid 2 (Highest Bid)
- Also factors in the **global average bid** submitted by all crews.
- Above average → likely trade.
- Below average → probability of trade drops sharply (cubic penalty in P3).

---

## Variables

| Symbol | Meaning |
|--------|---------|
| $p$ | Your bid price |
| $r$ | The seller's reserve price (unknown to you) |
| $L$ | Lower bound of the reserve price distribution |
| $H$ | Upper bound of the reserve price distribution |
| $V$ | Resale value of a Bio-Pod (unknown in P4) |
| $\mu$ | Global average of all teams' Bid 2 |
| $S(p, \mu)$ | Scaling factor applied to Bid 2 profit when $p < \mu$ |

For P4: $L = 670$, $H = 920$, $V = ?$

---

## Math From First Principles

### 1. The Base Profit (Bid 1 — Pure Optimization)

One seller with an unknown reserve price $r$ drawn uniformly from $[L, H]$.
You bid $p$. If $p > r$, they sell. You resell at value $V$.

**Probability they accept your bid:**

$$\Pr(\text{trade}) = \frac{p - L}{H - L}$$

At $p = L$ the trade never happens. At $p = H$ it's guaranteed. Linear in between.

**Profit if the trade happens:**

$$\text{surplus}(p) = V - p$$

**Expected profit:**

$$\Pi(p) = \Pr(\text{trade}) \times \text{surplus}(p) = \frac{p - L}{H - L} \cdot (V - p)$$

This is a downward-opening parabola in $p$. Higher $p$ makes the trade more
likely but shrinks your margin. The peak is where these two forces balance.

**Finding the optimum — take the derivative and set to zero:**

$$\frac{d\Pi}{dp} = \frac{1}{H - L} \left[ (V - p) + (p - L)(-1) \right] = \frac{V + L - 2p}{H - L}$$

$$\frac{d\Pi}{dp} = 0 \implies V + L - 2p = 0 \implies \boxed{p^* = \frac{V + L}{2}}$$

The optimal bid is the **midpoint between the resale value and the bottom of
the reserve range**.

**P3 Part 1 check:** $L = 160$, $V = 320$ → $p^* = \frac{320 + 160}{2} = 240$.
But reserves only go up to $H = 200$. Since $240 > 200$, the trade is guaranteed
at any $p \ge 200$, so the constrained optimum is $p = 200$.
This happens whenever $p^* > H$, i.e. $V > 2H - L$.

### 2. The Game Theory Layer (Bid 2 — Cubic Penalty)

Bid 2 has the same base economics, but adds a **scaling factor** $S$ that depends
on how your bid compares to the global average $\mu$.

**From P3, the scaling factor was:**

$$S(p, \mu) = \min\left(\left(\frac{V - \mu}{V - p}\right)^3,\ 1\right)$$

- If $p \ge \mu$: $S = 1$. Full profit. No penalty.
- If $p < \mu$: $S < 1$. Profit gets crushed.

**Why cubic?** The exponent of 3 creates extreme asymmetry.
Example with $V = 320$, $\mu = 287$:

| Your bid $p$ | Distance from $\mu$ | $S(p, \mu)$ | Profit lost |
|---|---|---|---|
| 290 | +3 | $\min(1.33,\ 1) = 1.0$ | 0% |
| 285 | −2 | $(33/35)^3 = 0.84$ | 16% |
| 275 | −12 | $(33/45)^3 = 0.39$ | 61% |
| 260 | −27 | $(33/60)^3 = 0.17$ | 83% |

**The asymmetry is the key insight.** The cost of being above average is zero
(capped at $S = 1$). The cost of being below is brutal and cubic.

**Full Bid 2 expected profit:**

$$\Pi(p, \mu) = \frac{p - L}{H - L} \cdot (V - p) \cdot S(p, \mu)$$

The optimal bid without game theory is still $p^* = \frac{V + L}{2}$.
The cubic penalty means you want to bid **above** that if others bid near it.

### 3. Nash Equilibrium Reasoning

If everyone bids $p^*$, then $\mu = p^*$, and $S = 1$ for everyone.
This IS a Nash equilibrium — no one gains by deviating.

But it's **unstable**. If others bid above $p^*$ (fearing the cubic penalty),
$\mu$ shifts up, and you MUST follow or get crushed. This creates upward pressure.

In P3, this pressure was **weak in practice**:
- Pure optimum: $p^* = \frac{320 + 250}{2} = 285$
- Actual average: $\mu = 287$ (only +2 above $p^*$)
- The upward spiral didn't materialize — most teams bid near $p^*$

**Practical takeaway:** bid 5–30 points above your estimate of $p^*$.
Costs almost nothing if $\mu \approx p^*$, but saves you if $\mu$ drifts up.

---

## Applying to P4

### The Critical Unknown: $V$

Resale value $V$ is not stated. The optimal Bid 1 is $p^* = \frac{V + 670}{2}$,
so everything depends on $V$.

| Assumed $V$ | Optimal Bid 1 $p^*$ | Reasoning |
|---|---|---|
| 920 | $\frac{920+670}{2} = \mathbf{795}$ | $V$ = top of range (like P3 Part 2) |
| 1000 | $\frac{1000+670}{2} = \mathbf{835}$ | $V$ moderately above range |
| 1100 | $\frac{1100+670}{2} = \mathbf{885}$ | $V$ well above range |
| $\ge 1170$ | $\mathbf{920}$ (capped) | Sweep all sellers (like P3 Part 1) |

### Why $V$ is Probably 920–1050

- If $V \gg 920$: both optimal bids are 920. No real decision. Bad game design.
- If $V = 920$: maximum strategic depth. Midpoint captures 50% of sellers.
- If $V \approx 1000$: sweet spot with meaningful spread between bids.

### Minimax Regret (Bid 1)

Which bid has the smallest worst-case loss across plausible $V$?

$$\Pi(p, V) = \frac{p - 670}{250} \cdot (V - p)$$

Worked example: $p = 835$, $V = 920$:

$$\Pi(835, 920) = \frac{165}{250} \times 85 = 56.1$$

$$\Pi^*(795, 920) = \frac{125}{250} \times 125 = 62.5$$

$$\text{Loss} = 1 - \frac{56.1}{62.5} = -10.2\%$$

| Bid 1 | Loss if $V=920$ | Loss if $V=1000$ | Loss if $V=1100$ | Worst case |
|---|---|---|---|---|
| 795 | 0% | −5.9% | −17.5% | **−17.5%** |
| **835** | −10.2% | **0%** | −5.9% | **−10.2%** |
| 870 | −16.8% | −4.5% | −0.5% | −16.8% |

**835 minimizes worst-case regret** across the plausible range.

### Game Theory (Bid 2)

Expected population average: $\mu \approx 800$–$830$ (most teams assume
$V \approx 920$–$1000$ and bid near $p^*$, with minimal game-theory adjustment,
just like P3 where $\mu$ was only +2 above $p^*$).

The cubic penalty means:
- Cost of being 30 pts above $\mu$: ~0% (capped at $S = 1$)
- Cost of being 10 pts below $\mu$: catastrophic

---

## Recommendation

| | Bid | Reasoning |
|---|---|---|
| **Lowest Bid** | **835** | Minimax-optimal across $V \in [920, 1100]$. Within 10% of optimal for any $V$. |
| **Highest Bid** | **860** | ~30–50 pts above expected $\mu$. Comfortable margin against cubic penalty. |

---

## Risk Summary

- $V = 920$, $\mu = 810$: lose ~10% on Bid 1, full value on Bid 2. Solid.
- $V = 1000$, $\mu = 820$: both bids near-optimal. Best case.
- $V \ge 1170$: should have bid 920/920. But that means no real decision — unlikely.
- $\mu > 860$: Bid 2 falls below average. Main risk. Mitigated by P3 evidence that $\mu$ stays near $p^*$.
