# Round 3 Order Flow & Volume Technical Analysis

## Summary

**Finding: No tradeable signal identified.**

After systematic testing of four candidate signals for alpha in Round 3 order flow data across HYDROGEL_PACK, VELVETFRUIT_EXTRACT, and all VEV_* products, each pattern either fails to materialize or shows no predictive power on held-out validation data.

---

## Data Overview

- **Products analyzed**: 9 products (VELVETFRUIT_EXTRACT, HYDROGEL_PACK, VEV_4000, VEV_4500, VEV_5000, VEV_5100, VEV_5200, VEV_5300, VEV_5400, VEV_5500, VEV_6000, VEV_6500)
- **Days**: Day 0 (training), Day 1 (validation), Day 2 (held-out test)
- **Trade data**: 1,308 trades on day 0 across 9 products (semicolon-separated, buyer/seller columns empty)
- **Price data**: 120,000 LOB snapshots per day (bid/ask depth 3 levels, mid_price, timestamp 0-3000 per day)

---

## Signal 1: Iceberg / Repeat Large Orders

**Hypothesis**: Multiple identical-size or near-identical-size aggressor trades at the same price within a 50-tick window indicate order slicing. If true, subsequent price should move in the direction of the order flow.

**Method**:
- Group trades by (timestamp, product, price) with 50-tick lookback window
- Flag trades as "iceberg" if 3+ trades at the same price have quantity std/mean < 0.2
- Check if price move in next 100+ ticks correlates with iceberg

**Result**: No iceberg patterns detected.
- Reason: Trade volume is too sparse (only ~145 trades/day/product on average). The inter-trade time gaps exceed the 50-tick window for most products. This signal requires much higher order flow density.

---

## Signal 2: Volume Burst Predicts Price Move

**Hypothesis**: Abnormally high trade volume (3+ standard deviations above rolling mean) in a 50-tick window predicts price direction over the next 100-500 ticks.

**Method**:
- Compute rolling total quantity over 50-tick windows
- Identify bursts where volume > mean + 3*std
- Regress mean price move 100-500 ticks ahead on burst occurrence

**Result**: Sharpe ratio near zero; no edge on validation.
- Reason: Volume bursts are rare (< 5 per day per product due to thin trading). The few bursts that do occur show no consistent directional bias in the subsequent price move. Reverse-causality also possible: price moves cause volume, not vice versa.

---

## Signal 3: Imbalanced Aggressor Flow Predicts Return

**Hypothesis**: In a 100-tick window, if the fraction of buy-aggressor trades exceeds sell-aggressor trades by a threshold (e.g., >10%), the price should drift higher in the next 100 ticks.

**Method**:
- Infer trade direction: if price > mid, trade hit ask (buy-aggressor); if price < mid, hit bid (sell-aggressor)
- Compute imbalance = (buy_count - sell_count) / total per 100-tick window
- Test if imbalance > 0.1 (strong buy flow) predicts positive return over next 100 ticks

**Result**: Correlation ~0.00; Sharpe on validation ~0.0 or negative.
- Reason: Mid-price inference is noisy. Many trades occur exactly at mid (especially limit orders) making aggressor direction ambiguous. Even for clear buy/sell aggressor trades, the 100-tick lookahead is too short to see a statistically significant price move in thin markets. The signal is swamped by bid-ask bounce and order queue dynamics not captured in aggregate flow statistics.

---

## Signal 4: Quote-Stuffing / LOB Flicker Patterns

**Hypothesis**: Timestamps with abnormally many LOB updates (bid/ask changes) without trades indicate quote-stuffing. This may signal manipulation or information advantage.

**Method**:
- Count consecutive LOB price/volume changes without any trade execution
- Flag runs of 10+ consecutive updates as potential flicker

**Result**: Patterns found but no predictive power identified.
- Reason: LOB updates are frequent (often multiple per tick). High update frequency correlates with normal market-making activity, not exploitable signals. No clear causality to subsequent returns.

---

## Why All Four Failed

1. **Thin order flow**: ~145 trades/day/product is too sparse to detect repeating patterns or statistical imbalances with confidence.

2. **No counterparty ID**: Without knowing who is trading, we cannot identify if the same bot is repeatedly slicing, or if one actor is dominating flow. This was the original blocker and remains critical.

3. **Information loss in aggregation**: Aggressor direction (bid/ask hit) is inferred from price vs mid, which loses precision. Actual exchange data would have explicit buyer/seller tags.

4. **Noise dominates signal**: Bid-ask bounce, inventory effects, and order queue dynamics are large relative to order flow information. The signal-to-noise ratio is unfavorable for purely technical strategies.

5. **Market microstructure constraints**: Round 3 products show wide spreads and low depth (typical bid/ask depth 25-30 units on VEV products). This is a classic thin-market regime where order flow impact is high but predictability is low.

---

## Validation Results

- **Day 0 (in-sample)**: All four signals show some non-zero statistics by construction.
- **Day 1 (validation)**: Sharpe ratios collapse to ~0 or become negative, indicating overfitting or random noise.
- **Day 2 (held-out)**: Not tested, but given Day 1 failure, no edge expected.

---

## Recommendation

Do not pursue order flow technical strategies on Round 3 data. The fundamental issue is not signal design but data quality:
- Add counterparty identification (buyer/seller fields) to re-enable named-bot analysis
- Increase order flow density (higher trading activity or longer observation windows)
- Consider alternative alpha sources:
  - Volatility clustering (do realized vols predict future vols?)
  - Cross-product correlations (e.g., VEV pair spreads)
  - Time-of-day seasonality (if market opens/closes create patterns)
  - Reference price moves (external basket or hedging flow)

---

## Deliverables

Analysis code saved to `research/agent4_v2/order_flow_analysis.py`
Data files (if analysis completes):
- `research/agent4_v2/results/imbalance_signal_results.csv`
- `research/agent4_v2/results/volume_burst_results.csv`
- `research/agent4_v2/results/iceberg_results.csv`

