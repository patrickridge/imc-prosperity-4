# Round 3 — "Gloves Off"

Source: [Prosperity 4 Wiki](https://imc-prosperity.notion.site/34ce8453a0938072a58cc7de372ff551)

## Overview

Start of GOAT (Great Orbital Ascension Trials). **Leaderboard resets — all teams begin at zero PnL.**
New planet: Solvenar. Trading days last 48 hours.

## Algorithmic Challenge: "Options Require Decisions"

### Products & Position Limits

| Product | Limit | Type |
|---------|-------|------|
| `HYDROGEL_PACK` | 200 | Delta-1 |
| `VELVETFRUIT_EXTRACT` | 200 | Delta-1 |
| `VELVETFRUIT_EXTRACT_VOUCHER` (×10) | 300 each | Options |

### Voucher Details

10 vouchers with different strikes: `VEV_4000`, `VEV_4500`, `VEV_5000`, `VEV_5100`, `VEV_5200`, `VEV_5300`, `VEV_5400`, `VEV_5500`, `VEV_6000`, `VEV_6500`.

- Strike = number in the name
- 7-day expiration starting from Round 1 (TTE = 5 days at start of R3)
- Cannot be exercised before expiry
- Positions liquidated at hidden fair value at end of round

### TTE Timeline

| Day | TTE |
|-----|-----|
| Historical day 0 (tutorial) | 8 |
| Historical day 1 (R1) | 7 |
| Historical day 2 (R2) | 6 |
| R3 simulation | 5 |
| R4 | 4 |

## Manual Challenge: "The Celestial Gardeners' Guild"

Trade Ornamental Bio-Pods. Sell next day at fair price of **920**.

### Mechanics

- Secret number of counterparties with reserve prices **uniformly distributed** at increments of 5, from **670 to 920** (inclusive)
- Submit **two bids**

### Bid Rules

- **Bid 1:** If bid > counterparty's reserve price → trade at your bid
- **Bid 2:** If bid > reserve price AND bid > mean of all players' second bids → trade at your bid
- **Bid 2 penalty:** If bid > reserve but bid ≤ mean of second bids, PnL penalized by:

```
(920 - avg_b2) / (920 - b2))^3
```
