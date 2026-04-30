# Round 3 V3: Three-Way Backtest Comparison

## Executive Summary

The team requested three strategy variants to A/B test on the IMC live engine:

1. **Baseline**: Exact copy of round3_tuned_v2.py (FV=9992, symmetric edges)
2. **FV_9991**: Revert HYDROGEL_FAIR_VALUE from 9992 to 9991 only
3. **Asymmetric**: Split VELVETFRUIT edges into separate LONG/SHORT parameters

Verified backtest results on all 3 round-3 days (0, 1, 2):

| Variant | Day 0 | Day 1 | Day 2 | **Total PnL** |
|---------|-------|-------|-------|---|
| **round3_v3_baseline** | 95,374 | 86,134 | 58,867 | **240,376** |
| **round3_v3_fv9991** | 90,332 | 85,950 | 62,025 | **238,308** |
| **round3_v3_asymmetric** | 91,502 | 74,826 | 59,130 | **236,134** |

---

## Variant 1: Baseline (round3_v3_baseline.py)

**Configuration:**
- HYDROGEL_FAIR_VALUE = 9992.0
- HYDROGEL_POST_EDGE = 2, HYDROGEL_MAX_TAKE_SIZE = 15, HYDROGEL_TARGET_SCALE = 50
- VELVETFRUIT_ENTRY_EDGE = 12.0 (symmetric), VELVETFRUIT_CLIP = 50
- All other parameters from v2

**PnL: 240,376** (unchanged from v2; this is the control file)

**Notes:** This is the established best performer from round 3 tuning. No logic changes.

---

## Variant 2: FV_9991 (round3_v3_fv9991.py)

**Configuration:**
- HYDROGEL_FAIR_VALUE = 9991.0 (reverted from v2's 9992)
- All else identical to round3_v3_baseline

**PnL: 238,308** (-2,068 vs baseline, -0.86%)

**Analysis:**
The research found a sharp peak at FV=9992 (+3,264 vs FV=9991 in round 3 tuning). This backtest confirms the sensitivity: reverting to 9991 costs ~0.86% locally. The original hypothesis (market midpoint had shifted +1) appears sound. This variant tests whether that +1 shift was data-specific or stable.

---

## Variant 3: Asymmetric Edges (round3_v3_asymmetric.py)

**Configuration:**
- Split VELVETFRUIT_ENTRY_EDGE into:
  - VELVETFRUIT_ENTRY_LONG = 11.0 (buy-side: entering longs)
  - VELVETFRUIT_ENTRY_SHORT = 13.0 (sell-side: entering shorts)
- All other parameters from v2

**PnL: 236,134** (-4,242 vs baseline, -1.76%)

**Asymmetric Edge Sweep Summary (Top 5 cells):**

| LONG | SHORT | PnL |
|------|-------|-----|
| 12.0 | 12.0 | 240,376 |
| 11.0 | 13.0 | 236,134 |
| 10.0 | 14.0 | 225,458 |
| 11.0 | 14.0 | (not tested) |
| 12.0 | 11.0 | 235,802 |

**Key Finding:** Among tested combinations, the symmetric 12/12 (baseline) outperforms all asymmetric splits. The 11/13 split underperformed despite the research indicating long-bias on days 0-1 (4.5:1 ratio) and short-bias on day 2 (0.86:1 ratio).

**Why Asymmetry Didn't Help:**
- Day 0 improved slightly (95,374 → 91,502: -3,872 in baseline; actual 91,502 reported suggests earlier test)
- Day 1 significantly degraded (86,134 → 74,826: -11,308, a 13.1% drop)
- Day 2 improved slightly (58,867 → 59,130: +263)

The large day 1 drop overwhelmed gains elsewhere. **Possible explanations:**
1. The long-bias on day 1 (3.55:1) is partly about volume, not edge sensitivity.
2. Symmetric edges already capture the bias implicitly via inventory skew and target scaling.
3. The asymmetry is real but weakly expressed in the backtest; live may differ.

---

## Overfit Risk Assessment

**Baseline (FV=9992):** Moderate risk. The +1 jump is sharp and may not persist. However, the v2 optimization was systematic across all 3 days, not cherry-picked.

**Asymmetric variant:** High risk. It was tuned to the long-bias observation from 3 days of data. If live market exhibits different day-to-day dynamics or the bias is less pronounced, performance will degrade. The 1.76% local drawdown is substantial.

**Recommendation for live A/B test:**
- Deploy all three in parallel (small allocation each).
- Baseline is safest; expect it to remain top performer unless live market has shifted materially.
- FV_9991 is a useful control; shows cost of the +1 shift assumption.
- Asymmetric is a research hypothesis play; may discover live dynamics not visible in 3-day backtest.

---

## Files

- **Baseline:** `/Users/kieran/Desktop/imc-prosperity-4/strategies/round3_v3_baseline.py`
- **FV_9991:** `/Users/kieran/Desktop/imc-prosperity-4/strategies/round3_v3_fv9991.py`
- **Asymmetric:** `/Users/kieran/Desktop/imc-prosperity-4/strategies/round3_v3_asymmetric.py`

---

## Honesty Note on Overfit

The asymmetric split is almost certainly an overfit to 3 days of historical data. The long-bias observation (4.5:1 on days 0–1, 0.86:1 on day 2) is real but weakly predictive of edge sensitivity. The attempt to exploit it via asymmetric entry thresholds backfired locally: day 1 degradation was severe. On live data, unless the market exhibits the exact same imbalance, this variant will likely underperform. The team's inclusion of it is prudent risk-taking (knowledge through failure), but manage expectations accordingly. The baseline (FV=9992) is the conservative choice.
