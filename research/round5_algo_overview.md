---
round: 5
date: 2026-04-28
status: scoping
hypothesis: 50 new products in 10 categories of 5 — pattern lives within categories, not across
---

## What's new in Round 5 algo

- **50 brand-new products** replacing all prior ones. KELP, RESIN, INK, baskets, vouchers, MAGNIFICENT_MACARONS, AETHER_CRYSTAL — all gone for algo trading.
- **Position limit: 10 per product** (tiny vs prior rounds' 50–250).
- **3 days of backtest data**: `data/round5/{prices,trades}_round_5_day_{2,3,4}.csv`.
- Wiki quote: *"Each group has its own story… some offer more market inefficiencies than others. In certain groups, strong patterns are embedded in price movements."*

## The 10 categories (5 products each)

| Category | Variants |
|---|---|
| Galaxy Sounds Recorders | DARK_MATTER, BLACK_HOLES, PLANETARY_RINGS, SOLAR_WINDS, SOLAR_FLAMES |
| Vertical Sleeping Pods | SUEDE, LAMB_WOOL, POLYESTER, NYLON, COTTON |
| Organic Microchips | CIRCLE, OVAL, SQUARE, RECTANGLE, TRIANGLE |
| Purification Pebbles | XS, S, M, L, XL |
| Domestic Robots | VACUUMING, MOPPING, DISHES, LAUNDRY, IRONING |
| UV-Visors | YELLOW, AMBER, ORANGE, RED, MAGENTA |
| Instant Translators | SPACE_GRAY, ASTRO_BLACK, ECLIPSE_CHARCOAL, GRAPHITE_MIST, VOID_BLUE |
| Construction Panels | 1X2, 2X2, 1X4, 2X4, 4X4 |
| Liquid Breath Oxygen Shakes | MORNING_BREATH, EVENING_BREATH, MINT, CHOCOLATE, GARLIC |
| Protein Snack Packs | CHOCOLATE, VANILLA, PISTACHIO, STRAWBERRY, RASPBERRY |

## First-look findings (3 days combined)

Run [`research/round5_explore.py`](round5_explore.py) for the full table. Headlines:

### Biggest 3-day drifts (these are TREND signals, not noise)

| Product | 3-day drift | Direction |
|---|---|---|
| PEBBLES_XL | **+60.7%** | strong long |
| MICROCHIP_OVAL | **−44.8%** | strong short |
| PEBBLES_XS | **−39.6%** | strong short |
| OXYGEN_SHAKE_GARLIC | +38.9% | long |
| MICROCHIP_SQUARE | +36.3% | long |
| GALAXY_SOUNDS_BLACK_HOLES | +34.6% | long |
| UV_VISOR_AMBER | −28.7% | short |
| ROBOT_IRONING | −21.7% | short |

### Category dispersion (mean range_pct)

`PEBBLES (48%) > MICROCHIP (41%) > SLEEP_POD ≈ UV_VISOR ≈ OXYGEN_SHAKE ≈ PANEL ≈ ROBOT ≈ GALAXY_SOUNDS (~25%) > TRANSLATOR (22%) > SNACKPACK (12%)`

**SNACKPACKs are dead** — half the volatility of the next-quietest group. Skip.

### Pair-trade smell tests (UPDATED — see H1 below)

- 3-day combined: PEBBLES_XL ↔ XS corr **−0.83**, MICROCHIP_SQUARE ↔ OVAL combined corr **−0.73**.
- **Day-by-day breakdown reveals these are NOT stable pairs.** See `round5_h1_pair_drift.py`.

## Hypothesis tests

### H1: Pair-trade stability (`round5_h1_pair_drift.py`)

| Pair | Day 2 corr | Day 3 corr | Day 4 corr | Verdict |
|---|---|---|---|---|
| PEBBLES_XL / PEBBLES_XS | **−0.875** | **+0.015** | **−0.829** | Pair breaks on day 3 — DO NOT trade as static pair |
| MICROCHIP_SQUARE / OVAL | +0.076 | −0.836 | +0.611 | Highly unstable, only one day shows the negative correlation |

The combined-3-day correlation was misleading. Daily correlation is unreliable for both pairs.

### H2: Drift persistence (`round5_h2_drift_persistence.py`)

| Product | Day 2 | Day 3 | Day 4 | Verdict |
|---|---|---|---|---|
| **PEBBLES_XS** | −19.5% | −14.9% | −12.0% | Cleanest: every day negative, monotonic short |
| **MICROCHIP_OVAL** | −7.4% | −19.7% | −25.6% | All 3 days negative, accelerating short |
| **GALAXY_SOUNDS_BLACK_HOLES** | +14.5% | +6.0% | +10.9% | Steady positive trend |
| PEBBLES_XL | +36.7% | −11.4% | +33.3% | Net long but reverses on day 3 — directional bets risky |
| MICROCHIP_SQUARE | +24.6% | +27.6% | −14.3% | Two days strong long, day 3 reversal |
| OXYGEN_SHAKE_GARLIC | +18.3% | +0.9% | +16.4% | Weak trend, day 3 flat |
| UV_VISOR_AMBER | −15.0% | −13.0% | −3.5% | Weak short trend, fading |
| ROBOT_IRONING | −4.9% | −21.0% | +4.4% | Reversing; market-make only |

### H3: PANEL basket relationships (`round5_h3_panel_basket.py`)

Tested whether PANEL prices are linked by area (1X4 = 2X2 = 4 sq units, etc.).

**Result: only one relation has any merit.**

| Relation | Day 2 mean | Day 3 mean | Day 4 mean | Verdict |
|---|---|---|---|---|
| **PANEL_1X4 ≈ PANEL_2X2** (both 4 sq) | +216 | −535 | −218 | Spread is small (~2-5%), mean-reverting → potential pair trade |
| PANEL_2X4 ≈ 2 × PANEL_2X2 | −8900 | −9127 | −5636 | Way off zero — not a basket |
| PANEL_4X4 ≈ 4 × PANEL_2X2 | −29187 | −31120 | −24975 | Same — products priced independently |

PANELs are NOT priced linearly by area. The only tradeable relationship is the 1X4↔2X2 spread, and even that drifts day-to-day.

## Bots / trader IDs in R5

**R5 trades CSVs have NO trader IDs.** Verified across all 35,385 trades on days 2/3/4 — buyer/seller fields are all empty (R4 had IDs on every row).

This kills the Olivia-style copy-trade approach (`round4_v1_olivia.py`) for R5. All R5 strategies must be statistical / TA-based, no counterparty signal.

## Compared to P2/P3 round 5

| | P2 R5 | P3 R5 | P4 R5 |
|---|---|---|---|
| # products | ~9 | ~15 | **50** (10 categories × 5) |
| Mechanic | Cross-year data mapping (P1 prices predicted P2) + bot signals (Vladimir, Remy, Rihanna, Vinnie) | Trader IDs revealed → Olivia copy-trading | New product taxonomy, **no trader IDs** |
| Counterparty info | Named bots, deterministic signals | Trader IDs in CSVs | None (anonymized) |
| Manual challenge | News-driven portfolio (similar) | News-driven portfolio (similar) | News-driven portfolio (same shape) |

The 10-categories × 5-variants structure is **new to P4 R5** — no precedent in P2 or P3. The manual news challenge is recurring across all three comps.

Implication: don't try to port `round4_v1_olivia.py` or P3 Olivia patterns. Lean on within-category structure (PANELs, PEBBLES, MICROCHIP) instead.

## Strategy direction

The wiki promised *"strong patterns embedded in price movements"* — confirmed, but H1/H2/H3 sharpen what's tradeable:

1. **Cleanest directional shorts**: PEBBLES_XS, MICROCHIP_OVAL — every day negative, no reversals. Highest-conviction trend trades.
2. **Cleanest directional long**: GALAXY_SOUNDS_BLACK_HOLES — steady positive every day.
3. **PANEL_1X4 ↔ PANEL_2X2 spread** — only viable basket relation; spread is small and mean-reverts.
4. **Avoid as static pair trades**: PEBBLES_XL/XS and MICROCHIP_SQUARE/OVAL — correlation breaks intraday.
5. **Risky directionals**: PEBBLES_XL, MICROCHIP_SQUARE — strong overall but reversal days hurt.
6. **No bot signals available** — strategies must be pure statistical / market-making / trend-following.
3. **Market-make the SNACKPACKs and TRANSLATORs** for steady tick income.
4. **Ignore** anything under 15% range with no obvious pair.

## Tooling status

- ✅ `data/round5/` populated (3 days of prices + trades CSVs)
- ✅ `backtester/data.py` LIMITS extended for all 50 products at limit=10
- ✅ Dashboard auto-discovers `data/round5/` via existing glob — no code change needed
- ✅ `research/round5_explore.py` for the per-product / per-category summary

## Open questions

- [ ] Does PANEL_1X2 + PANEL_1X2 ≈ PANEL_2X2 (or PANEL_1X4)? Test composition arb explicitly.
- [ ] Are the trades CSVs revealing trader IDs as in P3 R5? If yes, look for an Olivia-style informed counterparty.
- [ ] Are the drift signals stable when you walk the data forward day-by-day, or front-loaded into one day?
