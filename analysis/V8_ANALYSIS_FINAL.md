# V8A vs V8B Analysis - FINAL

## Performance
- **V8A: 51,276.66** ✓ Winner
- **V8B: 50,082.15**
- **Edge: +1,194 units (+2.39%)**

## Root Cause: Snackpack Per-Product Edges
V8A's optimization: differentiated spreads by product liquidity
```
VANILLA, STRAWBERRY (high volume)    → edge = 8 (wider)
CHOCOLATE, PISTACHIO (low volume)    → edge = 2 (tight)
```

V8B's simplification: uniform edge = 8 across all (loses optimization)

## Position Limits Reality Check
- Competition hard cap: 10 units per product
- V8A sets target: 10 (uses available limit efficiently)
- V8B sets target: 50 (pointless, capped at 10 anyway)
- Both hit same actual position, but V8A's logic is cleaner

## Why V8A Wins
1. **Product-specific spread tuning** — captures market microstructure
2. **Cleaner position logic** — no over-specification
3. **Snackpack dominates the edge** — these 4 products drive the win

## Next Steps for V9
### Option A: Hybrid (Safe)
- Keep V8A's Snackpack edges (proven +1,194)
- Test wider BLACK target (20 instead of 10)
- Expected: +500-1000 units more

### Option B: Focus Snackpack Only
- Disable BLACK/GARLIC trades entirely
- Maximize Snackpack capital
- Expected: +200-500 units more (but riskier)

### Option C: Snackpack + Parameter Scan
- Keep Snackpack edges
- Test edge values: 8→9, 2→3 (micro-tuning)
- Expected: +100-300 units (incremental)

**Recommendation**: A (Hybrid) is safest. Has proven 1,194 unit base, adds incremental BLACK/GARLIC exposure.
