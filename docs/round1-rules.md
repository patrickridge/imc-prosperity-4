# Round 1 — "Trading Groundwork"

Source: [Prosperity 4 Wiki](https://imc-prosperity.notion.site/342e8453a09380eb9ef8cb372641267b)

## Overview

First trading round on Intara. Goal: earn net profit of 200,000 XIRECs before day 3.
Trading days last 72 hours.

## Algorithmic Challenge: "First Intarian Goods"

### Products & Position Limits

| Product | Limit | Notes |
|---------|-------|-------|
| `ASH_COATED_OSMIUM` | 80 | More volatile, may follow a hidden pattern |
| `INTARIAN_PEPPER_ROOT` | 80 | Steady value (similar to tutorial EMERALDS) |

## Manual Challenge: "An Intarian Welcome"

Two opening auctions for `DRYLAND_FLAX` and `EMBER_MUSHROOM`.

### Auction Rules

- Submit a single limit order (price, quantity) per product
- You submit last — no bids/asks arrive after yours
- Exchange selects a clearing price that:
  1. Maximizes total traded volume
  2. Breaks ties by choosing the higher price
- Allocation: price priority, then time priority (you are last at any price level)

### Guaranteed Buyback

| Product | Buyback Price | Fee |
|---------|--------------|-----|
| `DRYLAND_FLAX` | 30/unit | None |
| `EMBER_MUSHROOM` | 20/unit | 0.10/unit traded |
