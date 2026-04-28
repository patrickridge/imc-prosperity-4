---
product: 9 Ignith goods (Round 5 Manual)
date: 2026-04-28
status: active
hypothesis: Allocate 1M budget across 9 news-driven goods using sentiment direction and quadratic-fee-aware sizing
test: Closed-form allocator under quadratic fee constraint
result: pending sentiment scores from team
---

## The challenge

You hold a portfolio for ONE day on the Ignith exchange. Allocate up to 100% of a `1,000,000` budget across 9 goods.

**Fee per product:** `fee = (volume_pct / 100)² × budget`
where `volume_pct` is the % of budget assigned to that product (0–100).

- Total volume across products must be ≤ 100%.
- Unused budget expires worthless.
- Used budget is subtracted from PnL — fees only apply on top of that, scaled quadratically.

The 9 goods come straight from the news stories in [manual5.pdf](manual5.pdf) ("Ashflow Alpha"). News sentiment determines direction; the fee formula determines size.

## The 9 goods and their stories

| # | Good | Direction | Headline | Conviction |
|---|------|-----------|----------|------------|
| 1 | **Lava Fountain Pen** (Stip + Splatter merger) | LONG | Successful "hot drop" launch, 6h queues | medium |
| 2 | **Thermalite Cores** | LONG | Quarterly forecast: users 1.42M → 3.89M next quarter | **high** (numeric) |
| 3 | **Scoria Paste** | LONG | Lava D. Ray urges stockpiling before "unaffordable" | medium |
| 4 | **Volcanic Incense** | LONG | Whiff Nostralico publicly calling buyers in, narrow-window buying accelerating | medium |
| 5 | **Sulfur Ltd.** | LONG | Being added to Elemental Index 118; index funds rebalance later this cycle | **high** (mechanical) |
| 6 | **Obsidian Cutlery** | SHORT | Production halted, contamination, evacuation | medium |
| 7 | **Pyroflex Cell** | SHORT | Tax cut canceled, levy doubles → "disrupt upgrades, slow purchases" | medium |
| 8 | **Ashes of the Phoenix** (Forever Feathers) | SHORT | Resurfaced video shows phoenix burned for sourcing — PR scandal | medium |
| 9 | **Lava Cakes** (Hotchot Pastries) | SHORT | Actual lava found in product, lawsuits piling up | medium |

5 longs, 4 shorts. Two stand out as higher-conviction:
- **Sulfur Ltd.** — index inclusion is a *mechanical* event. Index funds must buy on rebalance.
- **Thermalite Cores** — only story with a specific number (2.7× user growth).

## How the fee shapes allocation

Treat `w_i` = signed allocation as a fraction of budget (positive = long, negative = short, `Σ |w_i| ≤ 1`). Profit per good with expected return `r_i`:

```
profit_i = w_i · r_i · B − w_i² · B
```

Single-product optimum (unconstrained): `w_i* = r_i / 2`.

So if you expect Thermalite to rise 30%, optimal allocation is 15%. If you expect Lava Cakes to drop 20%, optimal short is 10% (`|w| = 0.10`).

Sum the optima: if `Σ |r_i|/2 ≤ 1`, the unconstrained allocation works. Otherwise, scale all positions down proportionally.

P3 hedgehogs scored **126,751 / 194,522 optimal** on this kind of round — they intentionally hedged below optimal because expected moves were guesses. We should do the same.

## What team needs to fill in

> ★ This is the meaningful decision: estimate expected move `r_i` for each story.
>
> P3 hedgehogs used ranges of ±5% to ±50% based on headline strength. Look at their table in `docs/reference/prosperity-3-hedgehogs.md` (Round 5 section) for calibration — they overestimated some moves badly (Haystacks, Solar Panels), so be cautious.

Edit [allocate.py](allocate.py) and fill in the `expected_returns` dict with your `r_i` estimates. Then run it to print the optimal volume_pct per product and total expected PnL.

## Strategy guardrails

- **Cap any single position at 25%** of budget. Even high-conviction shouldn't go bigger — fee at w=0.25 is already 6.25% of budget per product.
- **Hedge below "optimal"**. If the math says w=0.20, take 0.15. P3 lessons: some "obvious" stories don't move.
- **Sulfur Ltd. and Thermalite get the largest sizes** by default — they're our cleanest signals.
- **Skip a product entirely** if conviction is weak. Σ |w_i| can be < 1.

## Submit

Numbers go directly into the Manual Challenge Overview window before the round closes. Re-submitting overwrites; last submission wins.
