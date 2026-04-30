# R5 Strategy Development

## Workflow
```
1. Edit source:        research/r5_eda/sub_*.py
2. Build bundle:       python3 research/build_r5_submission.py
3. Wrap for upload:    ./submit.sh strategies/round5_v9_patched.py
4. Upload:             submissions/round5_v9_patched.py → prosperity.imc.com
5. Download OOS zip:   drop in strategies/ or logs/
6. Diagnose:           python3 utils/analyze_logs.py <new.zip>
7. Diff vs previous:   python3 utils/analyze_logs.py <old.zip> <new.zip>
8. Fix worst bleeder, go to step 1
```

Rule: change ONE sub-strategy per iteration so the diff is clean.

## Baseline
- 575780.zip = last confirmed OOS (50,082 PnL)
- Decoded: research/decoded_575780/

## Current submission (v9)
Changes vs 575780:
- snackpack: added RASPBERRY, per-product edge (CHOC/PIST=7, VAN/STRAW/RASP=8)
- robot_dishes: re-enabled (was dead code returning empty)
- galaxy_oxygen: fixed BLACK limit bug (60→10), all thresholds ÷10
- panel_spread, microchip, uv_visor, fallback_mm, pebbles: unchanged

## Key files
- research/r5_eda/sub_*.py — source of truth (8 sub-strategies)
- strategies/bundle_template.py — combiner boilerplate (don't edit)
- research/build_r5_submission.py — build script
- utils/analyze_logs.py — OOS log analysis + diff tool

---

# OOS Feedback — Log 575780 (Day 4)

**Total PnL: +50,082**

## Per-Product Breakdown

### LOSING money (fix these first)

| Product | PnL | Sub-strategy | Notes |
|---|---:|---|---|
| TRANSLATOR_SPACE_GRAY | -1,315 | fallback_mm | worst single product |
| SLEEP_POD_LAMB_WOOL | -1,114 | fallback_mm | |
| PANEL_1X2 | -1,086 | fallback_mm | |
| GALAXY_SOUNDS_BLACK_HOLES | -732 | galaxy_oxygen | directional long — wrong direction? |
| SNACKPACK_CHOCOLATE | -499 | snackpack | edge=2 too tight? |
| UV_VISOR_YELLOW | -447 | uv_visor | in both uv_visor AND fallback_mm? |
| PANEL_2X2 | -251 | panel_spread | spread trade losing leg |

**Total bleeding: -5,444**

### WINNING money

| Product | PnL | Sub-strategy |
|---|---:|---|
| PEBBLES_XL | +10,450 | pebbles |
| UV_VISOR_AMBER | +5,880 | uv_visor |
| SLEEP_POD_COTTON | +2,737 | fallback_mm |
| OXYGEN_SHAKE_GARLIC | +2,708 | galaxy_oxygen |
| PANEL_1X4 | +2,454 | panel_spread |
| PEBBLES_M | +2,405 | pebbles |
| SLEEP_POD_POLYESTER | +2,163 | fallback_mm |
| TRANSLATOR_GRAPHITE_MIST | +2,175 | fallback_mm |
| PANEL_4X4 | +2,151 | fallback_mm |
| PEBBLES_L | +2,074 | pebbles |
| ROBOT_LAUNDRY | +2,041 | fallback_mm |
| MICROCHIP_TRIANGLE | +1,963 | microchip |
| PANEL_2X4 | +1,878 | fallback_mm |
| MICROCHIP_SQUARE | +1,774 | microchip |
| UV_VISOR_RED | +1,680 | uv_visor |
| PEBBLES_S | +1,324 | pebbles |
| SLEEP_POD_NYLON | +1,320 | fallback_mm |
| TRANSLATOR_ASTRO_BLACK | +1,186 | fallback_mm |
| TRANSLATOR_ECLIPSE_CHARCOAL | +1,012 | fallback_mm |
| SNACKPACK_VANILLA | +928 | snackpack |
| TRANSLATOR_VOID_BLUE | +851 | fallback_mm |
| SNACKPACK_STRAWBERRY | +771 | snackpack |
| ROBOT_VACUUMING | +715 | fallback_mm |
| MICROCHIP_OVAL | +699 | microchip |
| MICROCHIP_RECTANGLE | +692 | microchip |
| PEBBLES_XS | +614 | pebbles |
| MICROCHIP_CIRCLE | +569 | microchip |
| ROBOT_MOPPING | +157 | fallback_mm |
| SLEEP_POD_SUEDE | +154 | fallback_mm |

### NOT TRADED (zero PnL)

GALAXY_SOUNDS_PLANETARY_RINGS, GALAXY_SOUNDS_SOLAR_WINDS,
GALAXY_SOUNDS_SOLAR_FLAMES, GALAXY_SOUNDS_DARK_MATTER,
OXYGEN_SHAKE_MINT, OXYGEN_SHAKE_CHOCOLATE, OXYGEN_SHAKE_MORNING_BREATH,
OXYGEN_SHAKE_EVENING_BREATH, UV_VISOR_ORANGE, UV_VISOR_MAGENTA,
ROBOT_DISHES, ROBOT_IRONING, SNACKPACK_PISTACHIO, SNACKPACK_RASPBERRY

## By Sub-Strategy (aggregated)

| Sub-strategy | PnL | Products | Key issue |
|---|---:|---:|---|
| pebbles | +16,868 | 5 | Star performer |
| fallback_mm | +15,024 | 14 | Big but 3 bleeders drag it down |
| uv_visor | +7,113 | 5 | YELLOW losing -447 |
| microchip | +5,698 | 5 | Solid |
| panel_spread | +2,203 | 2 | PANEL_2X2 losing, PANEL_1X4 winning |
| galaxy_oxygen | +1,976 | 10 | BLACK_HOLES -732; 8 products at zero |
| snackpack | +1,200 | 4 | CHOCOLATE -499 |
| robot_dishes | +0 | 1 | Not trading at all |

## Action Items

- [ ] Investigate fallback_mm bleeders: TRANSLATOR_SPACE_GRAY, SLEEP_POD_LAMB_WOOL, PANEL_1X2
- [ ] Fix GALAXY_SOUNDS_BLACK_HOLES — directional long losing; check if trend reversed OOS
- [ ] SNACKPACK_CHOCOLATE edge=2 too tight — widen or skip
- [ ] UV_VISOR_YELLOW conflict — appears in both uv_visor and fallback_mm sub-strategies
- [ ] ROBOT_DISHES making zero — is the regime switch never triggering?
- [ ] 14 products at zero PnL — are these intentionally skipped or broken?
- [ ] Galaxy/Oxygen: 8 of 10 products at zero — most of the directional logic not firing
