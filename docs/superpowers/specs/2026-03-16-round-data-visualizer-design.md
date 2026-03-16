# Round Data Visualizer

## Summary

Single Python script (`research/visualize.py`) that takes one day's price and trade CSVs and produces a 3-panel matplotlib figure per product.

## Usage

```bash
python research/visualize.py data/round0/prices_round_0_day_-1.csv data/round0/trades_round_0_day_-1.csv
```

Output: `research/plots/{product}_day_{day}.png`

## Data Format

**Prices CSV** (semicolon-delimited):
- `day`, `timestamp`, `product`, `bid_price_1..3`, `bid_volume_1..3`, `ask_price_1..3`, `ask_volume_1..3`, `mid_price`, `profit_and_loss`

**Trades CSV** (semicolon-delimited):
- `timestamp`, `buyer`, `seller`, `symbol`, `currency`, `price`, `quantity`
- Buyer/seller fields are empty in Round 0

## Panels (per product, vertically stacked, shared x-axis)

### 1. Price + Trades
- Mid-price as line
- Best bid/ask as shaded band
- Trade markers: green triangle-up = buy-side, red triangle-down = sell-side
- Buy/sell inferred: trade price >= mid = buyer-initiated, < mid = seller-initiated

### 2. Spread
- Line plot of `ask_price_1 - bid_price_1` over time

### 3. LOB Depth
- Stacked area: bid volumes (levels 1-3) below zero line, ask volumes (levels 1-3) above
- Shows how depth shifts over the day

## Dependencies

pandas, matplotlib (no new installs)

## Non-goals

- No interactivity, no HTML output
- No backtester integration
- No multi-day comparison (run separately per day)
