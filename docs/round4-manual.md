# Round 4 Manual Challenge — Option Contracts

## Underlying

| Product | Bid | Ask | Volume | Spot |
|---------|-----|-----|--------|------|
| AETHER_CRYSTAL | 49.975 | 50.025 | 200 each side | ~50 |

## Vanilla Options

| Contract | Type | Strike | Expiry | Bid | Ask | Volume |
|----------|------|--------|--------|-----|-----|--------|
| AC_50_P | Put | 50 | T+21 | 12.00 | 12.05 | 50 |
| AC_50_C | Call | 50 | T+21 | 12.00 | 12.05 | 50 |
| AC_35_P | Put | 35 | T+21 | 4.33 | 4.35 | 50 |
| AC_40_P | Put | 40 | T+21 | 6.50 | 6.55 | 50 |
| AC_45_P | Put | 45 | T+21 | 9.05 | 9.10 | 50 |
| AC_60_C | Call | 60 | T+21 | 8.80 | 8.85 | 50 |
| AC_50_P_2 | Put | 50 | T+14 | 9.70 | 9.75 | 50 |
| AC_50_C_2 | Call | 50 | T+14 | 9.70 | 9.75 | 50 |

## Exotic Options

| Contract | Type | Strike | Expiry | Bid | Ask | Volume | Details |
|----------|------|--------|--------|-----|-----|--------|---------|
| AC_50_CO | Chooser | 50 | T+21 (choose at T+14) | 22.20 | 22.30 | 50 | At T+14, auto-converts to whichever side (put/call) is ITM. Then standard option for remaining 7 days. |
| AC_40_BP | Binary Put | 40 | T+21 | 5.00 | 5.10 | 50 | Pays fixed 10 if underlying < 40 at expiry. Otherwise worthless. |
| AC_45_KO | Knock-Out Put | 45 (barrier 35) | T+21 | 0.15 | 0.175 | 500 | Standard put with K=45 unless underlying ever falls below 35 → knocked out (worthless). |

## Key Parameters

- Contract size: 3,000 (PnL multiplier)
- Underlying spot: ~50
- Annualized volatility: 251%
- 1 week = 5 trading days, 4 steps/day, 252 days/year
- T+14 = 2 weeks = 10 days = 40 steps
- T+21 = 3 weeks = 15 days = 60 steps
- PnL = average over 100 simulations of GBM (zero drift, discrete grid)
- Knock-out barrier monitored only at discrete steps (not continuous)
- Hold to expiry — no intra-round trading

## Price Column Notes

The "Price" column shown in the UI (e.g. +0.71, -0.45) is cosmetic ("investment cost") and does not affect PnL. Ignore it for strategy purposes.
