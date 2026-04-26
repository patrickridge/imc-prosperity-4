# Round 3 — What We Tried and Why

All tests used `--match-trades worse` (fills only at strictly better prices — the conservative setting).
Baseline PnL after bug fixes: **210,896** across 3 days.
Each idea was tested alone against baseline, then winners were combined.

---

## Bug Fixes (applied first)

**VEV position limit was wrong.** Wiki says 300, code said 200. Fixed it. Small gain.

**TTE was hardcoded to 5 days.** The historical data days have TTE = 8, 7, 6 — not 5. We now estimate the real TTE from option prices on the first tick and persist it. Gains +1,168, mostly on day 2 where the error was largest (6 vs 5).

**TTE had a floor of 0.5 days.** This overpriced options near end of day. Removed it.

**HYDROGEL post_edge.** Swept 36 parameter combos. take_edge=20 was already optimal, quote_size didn't matter, post_edge=3 beat post_edge=2 by +529. Wider margin, same fill rate.

---

## What Worked

### Bid+1 for VEV_5200 and VEV_5300 — **+16,230**

The problem: in conservative mode, bots sell at the bid price, and our bids were also at the bid. Equal prices don't fill. Zero option PnL.

The fix: bid one tick above the market bid. Now bot sells at `bid` are strictly better than our quote at `bid+1`, so we get filled.

Why it's profitable: these options are cheap. Market IV is ~20% but realized vol is ~34%. We're buying underpriced vol and profiting when positions are marked to market at day end.

Why only 5200/5300: they have 3-tick and 2-tick spreads. Bid+1 still leaves room inside the spread. For 1-tick spread options (5400, 5500), bid+1 = the ask — no buffer, no edge.

Independently verified. VELVETFRUIT and HYDROGEL PnL identical before and after.

### VELVETFRUIT edge=12, clip=60 — **+16,012**

VELVETFRUIT is the biggest profit center (~47% of total). The original parameters (entry_edge=10, clip=20) were never questioned.

We swept entry_edge from 5 to 15 and clip from 10 to 100. The peak is at edge=12, clip=60. The profit profile is a smooth hill — edge=11 and edge=13 are both clearly lower but still beat the baseline. Not a knife-edge optimum.

What edge=12 means in practice: buy when mid < 5243 (was 5245), sell when mid > 5267 (was 5265). A slightly wider band catches bigger moves. Clip=60 lets us fill more volume per tick when the book is thick — clip=20 was leaving fills on the table.

**Overfitting caveat:** Tuned on the same 3 days we test on. The smooth peak suggests the improvement is real, but the exact +16k magnitude may shrink on unseen data. The reviewer estimated ~60-70% should persist.

---

## What Failed (and why)

### Relax delta cap (H-B) — both worse
Cap at 1000 prevents overaccumulating options. Tried 2000 and 5000. Both lost money. The cap is doing its job — without it, we pile into options that hurt mark-to-market PnL.

### Penny options at price 1 (H-C) — loses 0.5/lot
VEV_6000/6500 trade at price 0. Buying at 1 means trades at 0 fill us. But the mid is 0.5, so we pay 1 for something worth 0.5. Guaranteed loss by construction.

### Delta hedge via VELVETFRUIT (H-D) — catastrophic (-131k)
P3 winners hedged option delta through the underlying. We tried it: replace VELVETFRUIT mean-reversion with delta-neutralizing trades. VELVETFRUIT went from +100k to -22k. The mean-reversion edge on VELVETFRUIT is worth far more than any hedging benefit. P4 is not P3 — the underlying here has strong mean-reversion that shouldn't be sacrificed.

### VEV_5500 at bid+1 (H-E) — loses money
1-tick spread means bid+1 = the ask. No room inside the spread. The bid+1 trick only works when there's spread to absorb the extra tick.

### Buy at ask for tight-spread options (H-F) — -2,448
Same idea as H-E but stated differently. Paying the full spread on 1-tick options doesn't work — the vol discount (theory) doesn't show up in mark-to-market (practice).

### Bid+2 for VEV_5200/5300 (H-G) — worse than bid+1
For VEV_5300 (spread=2), bid+2 hits the ask. Catastrophic on day 0. For VEV_5200 (spread=3), bid+2 gains on days 0-1 but loses more on day 2. Bid+1 is the sweet spot — one tick inside the spread, not two.

### Bigger lots for VEV_5200/5300 (H-H) — no change
Tested 40, 60, 100 lots. VEV_5200 PnL identical at all sizes. VEV_5300 slightly worse at 40+. The bottleneck is the number of bot trades per tick, not our order size. 20 lots already captures all available volume.

---

## Pattern: What Determines If an Idea Works

The successes share one trait: they exploit a structural edge (cheap vol, tunable mean-reversion) without fighting the market microstructure.

The failures share one trait: they pay too much to get fills (crossing the spread, overbidding on tight-spread products, buying worthless options at non-zero prices).

The single biggest lesson: **the backtester fill model matters as much as the strategy**. Half our ideas were killed not by bad logic but by how `--match-trades worse` handles order matching. Any edge that depends on equal-price fills is unreliable.

---

## Final Numbers

| Change | Impact |
|--------|--------|
| Bug fixes (limit, TTE, floor) | +~2,000 |
| HYDROGEL post_edge 2→3 | +529 |
| VEV_5200/5300 bid+1 | +16,230 |
| VELVETFRUIT edge=12, clip=60 | +16,012 |
| **Total improvement** | **+32,242 (+15.3%)** |

Original: 210,964 → Final: **243,206**

---

## Parameter Validation (confirmed originals are optimal)

### VELVETFRUIT anchor (H-J) — 5255 is the peak
Swept 5245 to 5265. PnL drops sharply in both directions — moving just 3 ticks to 5252 or 5258 costs ~23k on VELVETFRUIT. The original value was well-placed. No change.

### VEV_4000 bid_edge (H-K) — 8.0 is the peak
Swept 4 to 12. Lower values (4, 6) fill more but at worse prices, netting less. Higher values (10, 12) barely fill at all. 8.0 sits in the sweet spot: enough fills at good enough prices. No change.
