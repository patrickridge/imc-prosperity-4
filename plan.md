# V10 Plan — Disable losers + hypothesis exploration

## Step 1: Disable V9 losers (P0 recovery)
Apply to sub-strategy source files in research/r5_baseline/:

- sub_galaxy_oxygen.py: set ENABLE=False for SOLAR_FLAMES, DARK_MATTER, SOLAR_WINDS, CHOCOLATE
- sub_robot_dishes.py: revert to noop (return empty orders)
- sub_snackpack.py: remove RASPBERRY from PRODUCTS list

Expected recovery: ~+9,500 vs V9 (back above V8A baseline)

## Step 2: Rebuild bundle
Run build_r5_submission.py to produce strategies/round5_v10.py

## Step 3: Submit and compare
Submit V10 to OOS, compare against both 575780 (V8A) and 578611 (V9)

## Step 4: Hypothesis loop on remaining bleeders
Pick one bleeder at a time, form hypothesis, test via OOS, log result.
Candidates:
- Fallback MM bleeders (TRANSLATOR_SPACE_GRAY, SLEEP_POD_LAMB_WOOL, PANEL_1X2)
- UV_VISOR_YELLOW
- Unlocking MINT, MORNING_BREATH, ORANGE, MAGENTA, IRONING
