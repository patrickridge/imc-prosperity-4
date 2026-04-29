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

## Full Ashflow Alpha articles (verbatim from newspaper)

### 1. Lava Fountain Pen — "Crowds Line Up for Limited-Edition Lava Fountain Pen Featuring Magma Ink"

The first limited-edition Lava Fountain Pen, featuring a built-in Magma Ink reservoir, was sold yesterday during a celebratory event at the Rock & Flow Stationery shop in Magma Shopping Center. A large crowd gathered to witness the moment, following last month's merger between Stip Stationery Enterprises and Splatter Inc., the companies behind the Lava Fountain Pen and Magma Ink respectively. Several visitors reported waiting in line for more than six hours, saying they did not want to miss the release, which was widely promoted as a "hot drop."

### 2. Obsidian Cutlery — "Manufacturing Halted After Obsidian Cutlery Cuts Through Its Own Assembly Line"

A large-scale manufacturing facility suspended obsidian cutlery production after completed blades sliced through portions of the chemical assembly line used to process them. The breach triggered level 1 contamination protocols and a temporary evacuation of the site. Factory officials declined to comment, while industry experts warned the incident could have implications for other manufacturing facilities.

### 3. Pyroflex Cell — "Ignith Tax Authority Faces Industry Pressure After Abrupt End to Pyroflex Cell Tax Cut"

The Ignith Tax Authority is facing mounting pressure from energy-sector representatives following its decision to discontinue the Pyroflex Cell Tax Cut, effective tomorrow. The effectiveness of the 50% PCTC, introduced to stimulate the Pyroflex transition, has been the subject of increasing public criticism in recent months. In response, the Tax Authority has moved to abolish the measure, aligning with growing calls to end the financial incentive. Industry groups argue that the abrupt cancellation of the cut, which effectively doubles the current levy, will disrupt consumer upgrade cycles and slow new purchases.

### 4. Thermalite Cores — "Quarterly Forecast Report Shows Surge in Thermalite-Powered Smart Home Devices"

The latest quarterly forecast report shows a sharp increase in Thermalite-powered smart home devices, with active projected users rising from 1.42 million this quarter to 3.89 million next quarter. Thermalite Cores are projected to reach an average net activity time of 16 hours and 42 minutes per day, indicating more sustained household use rather than the short-term demand previously projected. The report shows a sharp rise in usage metrics, leading analysts to speculate about a very strong next quarter.

### 5. Ashes of the Phoenix — "Resurfaced Video of Ashes of the Phoenix Origin Shock Public"

Public concern escalated after a recently resurfaced video shows the sourcing method for the popular cosmetics product 'Ashes of the Phoenix'. The video shows a magnificent bird-like creature going up in flames and being reduced to ashes. Someone, who appears to be an employee of Eternal Feathers Ltd., walks into the scene scooping up a bucket load of the ashes, and then walks away. Following the public outcry, Forever Feathers Ltd. immediately tried to reassure the public that "the sourcing methods for Ashes of the Phoenix have been the same for many decades and do not harm the birds in any way. Birds who, we would like to emphasize once more, are actually immortal."

### 6. Scoria Paste — "Lava D. Ray Says 'Glory Days Are Ahead' For Ignith Economy, Urges Stockpiling of Scoria Paste"

Lava D. Ray, creative multitalent and self-proclaimed market medium, appeared on BrewTube Live claiming she has studied current market dynamics, "took its temperature" and is confident the Ignith economy will reach an all-time high in the foreseeable future. Speaking during her latest streaming marathon, D. Ray advised households to "stock up on Scoria Paste before it becomes unaffordable," pointing to the compound's central role in daily maintenance across Ignith. Often referred to as "the paste that keeps Ignith together," Scoria Paste is used extensively in residential repairs and infrastructure upkeep, making it a familiar indicator for household conditions.

### 7. Lava Cakes — "Traces of Actual Lava Found in Lava Cakes, Prompting Health Review"

Health authorities have launched a formal review after laboratory tests confirmed traces of actual lava in the wildly popular Lava Cakes. The discovery prompted an immediate halt in sales pending further investigation, with officials citing potential health risks associated with volcanic material exposure. While Hotchot Pastries Ltd. said it is cooperating fully with regulators, civil lawsuits are already piling up and vendors are quick to return their stock with lawyer letters attached.

### 8. Volcanic Incense — "Sudden Surge in Volcanic Incense as Whiff Nostralico Calls for People to Follow His Lead"

Volcanic Incense extended its rally this cycle as attention intensified around recent activity linked to Whiff Nostralico. Trading data shows accelerated buying concentrated within narrow time windows, coinciding with Nostralico's public appearances and commentary. He openly calls for anyone with "a genuine interest in making money" to follow his lead and buy the Volcanic Incense.

### 9. Sulfur Ltd. — "Index Committee Confirms Sulfur Ltd. For Elemental Index 118"

Elemental Index 118 will add Sulfur Reactor to its upcoming rebalance, according to the index committee's latest notice. The inclusion follows a review of eligible constituents across the elemental processing sector, where Sulfur Reactor's products are regarded as industry benchmarks. Funds tracking the index are expected to adjust their holdings accordingly once the rebalance takes effect later this cycle.

---

## Research findings: P3 calibration + trap analysis

### P3 precedent (from hedgehogs writeup)

| Product | Expected | Actual | Error | Takeaway |
|---|---|---|---|---|
| Haystacks | +12% | -0.48% | -12.5pp | "Obvious" long was dead wrong |
| Ranch Sauce | +10% | -0.72% | -10.7pp | "Obvious" long was dead wrong |
| Cacti Needle | -30% | -41.2% | +11.2pp | Short overshot |
| Solar Panels | -30% | -8.9% | +21.1pp | Regulatory short massively undershot |
| Red Flags | +5% | +50.9% | +45.9pp | PR scandal overshot 10x |
| VR Monocle | +30% | +22.4% | -7.6pp | Reasonable estimate |
| Quantum Coffee | -50% | -66.8% | +16.8pp | Short overshot |
| Moonshine | 0% | +3.0% | +3.0pp | Flat call was correct |
| Striped Shirts | 0% | +0.21% | +0.2pp | Flat call was correct |

**Patterns:**
- Devs plant at least 2 misdirections where "obvious" sentiment is wrong
- Regulatory/index catalysts undershoot 50-100% of expectation
- Scandal/PR stories overshoot 3-10x baseline sentiment
- Negative catalysts more reliable than positive ones

### Trap analysis for P4 R5

| Good | Surface | Trap Risk | Adjusted Direction | Adjusted Conviction | Notes |
|---|---|---|---|---|
| Thermalite Cores | LONG | LOW | **LONG** | **HIGH** | Only story with hard numbers (2.7x growth). Cleanest signal. |
| Lava Cakes | SHORT | LOW | **SHORT** | **HIGH** | Airtight — lava in food, health halt, lawsuits. No ambiguity. |
| Obsidian Cutlery | SHORT | LOW | **SHORT** | MEDIUM | Clean operational damage, contamination, evacuation. |
| Pyroflex Cell | SHORT | MEDIUM | **SHORT** | MEDIUM | Logical (levy doubles) but "effective tomorrow" = may be partially priced in. |
| Lava Fountain Pen | LONG | MEDIUM | **LONG** | LOW | Hype ≠ sustained demand. Limited edition = artificial urgency, post-launch fade risk. |
| Volcanic Incense | LONG | **HIGH** | **FLIP SHORT** | MEDIUM | Influencer pump: Nostralico openly calling buyers, narrow time windows = coordinated. Classic pump-and-dump setup. |
| Scoria Paste | LONG | **HIGH** | **SKIP** | SKIP | "Self-proclaimed market medium" = zero credibility. Artificial urgency ("before unaffordable"). |
| Sulfur Ltd. | LONG | MEDIUM-HIGH | **NEUTRAL/CAP** | LOW | Index inclusion is mechanical but likely already priced in. P3 showed regulatory catalysts undershoot massively. |
| Ashes of Phoenix | SHORT | HIGH | **UNCERTAIN** | LOW | Company says birds are "immortal" — scandal may blow over. Contradictory story. |

### Sizing recommendations

- **Max 15% per position** (not 25%) — fee at 15% is 2.25% vs 6.25% at 25%
- **Hedge factor 0.75** — P3 hedgehogs needed exactly this to survive estimation risk
- **Spread > concentration** — absorbs variance better when estimates are off
- **Skip weak convictions** — cost of being wrong (fees + reversal) exceeds upside
- **Sign-flip is the killer risk** — one wrong direction loses 3x expected gain

---

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
