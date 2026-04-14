# Round 1 Manual — Solution

## Final answer

| Good           | Side | Price           | Volume     | Expected profit |
|----------------|------|-----------------|------------|-----------------|
| Dryland Flax   | BUY  | 30 (or higher)  | **9,999**  | 9,999           |
| Ember Mushroom | BUY  | 17 (or higher)  | **19,999** | ~77,996         |

Combined: **~87,995 XIRECs**.

"Or higher" for the price means any integer price at or above the stated one
gives the same profit — we pay the clearing price, not our limit. What matters
is staying **strictly above** the clearing price so we get price priority over
the queue at that level.

Visual: run `python3 manual/round1/plot_books.py` to regenerate `books.png`
(two books + supply/demand curves).

---

## How the auction works (plain English)

1. Stack every bid and ask on a price line.
2. For each candidate price `p`, count **how many units would trade** at `p`:
   - total bids with price ≥ p want to buy,
   - total asks with price ≤ p want to sell,
   - trades = `min(buyers, sellers)`.
3. Pick the `p` where this `min` is largest. Ties go to the **higher** price.
   That's the clearing price `p*`.
4. Every trade executes at `p*`, regardless of individual limit prices.
5. Who fills at `p*`? Bids strictly above `p*` fill first (price priority).
   Bids exactly at `p*` fill next, oldest first (time priority). **We submit
   last, so at our own price we are last in the queue.**

That's the whole game.

## Step 1 — natural clearing price (no order from us)

### Flax

| Price | bids ≥ p | asks ≤ p | volume |
|-------|----------|----------|--------|
| 27    | 75,000   | 0        | 0      |
| 28    | 47,000   | 40,000   | **40,000** |
| 29    | 35,000   | 40,000   | 35,000 |
| 30    | 30,000   | 40,000   | 30,000 |

Peaks at p=28. Natural clearing: **28 × 40,000**.

### Mushroom

| Price | bids ≥ p | asks ≤ p | volume |
|-------|----------|----------|--------|
| 14    | 96,000   | 80,000   | 80,000 |
| 15    | 86,000   | 86,000   | **86,000** |
| 16    | 81,000   | 91,000   | 81,000 |
| 17    | 71,000   | 91,000   | 71,000 |
| 18    | 66,000   | 101,000  | 66,000 |
| 19    | 60,000   | 113,000  | 60,000 |

Peaks at p=15. Natural clearing: **15 × 86,000**.

## Step 2 — what our bid does to the curve

Our BUY with volume `v` at price `p_us` adds `v` to every "bids ≥ p" cell for
p ≤ p_us. That shifts the buyer curve up on the left, which can push the
max-volume price to the right.

The auction then re-picks `p*` based on the new max.

Two things we need to balance:

- **Make p\* land where we profit** (below the buyback ceiling).
- **Stay strictly above p\* in bid price** so we get priority over resting
  orders at that level.

## Step 3 — the one-unit-under-the-cap trick

Because ties break to the **higher** price, the clearing price walks up as we
stuff volume in. The sweet spot is the **largest v that keeps the next
price up from hitting the same volume cap as our target**.

That "largest v" is always one less than the cap difference. If our target
is `p*` and the next price up has volume cap `C`, we want `bids ≥ (p*+1) + v
= C − 1`, i.e. `v = C − 1 − bids_≥_(p*+1)`.

### Flax walkthrough

Target `p* = 29` (one tick above natural). Ask cap at p=29 and p=30 is
**40,000**.

Bid at `p_us = 30` with volume `v`:

| Price | bids ≥ p (with us) | asks ≤ p | volume |
|-------|---------------------|----------|--------|
| 28    | 47,000 + v          | 40,000   | 40,000 (capped) |
| 29    | 35,000 + v          | 40,000   | min(35,000 + v, 40,000) |
| 30    | 30,000 + v          | 40,000   | min(30,000 + v, 40,000) |

- `v = 9,999`: vol(30) = 39,999 (one short). Ties only at p=28 and p=29.
  Tiebreak picks **29**. Clearing = 29. ✓
- `v = 10,000`: vol(30) = 40,000. Three-way tie. Tiebreak picks **30**.
  Profit drops to 0 (we'd pay 30 = buyback price). ✗

So **v = 9,999** is the knife edge.

At `p* = 29`, bids above 29 fill first: the 30-bid (30,000) + us (9,999)
= 39,999, all accepted. Existing 29-bid (5,000) takes the leftover 1.
**We fill all 9,999 at 29. Profit = 9,999 × (30 − 29) = 9,999.**

### Mushroom walkthrough

Target `p* = 16` (one tick above natural 15). Ask cap at p=16 and p=17 is
**91,000**.

Bid at `p_us = 17` with volume `v`:

| Price | bids ≥ p (with us) | asks ≤ p | volume |
|-------|---------------------|----------|--------|
| 15    | 86,000 + v          | 86,000   | 86,000 (capped) |
| 16    | 81,000 + v          | 91,000   | min(81,000 + v, 91,000) |
| 17    | 71,000 + v          | 91,000   | min(71,000 + v, 91,000) |

- `v = 19,999`: vol(16) = 91,000 (capped). vol(17) = 90,999 (one short of
  cap). Max is p=16, unique. Clearing = **16**. ✓
- `v = 20,000`: vol(17) = 91,000 = vol(16). Tie. Tiebreak picks **17**.
  Profit drops to ~58k. ✗

So **v = 19,999** is the knife edge.

At `p* = 16`, bids above 16 fill first: 20-bid (43,000) + 19-bid (17,000)
+ 18-bid (6,000) + 17-bid existing (5,000) + us at 17 (19,999) = 90,999.
Existing 16-bid (10,000) takes the leftover 1. **We fill all 19,999 at 16.
Profit = 19,999 × (20 − 16 − 0.10) = 19,999 × 3.90 = 77,996.**

## Step 4 — why bid **above** the target, not at it

If we bid at `p*` itself, we're last in time priority at that level. Example:
bid at 16 for mushroom → existing 16-bid (10,000) fills first and we get
almost nothing. Bidding at 17 (or higher) puts us strictly above `p*`, so we
fill ahead of the resting queue at 16.

Any integer ≥ (p\*+1) works. Bidding 17 or 100 gives the same result, because
we pay `p*`, not our limit. Same principle for flax: bid 30 or 100, doesn't
matter. **Pick the lowest safe price so a mis-entry is less catastrophic.**

## Step 5 — why "one under the cap" instead of bidding bigger

The natural instinct is "more volume = more profit." But volume that pushes
the tiebreak up kills the trade — one extra unit past the knife edge and
clearing jumps, either removing our edge or flipping us to a worse price
level.

For these two books:

| v | Flax result | Mushroom result |
|---|-------------|-----------------|
| Small (e.g. 9 / 40) | Works, but only fills the tiny v → pennies of profit | Same |
| **9,999 / 19,999** | Fills the full v at `p*` just below cap | Same |
| 10,000 / 20,000 | Tiebreak flips → profit ≈ 0 or negative | Tiebreak flips → profit drops from 78k to 58k |

So the sweet spot is exactly `cap − existing_bids_≥_(p*+1) − 1`.

## What the old draft got wrong

- It assumed "resting-price matching" (aggressive bids pay resting ask
  prices). The wiki says uniform-price clearing — every trade at `p*`.
- An earlier rewrite also got the units wrong (recommended v=9 / v=40 instead
  of 9,999 / 19,999), which would still work but leave ~1000× the profit on
  the table.

## Sanity table

|                | Flax              | Mushroom           |
|----------------|-------------------|--------------------|
| Natural p*     | 28                | 15                 |
| Our target p*  | 29                | 16                 |
| Sweet-spot v   | 9,999             | 19,999             |
| Profit / unit  | 30 − 29 = 1       | 20 − 16 − 0.10 = 3.90 |
| Profit         | 9,999             | 77,996             |
