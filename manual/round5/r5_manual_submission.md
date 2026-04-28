---
product: Round 5 Manual — recommended submission
date: 2026-04-28
status: draft for team review
---

## Recommended submission (BASE case)

| Good | Direction | volume_pct | Rationale |
|---|---|---|---|
| LAVA_FOUNTAIN_PEN | LONG  | **+1.88%** | hot drop launch + merger; niche, possibly priced in |
| THERMALITE_CORE   | LONG  | **+7.50%** | only headline with a number — 1.42M → 3.89M users (2.7×) |
| SCORIA_PASTE      | LONG  | **+3.75%** | influencer urging stockpile before "unaffordable" |
| VOLCANIC_INCENSE  | LONG  | **+3.75%** | Whiff Nostralico publicly accelerating buys |
| SULFUR_LTD        | LONG  | **+5.62%** | mechanical index inclusion → forced rebalance buying |
| OBSIDIAN_CUTLERY  | SHORT | **−3.75%** | production halted, contamination |
| PYROFLEX_CELL     | SHORT | **−5.62%** | tax cut canceled, levy doubles |
| ASHES_OF_THE_PHOENIX | SHORT | **−3.75%** | PR scandal (PR scandals often fade) |
| LAVA_CAKES        | SHORT | **−5.62%** | actual lava found + lawsuits |

**Budget used: 41.2%** (well under 100%)
**Expected PnL: +35,156**

## Sensitivity table

| Scenario | r_i scale | Budget used | Expected PnL |
|---|---|---|---|
| Aggressive — narratives play out fully | 1.5× base | 61.9% | +79,102 |
| **BASE — recommended** | 1.0× base | **41.2%** | **+35,156** |
| Conservative — most news is priced in | 0.5× base | 20.6% | +8,789 |

## Why BASE, not Aggressive

P3 hedgehogs scored **126,751 / 194,522** optimal (65%) on this exact challenge type. Their post-mortem: they overestimated some moves (Haystacks, Solar Panels) and got burned. We hedged below optimal in [allocate.py](allocate.py) (75% hedge factor + 25% single-position cap) precisely to avoid that trap. Aggressive estimates re-introduce the risk.

If the team has stronger conviction on a specific story (e.g., Sulfur Ltd. index inclusion has a hard date), edit [sentiment_estimates.py](sentiment_estimates.py) and re-run. The framework is designed for last-minute updates.

## How to submit

Re-run after any edits:

```
python3 manual/round5/sentiment_estimates.py
```

Type the `volume_pct` numbers from the BASE case into the Manual Challenge Overview window. **Use signed values** (negative for shorts). Last submission wins, so iterate freely until the round closes.

## What could change the call

- Sulfur index inclusion date confirmed before/after the trading day → resize accordingly
- New news drops between now and round close → re-estimate that good
- Team disagrees on direction of any single story → easy to flip in `sentiment_estimates.py`
