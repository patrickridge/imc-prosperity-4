---
purpose: Round 5 strategy coverage — what's covered, what's not, current PnL
date: 2026-04-29
update: edit this file directly when shipping or changing a strategy
---

## Coverage status

50 products total across 10 categories of 5. Combined runner covers 45 of them.

| Strategy file | Products | 3-day backtest PnL |
|---|---|---|
| `strategies/pebbles.py` | 5 PEBBLES (XS, S, M, L, XL) | (the heavy lifter, ~+204k contribution) |
| `strategies/galaxy_oxygen.py` | 5 GALAXY_SOUNDS + 3 OXYGEN_SHAKEs (8 total) | **+148,114** |
| `strategies/r5_snackpack_mm.py` | 5 SNACKPACKs | **+14,640** |
| `strategies/r5_robot_dishes_mr.py` | ROBOT_DISHES | **+14,495** |
| `strategies/r5_panel_spread.py` | PANEL_1X4 + PANEL_2X2 | **+12,754** |
| `strategies/r5_fallback_mm.py` | 24 quiet products (UV_VISORs, TRANSLATORs, SLEEP_PODs, 4 ROBOTs, 2 OXYGEN_SHAKEs, 3 PANELs) | folded into combined |
| **Combined runner** (all of the above) | 45 products | **+513,216** total |
| **Submission bundle** (`submissions/r5_combined.py`) | same 45 products | **+513,216** (verified identical) |

## Not yet covered

- **5 MICROCHIPs** (CIRCLE, OVAL, SQUARE, RECTANGLE, TRIANGLE) — H5b found CIRCLE leads SQUARE/TRIANGLE/OVAL at lags 50-200 with corr ~0.05. Weak but real.

That's 5/50 still trading at zero in the combined runner.

## Manual

`manual/round5/sentiment_estimates.py` — recommended numbers print to stdout. Plug into the IMC site before round close. Estimated PnL: **+35,156**.

## How to add a new strategy

1. Drop the file in `strategies/`
2. Add it to `strategies/r5_combined.py` `SUB_STRATEGIES` list
3. Add it to `research/round5_build_submission.py` `SUB_MODULES` list
4. Run `python3 research/round5_build_submission.py` to refresh the bundle
5. Backtest the bundle to confirm it still runs: `./backtest.sh submissions/r5_combined.py 5-2`

## Submission

`submissions/r5_combined.py` is the file to upload to the IMC site. Regenerate after any strategy change with the build command above.
