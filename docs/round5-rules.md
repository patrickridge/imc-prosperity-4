# Round 5 — "The Final Stretch"

Source: [Prosperity 4 Wiki](https://imc-prosperity.notion.site/Round-5-The-Final-Stretch-350e8453a09380dd9347cd078df13f4c)

## Overview

The final round. 50 brand-new tradable goods replace every product from previous rounds — you can no longer trade `HYDROGEL_PACK`, `VELVETFRUIT_EXTRACT`, vouchers, `AETHER_CRYSTAL`, or anything else from Rounds 1–4 in the algo challenge.

Two challenges:
1. **Algo:** "Cherry Picking Winners" — pick which of the 50 new goods are worth trading.
2. **Manual:** "Extra! Extra! Read all about it!" — one-day news-driven portfolio on the neighbouring planet Ignith, fed by the *Ashflow Alpha* news source.

---

## Algorithmic Challenge: "Cherry Picking Winners"

### Products

50 products in 10 categories of 5. **Position limit: 10 per product.**

| Category | Variants |
|---|---|
| Galaxy Sounds Recorders | `GALAXY_SOUNDS_DARK_MATTER`, `GALAXY_SOUNDS_BLACK_HOLES`, `GALAXY_SOUNDS_PLANETARY_RINGS`, `GALAXY_SOUNDS_SOLAR_WINDS`, `GALAXY_SOUNDS_SOLAR_FLAMES` |
| Vertical Sleeping Pods | `SLEEP_POD_SUEDE`, `SLEEP_POD_LAMB_WOOL`, `SLEEP_POD_POLYESTER`, `SLEEP_POD_NYLON`, `SLEEP_POD_COTTON` |
| Organic Microchips | `MICROCHIP_CIRCLE`, `MICROCHIP_OVAL`, `MICROCHIP_SQUARE`, `MICROCHIP_RECTANGLE`, `MICROCHIP_TRIANGLE` |
| Purification Pebbles | `PEBBLES_XS`, `PEBBLES_S`, `PEBBLES_M`, `PEBBLES_L`, `PEBBLES_XL` |
| Domestic Robots | `ROBOT_VACUUMING`, `ROBOT_MOPPING`, `ROBOT_DISHES`, `ROBOT_LAUNDRY`, `ROBOT_IRONING` |
| UV-Visors | `UV_VISOR_YELLOW`, `UV_VISOR_AMBER`, `UV_VISOR_ORANGE`, `UV_VISOR_RED`, `UV_VISOR_MAGENTA` |
| Instant Translators | `TRANSLATOR_SPACE_GRAY`, `TRANSLATOR_ASTRO_BLACK`, `TRANSLATOR_ECLIPSE_CHARCOAL`, `TRANSLATOR_GRAPHITE_MIST`, `TRANSLATOR_VOID_BLUE` |
| Construction Panels | `PANEL_1X2`, `PANEL_2X2`, `PANEL_1X4`, `PANEL_2X4`, `PANEL_4X4` |
| Liquid Breath Oxygen Shakes | `OXYGEN_SHAKE_MORNING_BREATH`, `OXYGEN_SHAKE_EVENING_BREATH`, `OXYGEN_SHAKE_MINT`, `OXYGEN_SHAKE_CHOCOLATE`, `OXYGEN_SHAKE_GARLIC` |
| Protein Snack Packs | `SNACKPACK_CHOCOLATE`, `SNACKPACK_VANILLA`, `SNACKPACK_PISTACHIO`, `SNACKPACK_STRAWBERRY`, `SNACKPACK_RASPBERRY` |

### What the wiki says about strategy

> "Each group has its own story, but some offer more market inefficiencies than others. In certain groups, strong patterns are embedded in price movements, waiting to be discovered by you! You can capitalize on these opportunities, while developing an effective trading strategy for the other products, just as you have done before."

So: not every category is equally rich. Find the inefficiencies; market-make the rest.

### Data

Three days of backtest data live in `data/round5/`:

- `prices_round_5_day_{2,3,4}.csv` — order book snapshots
- `trades_round_5_day_{2,3,4}.csv` — public trade prints

See `research/round5_algo_overview.md` for first-pass findings. Headlines: PEBBLES_XL +60.7%, MICROCHIP_OVAL −44.8% over 3 days. PEBBLES_XL/XS correlation −0.83.

---

## Manual Challenge: "Extra! Extra! Read all about it!"

### Setup

You hold a portfolio for ONE day on the Ignith exchange. Allocate up to 100% of a `1,000,000` budget across **9 Ignith goods** described in *Ashflow Alpha* news stories ([manual/round5/manual5.pdf](../manual/round5/manual5.pdf)).

### Rules

- Submit volumes per good in the Manual Challenge Overview window. Resubmit any time before round close; last submission wins.
- **Total volume across goods must be ≤ 100% of budget.** Less is allowed.
- **Unused budget expires worthless** — does not add to PnL.
- **Used budget is subtracted from your trade PnL.**
- **Fee formula** (per product, on top of the used budget):

  ```
  fee = (volume_for_specific_product / 100)² × budget
  ```

  i.e. fees are **quadratic** in per-product volume. A 50% allocation costs 25% of budget in fees. A 10% allocation costs 1%.

### What this means for sizing

For a single product with expected return `r` and signed weight `w` (fraction of budget, positive = long, negative = short):

```
profit_i = w · r · B − w² · B
```

Unconstrained optimum: `w* = r / 2`. Then sum |w| across all 9 goods, cap at 1, and scale down if needed. The allocator [`manual/round5/allocate.py`](../manual/round5/allocate.py) does this with a 25% single-position cap and 75% hedge factor.

Notes for `expected_returns`: P3 Round 5 hedgehogs hit 65% of optimal because they overestimated some moves. See `docs/reference/prosperity-3-hedgehogs.md` for their actual table.

### The 9 Ignith goods (story summary)

See [manual/round5/r5_manual_news.md](../manual/round5/r5_manual_news.md) for the long/short classification and conviction tiers. Headlines:

| Good | Direction | Hook |
|---|---|---|
| Lava Fountain Pen | LONG | hot drop, Stip + Splatter merger |
| Thermalite Cores | LONG (high) | users 1.42M → 3.89M projected |
| Scoria Paste | LONG | Lava D. Ray urges stockpiling |
| Volcanic Incense | LONG | Whiff Nostralico publicly buying |
| Sulfur Ltd. | LONG (high) | added to Elemental Index 118 |
| Obsidian Cutlery | SHORT | production halted, contamination |
| Pyroflex Cell | SHORT | tax cut canceled, levy doubles |
| Ashes of the Phoenix | SHORT | resurfaced video, PR scandal |
| Lava Cakes | SHORT | actual lava in product, lawsuits |

---

## Tooling status

- `data/round5/` populated (3 days of prices + trades)
- `backtester/data.py` — `LIMITS` extended with all 50 products at limit=10
- `dashboard/` — auto-discovers `data/round5/` via existing glob (no change needed)
- `research/round5_explore.py` — per-product / per-category summary
- `manual/round5/allocate.py` — quadratic-fee-aware allocator (fill in `expected_returns` to use)
