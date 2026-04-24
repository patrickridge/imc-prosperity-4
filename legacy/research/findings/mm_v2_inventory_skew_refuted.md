---
product: EMERALDS, TOMATOES
date: 2026-04-11
status: refuted
hypothesis: Position pinning at +80 caps round-trip throughput; inventory skew that shifts both quotes toward unwinding will reopen buy quota and increase PnL.
test: Clone mm_v1 → mm_v2 with SKEW_PER_UNIT=0.1 applied to both buy_price and sell_price in make_orders; backtest round 0 days -2 and -1; compare per-product PnL, pin time, and fill counts.
result: refuted
---

## Why we looked

Baseline mm_v1 on round 0 days -2 and -1 totalled 29,414 (EMERALDS 14,525, TOMATOES 14,889). All EMERALDS PnL came from making — the book never has asks < 10,000 or bids > 10,000 in any of 20,000 snapshots, and every fill is at 9,993 / 10,007. EMERALDS pinned at +80 on 824 ticks (4.1% of day), TOMATOES on 415 (2.1%). Never hit −80.

Pinning *looked* like a throughput bottleneck: during pin windows `buy_qty = POSITION_LIMIT - position = 0`, so no new buy orders were placed. The hypothesis was that freeing the buy quota via faster unwinding would add round-trips at full edge.

## What we measured

mm_v2 vs mm_v1 on the same 2 days:

| product  | v1     | v2     | delta   |
|----------|--------|--------|---------|
| EMERALDS | 14,525 | 12,301 | −15%    |
| TOMATOES | 14,889 | 13,867 | −7%     |
| total    | 29,414 | 26,168 | **−11%**|

Mechanism check (pin elimination): pin@+80 went **824 → 0** (EMERALDS) and **415 → 0** (TOMATOES). The skew did exactly what it was designed to do.

EMERALDS fill comparison:
- v1: 1,027 buys all at 9,993; 1,048 sells all at 10,007. Per-round-trip edge = 14.
- v2: 917 buys across 9,992–9,995; 952 sells across 9,999–10,008. Per-round-trip edge ≈ 12.

Both the edge per trade (14 → 12) **and** the fill count (2,075 → 1,869) dropped.

## What we found

Pinning was not a throughput bottleneck. It was a symptom of flow bursts that reversed naturally at full edge — the strategy earned the full 14-seashell edge on every round-trip during pin windows. Skewing quotes to avoid pinning gave up edge per trade AND reduced fill frequency, because the skewed bid/ask moved further from the competitive 9,993/10,007 levels. Both terms moved the wrong way.

Root cause of the misdiagnosis: "time pinned" was measured and treated as implying "fills missed during pin". Those are different quantities. Time-at-pin is easy to measure; fills-missed requires counting counterparty flow that would have been takeable but wasn't — and that count was never produced.

Side observation worth keeping (not part of this finding): EMERALDS sold 198 units at 10,008 in the v2 run when skew pushed the ask above the usual 10,007. This suggests counterparties are partially price-insensitive within the spread, which is a forward hypothesis for a *wider*-quote strategy. To be logged separately when that hypothesis is tested.

## How it informs the code

`strategies/mm_v1.py` is unchanged; mm_v2 was deleted, not merged. The `fair ± 1` quote placement in `make_orders` (mm_v1.py:60–61) is earning the full spread and should not be disturbed without an explicit measurement of fills-missed.

## Gate measurement (2026-04-12)

The refutation's retire condition ("direct measurement of counterparty flow crossing fair while pinned") was run against the v1 baseline log:

|                   | pin ticks | missed takeable volume |
|-------------------|-----------|------------------------|
| EMERALDS (long)   |       824 |                      0 |
| TOMATOES (long)   |       415 |                    147 |

- **EMERALDS: absolute zero.** No ask ever appears below 10,000 during any of the 824 pin windows. Refutation stands without modification.
- **TOMATOES: 147 units across 415 ticks** (~0.35/tick avg, occasional clusters of 9–11). Gate is technically crossed.

**Arithmetic still says no.** Max theoretical recoverable ≈ 147 × (wall_mid − ask) ≈ order of 300 seashells if the missed asks sat ~2 below fair on average. mm_v2 lost **1,022 seashells on TOMATOES** to skew-driven edge erosion. Recoverable < loss. Broad inventory skew remains a losing trade even with the evidence.

Diagnostic note: the first run of this measurement returned `0` on both products due to a regex bug (literal `\n` decode + greedy `\w+` captured product name as `nTOMATOES`, which failed the book lookup). Fixed and rerun before interpretation. "Zero matches" is only trustworthy when the unmatched count is also zero.

## When to retire

**Broad inventory skew** (the mm_v2 mechanism — symmetric shift applied to both quotes every tick) is **refuted permanently**. Do not retry any `SKEW_PER_UNIT`-style parameter; the measurement shows there is no recoverable edge on EMERALDS and the TOMATOES recoverable is smaller than the per-tick edge erosion the mechanism causes elsewhere.

**Targeted take-priority during pins** was considered as a separate hypothesis: when `position == +POSITION_LIMIT` AND a takeable ask appears, free one unit by crossing our own make-quote and take the ask in the same tick. **Ruled out (2026-04-12)** — the Prosperity exchange enforces position limits by checking `position + total_buy_qty > LIMIT` across all submitted orders assuming full execution. Any buy order while at +POSITION_LIMIT causes all orders for the product to be rejected, regardless of concurrent sell orders. A two-tick variant (aggressive sell on tick T, take on tick T+1) doesn't work either because the takeable ask observed on tick T is not guaranteed to persist to tick T+1. The 147 TOMATOES units are not recoverable without a mechanism that can atomically sell-then-buy within a single tick, which the exchange does not support.
