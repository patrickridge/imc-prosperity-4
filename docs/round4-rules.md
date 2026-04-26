# Round 4 — "The More The Merrier"

Source: [Prosperity 4 Wiki](https://imc-prosperity.notion.site/34ee8453a0938059b604db93deaf0e29)

## Overview

Continue trading `HYDROGEL_PACK`, `VELVETFRUIT_EXTRACT`, and `VELVETFRUIT_EXTRACT_VOUCHER`.
**New this round:** counterparty IDs are now visible in historical trade data.

Manual challenge: trade `AETHER_CRYSTAL` and exotic option contracts.

---

## Algorithmic Challenge: "Hello, I'm Mark"

### What Changed

The `Trade` class now has `buyer` and `seller` fields populated with participant names
(previously `None` in Rounds 1–3). Use this to study counterparty behavior.

```python
class Trade:
    def __init__(self, symbol, price, quantity, buyer=None, seller=None, timestamp=0):
        self.symbol = symbol
        self.price = price
        self.quantity = quantity
        self.buyer = buyer      # NEW: participant name
        self.seller = seller    # NEW: participant name
        self.timestamp = timestamp
```

### Products & Position Limits

| Product                      | Limit |
|------------------------------|-------|
| `HYDROGEL_PACK`              | 200   |
| `VELVETFRUIT_EXTRACT`        | 200   |
| `VELVETFRUIT_EXTRACT_VOUCHER`| 300 per voucher (10 vouchers, strike-based) |

Example: `VEV_5000` = option with strike 5000, TTE = 4 days in R4, limit 300.

---

## Manual Challenge: "Vanilla Just Isn't Exotic Enough"

### Setup

- Underlying: `AETHER_CRYSTAL`
- Simulated via **Geometric Brownian Motion**, zero risk-neutral drift, **annualized vol = 251%**
- Discrete grid: **4 steps per trading day**, 252 trading days/year
- Contract size: 3000 (PnL multiplier only — prices shown are per-option)
- PnL = average across **100 simulations**, marked to fair value at expiry
- **Standalone** — no relation to Round 1

### Time Conventions

```python
TRADING_DAYS_PER_YEAR = 252
STEPS_PER_DAY = 4
STEPS_PER_YEAR = TRADING_DAYS_PER_YEAR * STEPS_PER_DAY

def weeks_to_years(weeks):
    return (weeks * 5) / TRADING_DAYS_PER_YEAR

def steps_for_weeks(weeks):
    return int(round(weeks * 5 * STEPS_PER_DAY))
```

- 1 week = 5 trading days = 20 steps
- 2 weeks = 10 trading days = 40 steps
- 3 weeks = 15 trading days = 60 steps

### Available Products

- `AETHER_CRYSTAL` (underlying)
- Vanilla calls and puts (2-week and 3-week expiry)
- **Exotic options:**

#### Chooser Option
- Expires in **3 weeks**
- After **2 weeks**, buyer chooses call or put (whichever is ITM)
- Then behaves as standard option for final week

#### Binary Put Option
- All-or-nothing payoff
- If underlying < strike at expiry → pays specified amount
- Otherwise → worthless

#### Knock-Out Put Option
- Behaves like a regular put **unless** underlying trades below the knockout barrier before expiry
- If barrier breached at any discrete step → option becomes **worthless immediately**
- Only discrete grid points matter (no continuous monitoring)

### Key Rules

- Buy or sell up to the displayed volume per product
- "Price" column is cosmetic (investment cost display) — does not affect PnL
- Hold positions to expiry — no intra-round trading across days
- Unhedged exposure → large losses possible
- Submit orders in Manual Challenge window; last submission before round end is locked in
