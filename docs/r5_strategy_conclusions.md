# Round 5 Strategy Conclusions

## Current Submission: `strategies/main_submission.py`

8 sub-traders bundled inline (base64). Total OOS PnL on Day 4 log 575780: **+50,082**.

## Sub-Trader Summary

**pebbles (+16,868)** — Family-rotation relative-value across 5 PEBBLES. EWMA residuals from family mean, pair trades when z-gap > 2.35. XL is the main profit source (+10,450). S looks like a loser standalone but is likely the profitable leg of pairs — needs trade-level diagnostics before blocking.

**fallback_mm (+15,024)** — Generic OBI-skewed MM on 14 unclaimed products (TRANSLATORs, SLEEP_PODs, ROBOTs, spare PANELs, UV_VISOR_YELLOW). Biggest contributor by product count. Three bleeders: TRANSLATOR_SPACE_GRAY (-1,315), SLEEP_POD_LAMB_WOOL (-1,114), PANEL_1X2 (-1,086). LAMB_WOOL has structural whipsaw issues — high reversal frequency makes MM unprofitable.

**uv_visor (+7,113)** — EMA trend-following pairs. Core: long RED / short AMBER. Overlay: long MAGENTA / short ORANGE. YELLOW deliberately skipped (unstable historically, but it's also in fallback_mm where it loses -447).

**microchip (+5,698)** — OBI-skewed MM on 5 shapes. Solid, consistent, no issues. Edge=2.

**panel_spread (+2,203)** — Pairs trade PANEL_1X4 vs PANEL_2X2 on rolling z-score. Entry z=2.5, exit z=0. Drift filter blocks entries when spread moves >250 over 100 ticks. 1X4 wins (+2,454), 2X2 loses (-251).

**galaxy_oxygen (+1,976)** — Directional positioning on 10 GALAXY/OXYGEN products. Buy-and-hold BLACK_HOLES and GARLIC. Slope-triggered shorts on SOLAR_FLAMES, PLANETARY_RINGS, SOLAR_WINDS. Dip-buy on DARK_MATTER. Delayed entries on CHOCOLATE, EVENING, MORNING. 8 of 10 products at zero PnL — most directional logic not firing on Day 4. BLACK_HOLES losing -732.

**snackpack (+1,200)** — OBI-skewed MM on 4 SNACKPACKs. Per-product edges: VANILLA/STRAWBERRY=8 (wider), CHOCOLATE/PISTACHIO=2 (tighter). V8A's key differentiator vs V8B (+1,194 improvement from per-product tuning).

**robot_dishes (+0)** — Regime-switching MM. Not trading at all — regime switch never triggers.

## What Worked

- Per-product edge tuning on SNACKPACKs: +1,194 vs uniform edges
- Pebbles family-rotation: strongest single sub-trader
- Simple OBI-skewed MM on wide product baskets (fallback_mm, microchip)
- Panel spread z-score pairs with drift filter

## What Didn't Work / Risks

- Galaxy/Oxygen directional bets: BLACK_HOLES and GARLIC are the biggest risk; large losses possible OOS
- Robot dishes regime switch: never fires, contributes nothing
- SLEEP_POD_LAMB_WOOL: structurally unsuitable for simple MM (high whipsaw)
- UV_VISOR_YELLOW: overlap between uv_visor and fallback_mm
- 14 products at zero PnL (intentionally skipped or broken triggers)

## Open Questions

1. Should galaxy_oxygen directional bets be disabled or gated more conservatively?
2. Is PEBBLES_S actually losing money, or is it the profitable leg of pairs?
3. Can fallback_mm bleeders be fixed by skipping those products, or do they need product-specific logic?
4. Robot dishes — debug or remove?
