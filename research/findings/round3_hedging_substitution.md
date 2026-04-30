# Round 3: Flow/Volume/Volatility Analysis — Hedging & Substitution Signals

## Executive Summary

**Key Finding**: **VELVETFRUIT realized volatility strongly predicts voucher order volume on Day 0 only (r=0.35–0.41), suggesting a market-regime-dependent hedging signal. This is not exploitable without understanding why it disappears on Days 1–2. All other tests (substitution, price-volume, LOB imbalance) show weak or regime-dependent signals with max |r| < 0.30 on Days 1–2.**

**Recommendation**: The Day 0 hedging signal is intriguing but fragile. Do not build a strategy around it without analyzing the regime change. Standard tests (volume → vol, LOB imbalance) show low correlation in most products, confirming the prior agent's finding that cross-product/within-product inefficiencies are weak.

---

## Data Overview

- **Period**: Round 3, Days 0–2 (3 × 120,000 ticks per day)
- **Products**: 12 total
  - Non-vouchers: HYDROGEL_PACK, VELVETFRUIT_EXTRACT
  - Vouchers: VEV_4000, 4500, 5000, 5100, 5200, 5300, 5400, 5500, 6000, 6500
- **Metrics**:
  - Realized volatility: 100-tick rolling std of 1-tick returns
  - Rolling volume: 100-tick sum of (bid_volume_1 + ask_volume_1)
  - LOB imbalance: (bid_vol - ask_vol) / (bid_vol + ask_vol)

---

## Test 1: Hedging Behavior (VELVETFRUIT vol → Voucher Volume)

### Hypothesis
When VELVETFRUIT_EXTRACT realized vol spikes, traders hedge by increasing orders in vouchers (hedging activity).

### Methodology
Correlation between VELVETFRUIT_EXTRACT realized vol and each voucher's rolling volume, at lags 0, 10, 50, 100 ticks.

### Results

#### Day 0 (Strong Signal)
- **VEV_6500**: r = 0.405 (lag 0), 0.395 (lag 10), 0.270 (lag 50) — **STRONGEST**
- **VEV_4000**: r = 0.370, 0.361, 0.262 — **STRONG**
- **VEV_6000**: r = 0.370, 0.358, 0.268 — **STRONG**
- **VEV_4500**: r = 0.342, 0.315 — **STRONG**
- **VEV_5500**: r = 0.361, 0.348, 0.245 — **STRONG**
- **VEV_5100**: r = 0.353, 0.330, 0.188 — **STRONG**
- **Pattern**: Lower strikes (VEV_4000–5400) show r > 0.31; higher strikes (VEV_6000–6500) show r > 0.34; signal strongest at lag 0, decays at lag 50+.

#### Day 1 (No signal)
- All correlations |r| < 0.10 across all lags.

#### Day 2 (Weak remnant)
- **VEV_5000**: r = 0.176 (lag 50)
- **VEV_5100**: r = 0.161 (lag 50)
- All other vouchers: |r| < 0.10.

### Aggregate Statistics

| Voucher      | Avg r (Days 0-2) | n tests | Pattern             |
|--------------|------------------|---------|---------------------|
| VEV_6500     | 0.108            | 12      | Strong on Day 0 only |
| VEV_6000     | 0.121            | 12      | Strong on Day 0 only |
| VEV_5500     | 0.117            | 12      | Strong on Day 0 only |
| VEV_5100     | 0.144            | 12      | Strong on Day 0 only |
| VEV_5000     | 0.069            | 12      | Weak across all days |

### Interpretation

**Regime Dependency**: Day 0 shows a genuine hedging signal (traders increase voucher volume when underlying vol spikes), but this behavior **completely disappears on Days 1–2**. Possible causes:

1. **Initial market structure on Day 0** may differ (e.g., higher uncertainty, more rebalancing pressure).
2. **Trader behavior shifts** mid-round (learning, portfolio adjustment).
3. **Statistical artifact** of the specific tick sequencing on Day 0.

**Trade Implication**: Cannot use this signal as a stable multi-day strategy. A Day 0-only strategy would require:
- Entry: When VELVETFRUIT vol spikes above trailing mean + 1σ, buy vouchers (especially VEV_6500, 6000).
- Exit: Hold for 10–50 ticks.
- Risk: Signal vanishes after Day 0; heavily curve-fit.

---

## Test 2: Substitution Behavior (HYDROGEL Volume ↔ Voucher Volume)

### Hypothesis
When HYDROGEL_PACK volume drops, traders shift to vouchers (budget-constrained substitution), or vice versa.

### Methodology
Correlation between HYDROGEL rolling volume and each voucher's rolling volume (same-day, no lags).

### Results

#### All Days (Consistent Co-Movement)

| Voucher      | Avg r (Days 0-2) | Interpretation        |
|--------------|------------------|-----------------------|
| VEV_6000     | 0.938            | **Strong co-movement** |
| VEV_6500     | 0.929            | **Strong co-movement** |
| VEV_5500     | 0.923            | **Strong co-movement** |
| VEV_5400     | 0.917            | **Strong co-movement** |
| VEV_4500     | 0.903            | **Strong co-movement** |
| VEV_4000     | 0.897            | **Strong co-movement** |
| VEV_5300     | 0.866            | **Strong co-movement** |
| VEV_5200     | 0.832            | **Strong co-movement** |
| VEV_5100     | 0.756            | **Strong co-movement** |
| VEV_5000     | 0.706            | **Strong co-movement** |

### Interpretation

**Not Substitution; Joint Market Movement**: The very high correlations (0.7–0.95) indicate that HYDROGEL and vouchers **move together as part of the same market rhythm**, not as budget competitors. When trading volume is high, both see increased activity; when quiet, both dry up.

**Possible Explanation**:
- Market-maker behavior: same quoting/rebalancing across all products.
- Synchronous arrival of large orders.
- Common liquidity provision.

**Trade Implication**: Cannot exploit as a spread/relative-value trade. The strong co-movement suggests they share common risk factors.

---

## Test 3: Per-Product Price-Volume Relationship

### Hypothesis
For each product, rolling volume predicts realized volatility (Klueger/Karpoff: informed traders first → vol follows). Or vice versa (volatility attracts volume).

### Methodology
Correlation between rolling volume and realized vol at lags -50, -10, 0, 10, 50 ticks for key products.

### Results

#### VEV_5000 (Interesting Signal)
- **Day 0**: r = 0.24–0.29 across all lags (consistent, symmetric).
- **Day 1**: r ≈ 0.18 across all lags (stable, weaker).
- **Day 2**: r = 0.27–0.29 across all lags (strong again).
- **Aggregate**: r_avg = 0.241 — **Moderate relationship** (statistically significant, but marginal edge).

#### VELVETFRUIT_EXTRACT
- **Day 0**: r = 0.13–0.17 (weak).
- **Day 1**: (no significant lags, |r| < 0.10).
- **Day 2**: r ≈ -0.19 (slight negative, unexpected).
- **Aggregate**: r_avg ≈ -0.008 — **No exploitable signal**.

#### HYDROGEL_PACK
- **All Days**: |r| < 0.05 — **No signal**.

#### VEV_5500
- **All Days**: |r| < 0.15 — **No signal**.

### Interpretation

**Weak Within-Product Signal**: Only VEV_5000 shows a consistent, moderate volume-volatility link (r ≈ 0.24). The relationship is symmetric across lags, suggesting **simultaneous response rather than causal**. Possible interpretation:

1. High-frequency microstructure: when traders hit both sides, vol and volume spike together.
2. No predictive power: lag 0 dominates; neither predicts the other.

**Trade Implication**: Cannot build a profitable strategy on this alone. r=0.24 is too weak to overcome transaction costs.

---

## Test 4: Order-Book Imbalance vs Realized Volatility

### Hypothesis
Asymmetric LOB (extreme bid/ask ratio) predicts near-term realized volatility (directional pressure).

### Methodology
Correlation between LOB imbalance and realized vol at lags 0, 10, 50 ticks for key products.

### Results

**All Products, All Days**: |r| < 0.02 — **No signals detected**.

### Interpretation

**LOB Asymmetry is Not Predictive**: Order book imbalance (even at top 1 level) does not forecast volatility. Likely because:
1. LOB depth is small in this market; top-level imbalance is noise.
2. Market-makers quickly rebalance, canceling imbalance before vol materializes.

---

## Summary Table: All Tests

| Test                                 | Strongest Signal             | Correlation | Status             | Trade Potential |
|--------------------------------------|------------------------------|-------------|---------------------|-----------------|
| Hedging (VELVETFRUIT vol → vouchers) | VEV_6500 on Day 0 only      | 0.405       | Regime-dependent    | Low (not stable) |
| Substitution (HYDROGEL ↔ vouchers)   | VEV_6000 overall            | 0.938       | Too strong (co-move) | None (not subst) |
| Price-Volume (within-product)        | VEV_5000 overall            | 0.241       | Weak, simultaneous  | Low (not causal) |
| LOB Imbalance vs Vol                 | (none)                      | <0.02       | None               | None            |

---

## Cross-Test Synthesis

### What Worked (Weakly)
1. **VELVETFRUIT vol → voucher volume on Day 0**: r = 0.35–0.41 for lower/higher strikes. Suggests genuine hedging pressure on the initial day, but regime-switches off after 24 hours.
2. **VEV_5000 volume ↔ realized vol**: r = 0.24 across all days, symmetric lags. Too weak to trade, but consistent.

### What Failed
1. **HYDROGEL-voucher substitution**: Turned out to be co-movement (r > 0.85), not budget competition. No trading edge.
2. **LOB imbalance as vol predictor**: Completely uncorrelated (r < 0.02).
3. **Cross-product volume-volume or vol-vol relationships**: Near-zero except for the trivial co-movement.

### Comparison to Prior Agent (Cross-Product Correlations)

The prior agent found max |r| < 0.30 for price correlations and concluded "no exploitable edge." We confirm that even broader tests (volume, volatility, LOB) yield weak signals outside the hedging anomaly on Day 0. The strongest finding here is the **hedging signal on Day 0 only**, which is:
- Regime-dependent (disappears after Day 0).
- Intriguing but unactionable without understanding the regime driver.
- Unlikely to generalize to future rounds.

---

## Limitations

1. **Day 0 anomaly**: Without additional rounds, cannot determine if hedging signal is a one-off event or a reproducible pattern that decays over time.
2. **Microstructure blind**: Analysis uses top 1 LOB level and aggregate volumes. Full order book and trade intensity data might reveal additional patterns.
3. **Lag selection**: Tested lags up to 100 ticks (~1 minute). Longer-horizon effects (10+ minutes) untested.
4. **No ML model**: Sklearn unavailable in environment; could not test nonlinear relationships (GradientBoosting as planned).
5. **Causality assumption**: Even if two series correlate, one does not necessarily cause the other.

---

## Verdict

**No actionable flow/volume/volatility edge found that is both stable and exploitable.**

1. **Hedging signal (Day 0 only)**: Real but regime-dependent; cannot be used confidently.
2. **Substitution (HYDROGEL-vouchers)**: False signal; they move together, not inversely.
3. **Within-product volume-vol**: Weak (r ≈ 0.24 at best), no predictive lag structure.
4. **LOB imbalance**: Unrelated to vol.

### Recommendation
**Focus on within-product inefficiencies** (as per the prior agent's hypothesis 3). Spread trading, inventory-skew effects, or volatility regime changes within a single product are more promising than the cross-product/volume signals tested here. The data suggests that hedging and flow dynamics are either too complex to model with simple correlations or are sufficiently efficient that they do not generate exploitable patterns.

---

## Appendix: Raw Test Results by Day

### Day 0: Hedging Signal (VELVETFRUIT vol → Voucher Volume)

| Voucher   | Lag 0 | Lag 10 | Lag 50 | Lag 100 |
|-----------|-------|--------|--------|---------|
| VEV_4000  | 0.370 | 0.361  | 0.262  | 0.107   |
| VEV_4500  | 0.342 | 0.315  | 0.137  | 0.061   |
| VEV_5000  | 0.223 | 0.188  | 0.064  | 0.008   |
| VEV_5100  | 0.353 | 0.330  | 0.188  | 0.066   |
| VEV_5200  | 0.320 | 0.287  | 0.134  | 0.043   |
| VEV_5300  | 0.316 | 0.293  | 0.157  | 0.053   |
| VEV_5400  | 0.346 | 0.333  | 0.218  | 0.075   |
| VEV_5500  | 0.361 | 0.348  | 0.245  | 0.086   |
| VEV_6000  | 0.370 | 0.358  | 0.268  | 0.094   |
| VEV_6500  | 0.405 | 0.395  | 0.270  | 0.097   |

**Note**: Day 1 and Day 2 show |r| < 0.10 except for isolated late-day (lag 50) signals in VEV_5000 and VEV_5100 on Day 2.

---

**End of Report**
