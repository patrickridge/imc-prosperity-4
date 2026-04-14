# Round 1 Manual — "An Intarian Welcome"

Source: Prosperity 4 Wiki, Round 1 — "Trading groundwork", section "Manual
trading challenge".

## Prompt

The Intarians open two exchange auctions, one for `DRYLAND_FLAX` and one for
`EMBER_MUSHROOM`. We submit **one limit order (price, quantity) per good**, and
we submit **last** — no further bids/asks arrive after our order.

One-time opportunity. Does not affect algorithmic trading.

## Auction mechanism (verbatim from wiki)

When the auction ends, the exchange selects a **single clearing price p\*** that:

1. maximizes total traded volume, then
2. breaks ties by choosing the **higher** price.

All bids with price ≥ p\* and asks with price ≤ p\* execute at p\*. **Allocation
is price priority, then time priority. Since we submit last, we are last in line
at any price level we join.**

This is uniform-price clearing. It is NOT resting-price matching and NOT
pay-your-bid.

## Guaranteed buyback after the auction

No continuous trading on these products. The Merchant Guild buys any inventory
at a fixed price:

- `DRYLAND_FLAX`: **30** per unit, no fees.
- `EMBER_MUSHROOM`: **20** per unit, **fee: 0.10 per unit traded**.

Break-even buy prices:

- Flax: p\* ≤ 30.
- Mushroom: p\* ≤ 19.90.

## Order books (stale, crossed)

Authoritative values live in `welcome_auction.py`.

### Dryland Flax

| Side | Price | Volume  |
|------|-------|---------|
| Ask  | 33    | 30,000  |
| Ask  | 32    | 20,000  |
| Ask  | 31    | 20,000  |
| Ask  | 28    | 40,000  |
| Bid  | 30    | 30,000  |
| Bid  | 29    | 5,000   |
| Bid  | 28    | 12,000  |
| Bid  | 27    | 28,000  |

Crossed (best bid 30 > best ask 28). Natural clearing price without our order:
**28** (volume 40k).

### Ember Mushroom

| Side | Price | Volume  |
|------|-------|---------|
| Ask  | 19    | 12,000  |
| Ask  | 18    | 10,000  |
| Ask  | 17    | 0       |
| Ask  | 16    | 5,000   |
| Ask  | 15    | 6,000   |
| Ask  | 14    | 35,000  |
| Ask  | 13    | 25,000  |
| Ask  | 12    | 20,000  |
| Bid  | 20    | 43,000  |
| Bid  | 19    | 17,000  |
| Bid  | 18    | 6,000   |
| Bid  | 17    | 5,000   |
| Bid  | 16    | 10,000  |
| Bid  | 15    | 5,000   |
| Bid  | 14    | 10,000  |
| Bid  | 13    | 7,000   |

Crossed (best bid 20 > best ask 12). Natural clearing price without our order:
**15** (volume 86k).

## What to decide

For each good, pick a single **(side, price, volume)** that maximizes expected
profit under uniform-price clearing with "highest price wins the tiebreak" and
with us last in time at our own price level.

Key tension: bidding higher pushes the clearing price up (bad, we pay more).
Bidding at the existing top price puts us behind the resting volume (bad, we
fill little). The sharp trick is to pick a volume that makes the max-volume
tiebreak land one tick above the natural clear, so we fill as the price-priority
overflow rather than the crowded-queue tail.

## Analogues in past Prosperity rounds

No past manual challenge used this exact mechanism. Closest precedents:

- **P2 R1 "Goldfish auction"** (`docs/reference/prosperity-2-solutions.md:43-46`)
  — sealed bid against sellers with uniform-random reserve prices. Pure
  distribution optimization, no order book.
- **P3 R3 "Sea turtles"** (`docs/reference/prosperity-3-hedgehogs.md:829-838`)
  — sealed bid against a reserve-price seller, **pay-your-bid** semantics.

Both are sealed-bid manuals, but neither involves clearing a crossed order book.
The P4 R1 mechanic is new — treat the wiki text as the only ground truth.
