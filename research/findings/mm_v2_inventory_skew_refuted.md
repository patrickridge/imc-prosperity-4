# Findings

Rolling record of what's been measured and what's been ruled out. Read this first before proposing a new strategy direction.

## Baseline — mm_v1

Round 0, days -2 and -1:

| Product  | Day -2 | Day -1 | Total  | ~PnL / limit / day |
|----------|--------|--------|--------|--------------------|
| EMERALDS |  6,958 |  7,567 | 14,525 | ~90                |
| TOMATOES |  7,938 |  6,951 | 14,889 | ~91                |
| **Total**| 14,896 | 14,518 | 29,414 |                    |

Verified from backtest log (not assumed):
- **All EMERALDS PnL is from making**, not taking. The book never has asks < 10,000 or bids > 10,000 in any of 20,000 snapshots; every fill is at 9,993 / 10,007.
- Buy/sell fills are near-symmetric (EMERALDS net −21 across 2 days; TOMATOES net +84, EOD ≈ flat).
- EMERALDS pins at +80 on 824 ticks (4.1%), TOMATOES on 415 (2.1%). Never hits −80.

## Open observations (not yet a hypothesis)

- In the v2 run, TOMATOES (and EMERALDS when short) got fills at `best_ask + 1` — e.g. EMERALDS sold 198 units at 10,008 when skew pushed the ask up. Suggests counterparties are partially price-insensitive within the spread, which means wider-quote strategies may capture more per trade without losing fill count. Not tested.

## Rejected hypotheses

### mm_v2 — inventory skew in make_orders (rejected 2026-04-11)

**Premise:** position pinning at +80 was capping throughput; skewing both quotes down when long would unwind faster, reopen buy quota, and increase round-trip count.

**Change:** `SKEW_PER_UNIT = 0.1`, applied as `skew = -round(position * SKEW_PER_UNIT)` added to both `buy_price` and `sell_price` in `make_orders`.

**Result:**

| Product  | v1     | v2     | delta   |
|----------|--------|--------|---------|
| EMERALDS | 14,525 | 12,301 | −15%    |
| TOMATOES | 14,889 | 13,867 | −7%     |
| **Total**| 29,414 | 26,168 | **−11%**|

**Why it failed:** mechanism worked (pin@+80 went 824 → 0 and 415 → 0) but the premise was wrong. Pinning was not a throughput bottleneck — it was a symptom of flow bursts that reversed naturally at full edge. Skewing quotes away during accumulation dropped per-round-trip edge from 14 → ~12 **and** dropped fill count by ~10%. Both terms moved the wrong way.

**Lesson:** "time pinned" ≠ "fills missed during pinning". I measured the first and assumed the second. The pin was free edge-capture, not a blocker.

**Do not retry** any variant of this (including smaller `SKEW_PER_UNIT`) without first measuring **fills-missed-during-pin directly** — i.e., count counterparty flow that crossed fair while our position was capped. Parameter-tuning SKEW_PER_UNIT without that diagnostic would be tuning the wrong mechanism.
