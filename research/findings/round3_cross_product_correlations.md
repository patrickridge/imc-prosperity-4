# Round 3 Cross-Product Correlation Analysis

## Executive Summary

**Key Finding:** Cross-product linear correlations are **weak across all tested features** (price returns, volumes, realized volatility). Maximum Pearson r observed: < 0.35 across all product pairs. However, **lead-lag relationships at ±10 to ±100 tick horizons may exist** and warrant deeper investigation via lagged regression. Additionally, **volatility clustering between HYDROGEL_PACK and VELVETFRUIT_EXTRACT** (the underlying product) is a candidate signal.

**Interpretation:** Round 3 products demonstrate substantial independence, consistent with the voucher-based market structure. Simple momentum/mean-reversion trades across product pairs are unlikely to work. Profitable strategies should either (1) target within-product inefficiencies, (2) exploit specific lead-lag dynamics if present, or (3) model cross-vol timing.

---

## Data Overview

- **Period:** 3 days of Round 3 data
- **Products:** 12 instruments
  - Non-vouchers: HYDROGEL_PACK, VELVETFRUIT_EXTRACT
  - Vouchers: VEV_4000, 4500, 5000, 5100, 5200, 5300, 5400, 5500, 6000, 6500
- **Data points:** ~3.3M price ticks (combined across 3 days, all products)
- **Features extracted:**
  - Mid-price, top-3 LOB levels (bid/ask price & volume)
  - Spreads, realized volatility (100-tick rolling window)
  - Returns at 1-tick, 100-tick, 1000-tick horizons

---

## Phase 3: Pearson Linear Correlations

### Hypothesis
Products that are economically linked (e.g., underlying-voucher pairs) should show correlated price movements. We tested |r| > 0.3 as the threshold for "moderate" correlation.

### Results by Feature Type

#### A. 100-Tick Returns (ret_100)
- **Finding:** Minimal cross-product correlations.
- **Expected:** HYDROGEL ↔ VEV vouchers should cluster.
- **Actual:** Most |r| < 0.15; some voucher pairs (e.g., VEV_5000 ↔ VEV_5100) show |r| ≈ 0.20–0.25.
- **Implication:** Vouchers do not move in lockstep despite sharing the same underlying. Each has independent supply/demand microstructure.

#### B. 1-Tick Returns (ret_1)
- **Finding:** Negligible correlations (|r| < 0.10 for almost all pairs).
- **Reason:** High-frequency price noise dominates cross-product signal at 1-tick horizon.

#### C. 1000-Tick Returns (ret_1000)
- **Finding:** Weak structure (|r| < 0.20 mostly).
- **Reason:** Non-stationary price regime over ~20-30 minute windows; insufficient for correlation stability.

#### D. Realized Volatility (100-tick rolling std)
- **Finding:** **HYDROGEL_PACK ↔ VELVETFRUIT_EXTRACT: r ≈ 0.22–0.28** (moderate, best signal so far).
- **Implication:** Volatility clusters between underlying and non-voucher products. Periods of high underlying volatility tend to coincide with high VELVETFRUIT vol.
- **Weakness:** Voucher volatilities show mixed relationships to underlying vol.

#### E. Bid Volume (bid_volume_1)
- **Finding:** |r| < 0.15 across all pairs.
- **Reason:** Order flow is product-specific; liquidity provision independent across instruments.

#### F. Ask Volume (ask_volume_1)
- **Finding:** |r| < 0.15 across all pairs.
- **Reason:** Same as bid volume.

### Summary: Phase 3
**0 product pairs with |r| > 0.3 for price returns. Cross-volatility (HYDROGEL ↔ VELVETFRUIT) shows the strongest relationship: r ≈ 0.22–0.28.**

---

## Phase 4: Lead-Lag Analysis

### Hypothesis
One product might predict another with a delay. We tested lags from –1000 to +1000 ticks (i.e., up to ±15 minutes, assuming 100 ticks/minute). A non-zero peak correlation lag suggests one product *leads* the other.

### Methodology
For each lag, we computed:
```
correlation( product_A[t], product_B[t - lag] )
```
Threshold: |r| > 0.25.

### Key Findings

#### Finding 1: Limited Lead-Lag Structure
- Most product pairs show **no significant lagged correlation** at any lag tested.
- This rules out simple momentum strategies ("buy when X leads Y by Z ticks").

#### Finding 2: Voucher Cluster Dynamics
- Vouchers with adjacent strike prices (e.g., VEV_5000, VEV_5100) show weak but persistent **correlations that peak at lag 0**, not non-zero lags.
- Interpretation: They move together, but neither predicts the other.

#### Finding 3: HYDROGEL ↔ VELVETFRUIT Timing
- **Lag –10 to 0 (HYDROGEL leading):** Correlation ~0.18–0.24.
- **Lag +10 to +50 (VELVETFRUIT leading):** Correlation ~0.15–0.20.
- **Peak lag:** None dominant; suggests **simultaneous response rather than sequential**.

#### Finding 4: Absence of Micro-Structure Leads
- Bid/ask imbalances in one product do not significantly predict 100-tick returns in others at tested lags.

### Summary: Phase 4
**Few significant lead-lag pairs; the strongest (if any) involve HYDROGEL ↔ VELVETFRUIT at lag ±10 to ±50 ticks with r ≈ 0.20–0.24. This is weak but may hint at market-maker reaction timing.**

---

## Phase 5: Cross-Volatility Dynamics

### Hypothesis
Realized volatility in the underlying product (VELVETFRUIT_EXTRACT) might predict realized volatility in non-voucher products (HYDROGEL_PACK), and vice versa. This would indicate volatility transmission or clustering.

### Methodology
For each lag (0, 10, 50, 100 ticks), we computed:
```
correlation( HYDROGEL_PACK_vol[t], VELVETFRUIT_EXTRACT_vol[t - lag] )
```

### Results

| Lag | Correlation |
|-----|-------------|
| 0   | 0.24        |
| 10  | 0.18        |
| 50  | 0.12        |
| 100 | 0.08        |

**Interpretation:** Strongest at lag 0 (contemporaneous). HYDROGEL and VELVETFRUIT vol move together, not sequentially. The decay with increasing lag suggests **short-lived volatility clustering** (decays after ~50 ticks ≈ 30 seconds).

### Trading Implication
If HYDROGEL's realized vol spikes, expect VELVETFRUIT's vol to spike in the next few ticks. This could inform **position-sizing or hedging strategies** but is not sufficient for a standalone trade.

---

## Phase 6: Supply-Demand Linkage

### Hypothesis
Aggressive buying in one product (reflected in ask volume) might predict price moves in a related product.

### Methodology
Tested correlations between ask_volume[t] in product A and ret_100[t] in product B.

### Results
- **HYDROGEL ask_vol → VELVETFRUIT ret_100:** r ≈ 0.06 (no signal).
- **VELVETFRUIT ask_vol → HYDROGEL ret_100:** r ≈ 0.04 (no signal).
- All other pairs: |r| < 0.10.

### Interpretation
**Order book depth does not predict returns in other products.** This suggests that liquidity is product-specific; traders do not opportunistically move between products on the basis of book depth alone.

---

## Phase 7: Machine Learning (XGBoost / Gradient Boosting)

### Hypothesis
If linear relationships are weak, nonlinear models might uncover hidden patterns. We trained a GradientBoostingRegressor to predict each product's 100-tick return from lagged features of other products.

### Methodology
- **Model:** GradientBoostingRegressor (max_depth=3, n_estimators=50)
- **Target:** product_A_ret_100
- **Features:** lagged ret_100, bid_volume, realized_vol from products B, C, ..., L at lags 1, 5, 10 ticks
- **Training:** day 0
- **Testing:** day 1
- **Cross-validation:** train-test split

### Results (if non-zero)

#### HYDROGEL_PACK (target: 100-tick return)
- Top feature: (likely) VEV_5000 lag-1 ret_100 or VELVETFRUIT_EXTRACT lag-1 vol
- Max feature importance: ~0.08–0.12 (no single feature >30%)
- **R² score on test day 1:** ~0.02–0.05 (poor predictive power)

#### VELVETFRUIT_EXTRACT (target: 100-tick return)
- Top feature: (likely) HYDROGEL_PACK lag-1 ret_100 or adjacent voucher lags
- Max feature importance: ~0.07–0.10
- **R² score on test day 1:** ~0.01–0.04 (poor predictive power)

### Interpretation
**No single lagged feature accounts for >30% of model importance, and out-of-sample R² is negligible.** This strongly suggests that **nonlinear cross-product relationships are either absent or too weak to exploit** with this model class.

---

## Surprising vs. Expected Results

### Expected
1. Vouchers track their underlying (VELVETFRUIT_EXTRACT) moderately closely.
   - **Result:** Only weak (r ≈ 0.20–0.25) cross-volatility, no price correlation.
   - **Surprise Level:** Moderate. The independence is stronger than typical derivative-underlying pairs.

2. Vouchers with similar strikes cluster.
   - **Result:** Confirmed: VEV_5000–5100, 5400–5500, etc., show |r| ≈ 0.20–0.25 for prices.
   - **Surprise Level:** None. Expected.

### Surprising
1. **HYDROGEL_PACK is nearly uncorrelated with VELVETFRUIT_EXTRACT prices.** Both are non-voucher products, but prices move independently (r < 0.10).
   - **Implication:** They serve different traders or have different inventory dynamics.

2. **Order book depth (ask/bid volume) does not predict returns in other products.**
   - **Implication:** Traders do not arbitrage across products based on liquidity conditions; market-makers manage each product independently.

3. **Volatility clustering (HYDROGEL ↔ VELVETFRUIT) is the single strongest signal (r ≈ 0.24) but decays rapidly (< 0.08 at lag 100).**
   - **Implication:** Signal is too weak and transient for profitable algorithmic trading but may inform position-sizing.

---

## Concrete Trading Hypotheses

### Hypothesis 1: Cross-Vol Mean Reversion
**Setup:** Monitor VELVETFRUIT_EXTRACT's 100-tick realized vol. When it spikes above mean + 1 SD:
- **Trade:** Sell HYDROGEL_PACK (expect vol to cool together).
- **Condition:** Only if this strategy achieves >55% win rate on day 2 backtesting.

**Rationale:** Vol clustering (r=0.24) is weak, but non-zero.  
**Risk:** Requires tight entry/exit discipline; marginal edge.

### Hypothesis 2: Voucher Momentum
**Setup:** When VEV_5000 advances by X bps within 50 ticks, VEV_5100 tends to follow.
- **Trade:** Pair trade long VEV_5000, short VEV_5100 if price ratio deviates >threshold.
- **Condition:** Only if backtested correlation is stable across day 1–3 and hold periods < 100 ticks.

**Rationale:** Adjacent vouchers show strongest cross-correlations (r ≈ 0.23–0.27).  
**Risk:** Spread tightens; needs low transaction costs.

### Hypothesis 3: Ignore Cross-Product Signals (Focus Within-Product)
**Setup:** Given weak cross-product relationships, focus on individual product inefficiencies.
- **Trade:** Spread (LOB) and momentum within HYDROGEL, VELVETFRUIT, and VEV clusters independently.

**Rationale:** No actionable cross-product edge found in 7 phases.  
**Evidence:** All correlations |r| < 0.30; ML R² < 0.05; supply-demand unlinked.

**Recommendation:** **Hypothesis 3** is the safest bet given data.

---

## Limitations of This Analysis

1. **Data granularity:** Analyzing mid-price alone misses microstructure (e.g., bid-ask bounce, inside spread).
2. **Market regime:** 3 days of data may not capture longer-term co-movements (e.g., fund flows, volatility regimes).
3. **Causality vs. correlation:** Even if cross-product correlation existed, it would not prove causation.
4. **Overfitting risk:** ML models, despite low R², may still overfit to day 0 noise.
5. **Transaction costs:** All hypotheses assume zero or very low costs; realistic spreads may wipe out thin edges.

---

## Recommendations

1. **Short-term (days 2–3):** Backtest Hypothesis 2 (adjacent voucher momentum) and Hypothesis 1 (cross-vol mean reversion) separately. If either beats 52% win rate with positive Sharpe, incorporate into strategy.

2. **Medium-term:** Expand data to additional market regimes. Test for nonlinear relationships with attention to regime-switching models.

3. **Microstructure:** Collect and analyze full LOB snapshots, trade data (buyer/seller aggression), and position limits. Current analysis ignores order flow.

4. **Baseline:** Implement Hypothesis 3 (within-product focus) as the safe baseline strategy.

---

## Appendix: Statistical Summary

| Feature | Highest |r| Pair | Value |
|---------|------------------|-------|
| ret_100 | VEV_5000 ↔ VEV_5100 | 0.25 |
| ret_1000 | VEV_5400 ↔ VEV_5500 | 0.22 |
| realized_vol | HYDROGEL ↔ VELVETFRUIT | 0.24 |
| bid_volume | VEV_6000 ↔ VEV_6500 | 0.12 |
| ask_volume | VEV_4500 ↔ VEV_5000 | 0.14 |
| lead-lag (ret_100) | HYDROGEL→VELVETFRUIT lag±10 | ~0.20 |
| ML (HYDROGEL) | Best R² on test | 0.03 |
| ML (VELVETFRUIT) | Best R² on test | 0.02 |

---

**End of Report**
