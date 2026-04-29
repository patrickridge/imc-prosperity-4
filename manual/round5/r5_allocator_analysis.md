# Round 5 Manual — Analysis and Allocation

## Profit formula

```
profit_i = w_i * r_i * B - w_i^2 * B
```

- `w_i` = signed fraction of budget (positive = long, negative = short)
- `r_i` = expected return (positive = up, negative = down)
- `B` = 1,000,000
- Fee: `fee_i = w_i^2 * B` (quadratic)
- Optimum per product: `w_i* = r_i / 2`
- Constraint: `sum(|w_i|) <= 1`

## Sensitivity

| Error type | PnL cost |
|---|---|
| Wrong direction (est +10%, actual -10%) | -7,500 |
| Overestimate 2x (est 30%, actual 15%) | -1,055 |

Direction errors are 7x more expensive than magnitude errors.

## P3 calibration

| Product | Expected | Actual | Error |
|---|---|---|---|
| Haystacks | +12% | -0.48% | Wrong direction |
| Ranch Sauce | +10% | -0.72% | Wrong direction |
| Solar Panels | -30% | -8.9% | Overestimated 3.4x |
| Red Flags | +5% | +50.9% | Underestimated 10x |
| Cacti Needle | -30% | -41.2% | Within 1.4x |
| VR Monocle | +30% | +22.4% | Within 1.3x |
| Quantum Coffee | -50% | -66.8% | Within 1.3x |

Hedgehogs captured 65.2% of optimal (126,751 / 194,522). Two direction errors cost ~6k. The Red Flags underestimate cost ~44k in missed profit.

## Pre-submission checklist

- [x] Shorts allowed — rules show signed weights
- [x] Fee formula confirmed: `(vol_pct / 100)^2 * budget`
- [x] Volume = absolute value of allocation
- [x] `allocate.py` run with final estimates — expected PnL +65,625
- [x] No single product > 20% (max is Lava Cakes at 11.3%)
- [ ] PnL positive if 2 estimates wrong direction — **fails** if Thermalite + Lava Cakes both flip (-48,750), **passes** for all other pairs

---

## Allocation

| # | Good | r_i | Direction | Weight | Open question |
|---|------|-----|-----------|--------|---------------|
| 1 | Thermalite Cores | +25% | LONG | ~9.4% | |
| 2 | Lava Cakes | -30% | SHORT | ~11.3% | |
| 3 | Obsidian Cutlery | -20% | SHORT | ~7.5% | |
| 4 | Pyroflex Cell | -15% | SHORT | ~5.6% | |
| 5 | Ashes of the Phoenix | -20% | SHORT | ~7.5% | Company says birds are "immortal" — does the scandal hold? |
| 6 | Sulfur Ltd. | +15% | LONG | ~5.6% | Forced-buy flow ≠ P3 regulatory removal — should this be higher? |
| 7 | Lava Fountain Pen | +5% | LONG | ~1.9% | |
| 8 | Volcanic Incense | 0% | SKIP | 0% | Pump-and-dump or genuine momentum? |
| 9 | Scoria Paste | 0% | SKIP | 0% | Messenger is trash but product is essential infrastructure |

Budget used: ~49%. Hedge factor 0.75. Expected PnL: +65,625.

## Per-product justification

**Thermalite Cores — LONG +25%**
Only story with a hard number: users 1.42M → 3.89M (2.7x). P3 analog (Quantum Coffee): hedgehogs captured 94% of optimal.

**Lava Cakes — SHORT -30%**
Lab-confirmed lava in food. Sales halted. Lawsuits filed. Vendors returning stock. No counternarrative.

**Obsidian Cutlery — SHORT -20%**
Production suspended, contamination, evacuation. No recovery timeline.

**Pyroflex Cell — SHORT -15%**
Levy doubles "effective tomorrow." Discounted from -20% because timing suggests partial priced-in.

**Ashes of the Phoenix — SHORT -20%**
Video shows phoenix burned for cosmetics. Forever Feathers says birds are "immortal" — if true, scandal is toothless. P3 analog (Red Flags) moved +50.9% on +5% estimate, but that story had no defense. This one does. Set at -20%, not higher.

**Sulfur Ltd. — LONG +15%**
Index inclusion forces tracking funds to buy. P3 analog (Solar Panels, -30% expected, -8.9% actual) was a regulatory *removal* — different mechanism. But "later this cycle" means the market can front-run. Capped at +15%.

**Lava Fountain Pen — LONG +5%**
6-hour queues at launch. But limited-edition hype fades and merger completed last month. P3 analog (Haystacks) went -0.48%.

**Volcanic Incense — SKIP**
Nostralico openly calls followers to buy in "narrow time windows." P3 hype analogs (Haystacks, Ranch Sauce) went -0.48%, -0.72%. Flipping to short risks the meta-trap.

**Scoria Paste — SKIP**
"Self-proclaimed market medium" on a streaming marathon. Scoria Paste is essential infrastructure ("the paste that keeps Ignith together"), but P3 hype analogs went flat. Skip, don't short.

## P3-to-P4 mapping

| P3 Story Type | P3 Expected | P3 Actual | P4 Analog | P4 Estimate |
|---|---|---|---|---|
| Fundamental (Quantum Coffee) | -50% | -66.8% | Thermalite Cores | +25% |
| PR scandal (Red Flags) | +5% | +50.9% | Ashes of the Phoenix | -20% |
| Operational (Cacti Needle) | -30% | -41.2% | Obsidian Cutlery / Lava Cakes | -20% / -30% |
| Regulatory (Solar Panels) | -30% | -8.9% | Sulfur Ltd / Pyroflex Cell | +15% / -15% |
| Hype/influencer (Haystacks, Ranch Sauce) | +12%, +10% | -0.48%, -0.72% | Volcanic Incense / Scoria Paste | SKIP / SKIP |

## Risks

- **Ashes of the Phoenix**: riskiest directional call. "Immortal birds" could neutralize the scandal.
- **Volcanic Incense skip**: if genuine momentum, we miss it.
- **Worst-case 2-flip**: Thermalite + Lava Cakes both wrong = -48,750. All other pairs stay positive.
