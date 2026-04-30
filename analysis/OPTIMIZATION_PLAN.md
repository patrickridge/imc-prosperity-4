# V8 Optimization Plan

## Current Status
- **V8A (Snackpack Edge): 51,276.66** ✅ BETTER
- **V8B (Blackholes 50): 50,082.15**
- Margin: +1,194 units (~2.4% edge)

## Root Cause Analysis

### Why V8A Wins
1. **Product-specific spreads**: Snackpack edges tuned per product
   - High-volume (Vanilla, Strawberry): edge=8 (wider for liquidity)
   - Low-volume (Chocolate, Pistachio): edge=2 (tight for scalping)
   - This is market-microstructure optimization

2. **Conservative BLACK positioning**: Limit=10, Target=10
   - Reduces execution risk
   - Better risk-adjusted returns

### Why V8B Underperforms
1. **Uniform Snackpack edge (8)**: Loses product granularity
   - Vanilla/Strawberry: overly conservative (should be wider)
   - Chocolate/Pistachio: overly aggressive (should be tighter)

2. **Aggressive BLACK**: Limit=60, Target=50
   - Creates execution friction on large positions
   - May hit position limits mid-trade
   - Concentrated risk on single product

## V9 Optimization Strategy

### Approach 1: Hybrid (Recommended)
```
- Keep V8A's per-product Snackpack edges as verified core
- Test BLACK targets: 10 → 20 (mid-point between v8a/v8b)
- Test Garlic (galaxy/oxygen pair): increase from 10 → 15
- Result: Preserve winning Snackpack logic + selective aggression
```

### Approach 2: Snackpack + Galaxy Focus
```
- Keep Snackpack per-product edges (proven)
- Disable aggressive BLACK entirely
- Shift capital to Galaxy/Oxygen overlays
- Test whether Galaxy has better risk-reward than BLACK
```

### Approach 3: Edge Re-tuning
```
- Keep per-product concept
- Test edge values: 8→10, 2→3 (widen slightly across board)
- Purpose: Capture more spread while maintaining product specificity
- Risk: May overfit to current market regime
```

## Next Steps
1. Create V9 with Approach 1 (safest)
2. Run backtest on R5 all days
3. Compare to v8a: target +500 units (1% improvement)
4. If successful, iterate on BLACK/Garlic tuning
