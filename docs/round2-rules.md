# Round 2 — "Growing Your Outpost"

Source: [Prosperity 4 Wiki](https://imc-prosperity.notion.site/345e8453a09380b29132fdf4de9174d4)

## Overview

Final round on Intara. Must reach 200,000 XIRECs threshold before leaderboard resets for Phase 2 (GOAT).
Same products as Round 1, plus a Market Access Fee mechanic and a budget allocation manual challenge.

## Algorithmic Challenge: "Limited Market Access"

### Products & Position Limits

| Product | Limit |
|---------|-------|
| `ASH_COATED_OSMIUM` | 80 |
| `INTARIAN_PEPPER_ROOT` | 80 |

### Market Access Fee (MAF)

- Bid for 25% more quotes in the order book via a `bid()` method in your Trader class
- Top 50% of bids get extra market access; bottom 50% don't pay anything
- One-time fee deducted from Round 2 profit: `PnL = profit - bid` (if accepted)
- Negative bids treated as 0
- Unique to Round 2 — `bid()` ignored in all other rounds

```python
class Trader:
    def bid(self):
        return 15  # your MAF bid

    def run(self, state: TradingState):
        ...
```

### Extra Flow Example

Without MAF: `ask@9(10), ask@7(10), bid@5(10), bid@4(5)`
With MAF: `ask@9(10), ask@8(5)←extra, ask@7(10), bid@5(10), bid@4(5)`

## Manual Challenge: "Invest & Expand"

Budget: 50,000 XIRECs allocated across three pillars (0–100% each, total ≤ 100%).

### PnL Formula

```
PnL = (Research × Scale × Speed) − Budget_Used
```

### Pillars

| Pillar | Growth | Formula / Range |
|--------|--------|-----------------|
| Research | Logarithmic | `200_000 * log(1+x) / log(101)`, 0→0, 100→200,000 |
| Scale | Linear | 0→0, 100→7 |
| Speed | Rank-based | Highest investment → 0.9, lowest → 0.1, linear between by rank |

- Equal speed investments share the same rank
- Teams with no manual submission excluded from speed ranking
