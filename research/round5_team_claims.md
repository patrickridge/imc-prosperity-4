---
purpose: Round 5 work split — who's claiming what, current status
date: 2026-04-29
update: edit this file directly when claiming or finishing a strategy
---

## Algo strategies — claims and status

| Category / Product | Owner | Strategy file | Status | Backtest PnL (3 days) |
|---|---|---|---|---|
| **PEBBLES** | Kaushal | `strategies/pebbles.py` | live, iterating | ? (not run by me) |
| **SNACKPACK** (5 products) | Patrick | `strategies/r5_snackpack_mm.py` | tuned, ready | **+14,640** |
| **ROBOT_DISHES** | Patrick | `strategies/r5_robot_dishes_mr.py` | v2 regime switch | **+14,495** |
| **PANEL_1X4 ↔ 2X2 spread** | Patrick | `strategies/r5_panel_spread.py` | tuned via sweep | **+7,280** (day 3 hurts: -25k) |
| **MICROCHIP** | Kaushal | — | researching, possibly lead-lag | — |
| **GALAXY long bias** | Kaushal | — | researching BLACK_HOLES + others | — |
| **OXYGEN long bias** | Kaushal | — | researching GARLIC + others | — |
| **Manual** | Lev (suggested) | `manual/round5/sentiment_estimates.py` | numbers ready, needs submission | recommended +35,156 |
| **Fallback MM** (30 unclaimed products) | Patrick | `strategies/r5_fallback_mm.py` | shipped | **+118,531** |

## Categories nobody is on

- **UV_VISORs** (5 products) — H6 mm_score 130–145, decent MM candidates
- **TRANSLATORs** (5 products) — H6 mm_score ~130, decent MM candidates
- **SLEEP_PODs** (5 products) — H6 mm_score ~130, deeper but less-discussed
- **Other ROBOTs** (4 products: VACUUMING, MOPPING, LAUNDRY, IRONING)
- **Other GALAXY_SOUNDS** (4 products if Kaushal takes BLACK_HOLES)
- **Other OXYGEN_SHAKEs** (4 products if Kaushal takes GARLIC)
- **Other PANEL** (3 products: 1X2, 2X4, 4X4 — independent per H3)

A multi-product fallback MM (`strategies/r5_fallback_mm.py`) covers most of these with simple OBI-skewed quotes.

## Findings worth sharing

- **H5b just confirmed**: MICROCHIP_CIRCLE leads SQUARE, TRIANGLE, OVAL at lags 50–200 ticks, corr ~+0.05. Weak but stable. `research/round5_h5b_microchip_lags.py`.
- **PEBBLES_XL is the most mean-reverting product in the round** (Hurst 0.424). Validates the MR approach.
- **ROBOT_DISHES has lag-1 ACF of −0.22**, strongest reversal anywhere.
- **No within-category lead-lag** at short lags (H5) — only the longer-lag CIRCLE leadership above.
- **Trade size carries no information** (H12) — abnormal-size flagging won't substitute for missing trader IDs.

## How to claim something

1. Add a row to the table above (or update an existing one)
2. Push to `round5/eda` (no PR needed for claim updates — just push)
3. Drop a note in slack so the team sees it
