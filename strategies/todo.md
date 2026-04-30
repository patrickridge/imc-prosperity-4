# R5 Strategy Changelog & TODO

## Submission log

### V8A (575780) — Baseline: +50,082
No changes. First instrumented OOS run.

### V9 (578611) — Result: +44,774 (delta: -5,308)
Changes made:
1. Snackpack: added RASPBERRY, per-product edge (CHOC/PIST 2→7, VAN/STRAW/RASP=8)
2. Galaxy/Oxygen: all windows and thresholds ÷10 (activate for 1k-tick OOS)
3. Robot Dishes: wired up regime-switch MM (was noop returning empty dict)

What worked:
- SNACKPACK_PISTACHIO: 0 → +500 (edge widening let it trade profitably)
- SNACKPACK_CHOCOLATE: -499 → -331 (edge widening reduced adverse selection)
- GALAXY_SOUNDS_PLANETARY_RINGS: 0 → +3,006 (÷10 windows activated, strong winner)
- OXYGEN_SHAKE_EVENING_BREATH: 0 → +320 (÷10 windows activated, small win)

What backfired:
- GALAXY_SOUNDS_DARK_MATTER: 0 → -5,078 (÷10 activated but signal is WRONG)
- ROBOT_DISHES: 0 → -1,871 (regime MM trading but losing badly)
- OXYGEN_SHAKE_CHOCOLATE: 0 → -890 (signal wrong direction)
- GALAXY_SOUNDS_SOLAR_WINDS: 0 → -720 (signal wrong)
- GALAXY_SOUNDS_SOLAR_FLAMES: 0 → -580 (signal wrong)
- SNACKPACK_RASPBERRY: 0 → -454 (added but losing — MM edge not wide enough?)

Net by change:
- Galaxy/Oxygen ÷10:  -3,942 (4 losers, 2 winners)
- Robot Dishes wired:  -1,871
- Snackpack fixes:       +214 (PISTACHIO +500, CHOC +168, RASP -454)
- Noise (unchanged code): +291 (panel, pebbles, uv minor variance)

Lesson: activating previously-dead code without verifying signal direction
on OOS data is destructive. The ÷10 fix was correct mechanically but the
directional signals themselves are wrong for several products.

## TODO — V10 fixes

### P0: Revert harmful activations (-7,684 recoverable)

1. Galaxy/Oxygen: disable the 4 losing products
   DARK_MATTER, SOLAR_WINDS, SOLAR_FLAMES, OXYGEN_SHAKE_CHOCOLATE
   Keep PLANETARY_RINGS (+3,006) and EVENING_BREATH (+320) active.
   BLACK_HOLES and GARLIC unchanged (were active in V8A already).
   Expected recovery: +7,268

2. Robot Dishes: revert to noop (or fix parameters)
   Regime MM is losing -1,871. Either disable or research correct params.
   Expected recovery: +1,871

3. Snackpack RASPBERRY: disable or widen edge
   Losing -454 with edge=8. Either remove or try edge=12+.
   Expected recovery: +454

### P1: Fix existing bleeders (carried from V8A, -3,962 total)

4. Fallback MM bleeders: TRANSLATOR_SPACE_GRAY (-1,315),
   SLEEP_POD_LAMB_WOOL (-1,114), PANEL_1X2 (-1,086)
   All use global EDGE=3. Likely adverse selection on tight-spread products.
   Test: per-product edge, or exclude the 3 worst.

5. UV_VISOR_YELLOW (-447): in fallback_mm with EDGE=3, excluded from uv_visor
   as "unstable". Remove from fallback_mm entirely.

### P2: Unlock new PnL

6. OXYGEN_SHAKE_MINT + MORNING_BREATH: not in any sub-strategy.
   Add to fallback_mm or research a dedicated signal.

7. UV_VISOR_ORANGE/MAGENTA: in uv_visor MO overlay but never trigger.
   EMA windows (FAST=100, SLOW=800) may need ÷10 for 1k ticks.

8. ROBOT_IRONING: in fallback_mm list but zero trades. Check order book.

### Decision needed

- Galaxy/Oxygen products that ARE working (PLANETARY_RINGS, EVENING_BREATH,
  GARLIC): keep as-is or research whether signal is robust across days?
- Robot Dishes: kill entirely or invest time fixing regime detection?
