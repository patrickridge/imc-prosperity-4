---
purpose: Round 5 manual submission — values entered on IMC site
date: 2026-04-30
status: submitted
---

## Submitted values

These were entered into the Manual Challenge form on prosperity.imc.com on 2026-04-30 and confirmed accepted.

| Tradable good | Buy/Sell | Percentage | Investment | Fee |
|---|---|---:|---:|---:|
| Obsidian cutlery | Sell | **8%** | 80,000 | 6,400 |
| Pyroflex cells | Sell | **6%** | 60,000 | 3,600 |
| Thermalite core | Buy | **9%** | 90,000 | 8,100 |
| Lava cake | Sell | **11%** | 110,000 | 12,100 |
| Magma ink | Buy | **2%** | 20,000 | 400 |
| Scoria paste | — | (skipped) | — | — |
| Ashes of the Phoenix | Sell | **8%** | 80,000 | 6,400 |
| Volcanic incense | — | (skipped) | — | — |
| Sulfur reactor | Buy | **6%** | 60,000 | 3,600 |
| **Total** | | **50%** | **500,000** | **40,600** |

Expected PnL after fees: **~+65,000**.

## Reasoning per good

The values come from `manual/round5/allocate.py` `expected_returns` dict. Each `r_i` is the expected % move; the allocator computes `w* = r_i / 2` (the profit-maximising weight on a quadratic-fee curve), caps at 25% per good, and applies a 75% hedge factor (P3 hedgehogs hit 65% of optimal because they overestimated, so hedging reduces tail risk). Whole-number rounding for the IMC form.

| Good | r_i used | Why |
|---|---|---|
| Lava cake | **−30%** | Actual lava found in product + lawsuits piling up = sustained drag, not a news scandal that fades. Strongest consensus short. |
| Thermalite core | **+25%** | Only headline with hard numbers (1.42M → 3.89M users projected, 2.7×). Quantitative + obvious bullish read. |
| Obsidian cutlery | **−20%** | Production halted, contamination + evacuation. Clear consensus short. |
| Ashes of Phoenix | **−20%** | PR scandal from resurfaced video showing phoenix burned. PR scandals can fade but consensus is short. |
| Pyroflex cells | **−15%** | Tax cut canceled, levy doubles → demand drops. Consensus short. |
| Sulfur reactor | **+15%** | Mechanical index inclusion (Elemental Index 118) → forced rebalance buying by index funds. |
| Magma ink | **+5%** | Hot drop launched after Stip + Splatter merger. Already news-of-the-day so partly priced in. Small position. |
| Scoria paste | **0%** | Pure influencer hype (Lava D. Ray). Crowd direction unpredictable, skip. |
| Volcanic incense | **0%** | Pure influencer hype (Whiff Nostralico). Same as Scoria, skip. |

## Why these specific weights, not others

The wiki update on 29/04 clarified: *"crowd consensus moves the realised return within the range"*. So:

- **Going with the consensus amplifies profit.** Lava cake / Thermalite / Sulfur are consensus trades — everyone reads the same news, the crowd will push the realised return in our direction.
- **Going against subtle stories is risky.** Influencer hype (Scoria, Volcanic) is a coin flip on whether the crowd believes it.
- **Magma ink is small** because the launch event already happened — likely priced in by the time we trade.

## How to upload bigger sizes if you want more PnL

Run the allocator with custom values:

```
python3 manual/round5/allocate.py
```

Or edit `expected_returns` in `manual/round5/allocate.py` (or `sentiment_estimates.py` for the BASE/AGGRESSIVE/CONSERVATIVE scenarios).

The conservative cap is 25% per good and a 75% hedge factor. To go bigger, edit `MAX_SINGLE_POSITION` and `HEDGE_FACTOR` in `allocate.py`. Going to 100% hedge (no hedge) on the same `r_i` values gives ~+90k expected, but adds risk if the sentiment estimates are off.

Last submission wins on the IMC site — you can resubmit until round close.

## Wiki update history

- 2026-04-29 12:00 CEST: "Sulfur Ltd." renamed to "Sulfur Reactor" in the Ashflow Alpha visual. Mechanism unchanged — still mechanical index inclusion.
- "Forever Feathers" = "Eternal Feathers" — typo correction, no impact.
