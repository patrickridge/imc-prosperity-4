"""
Round 1 manual challenge — Intarian welcome auction.

Goal: pick ONE order per good that maximizes profit under price-time priority
on a stale (crossed) order book. See problem.md for full rules.

Run:   python3 manual/round1/welcome_auction.py
"""

from dataclasses import dataclass


LIQUIDATION_FLAX = 30
LIQUIDATION_MUSHROOM = 20
MUSHROOM_FEE_PER_UNIT = 0.05  # on buy AND on sell


@dataclass
class Level:
    price: int
    volume: int


# Sorted: asks ascending (best ask first), bids descending (best bid first).
FLAX_ASKS = [Level(28, 40_000), Level(31, 20_000), Level(32, 20_000), Level(33, 30_000)]
FLAX_BIDS = [Level(30, 30_000), Level(29, 5_000), Level(28, 12_000), Level(27, 28_000)]

MUSHROOM_ASKS = [
    Level(12, 20_000), Level(13, 25_000), Level(14, 35_000), Level(15, 6_000),
    Level(16, 5_000),  Level(17, 0),  Level(18, 10_000),      Level(19, 12_000),
]
MUSHROOM_BIDS = [
    Level(20, 43_000), Level(19, 17_000), Level(18, 6_000),  Level(17, 5_000),
    Level(16, 10_000), Level(15, 5_000),  Level(14, 10_000), Level(13, 7_000),
]


# ---------------------------------------------------------------------------
# TODO: fill in the two functions below.
#
# The puzzle: on a CROSSED stale book, the auction will first match the
# existing overlapping bids and asks against each other (price-time priority).
# Your single new order sits in the queue. To get filled, you must beat
# existing orders on price (or match price but accept time priority behind
# them — which usually means you don't fill at all if volume is already
# satisfied).
#
# Think about:
#   1. What is the natural clearing price of the stale book WITHOUT your order?
#      (Walk asks from low→high, bids from high→low, accumulate until crossed
#      volume matches on both sides.)
#   2. Where would you insert your order to jump the queue and still be
#      profitable after liquidation (and fees, for mushrooms)?
#   3. For flax: liquidation = 30. You profit on BUY side if fill price < 30,
#      on SELL side if fill price > 30.
#   4. For mushrooms: liquidation = 20, with 0.05 round-trip fee. Break-even
#      buy price = 20 - 0.05 = 19.95. Break-even sell price = 20 + 0.05.
# ---------------------------------------------------------------------------


def decide_flax_order() -> tuple[str, int, int]:
    """Return (side, price, volume) for the single Dryland Flax order.

    side  = 'BUY' or 'SELL'
    price = integer XIRECs
    volume = integer units
    """
    raise NotImplementedError("decide what Flax order maximizes profit")


def decide_mushroom_order() -> tuple[str, int, int]:
    """Return (side, price, volume) for the single Ember Mushroom order."""
    raise NotImplementedError("decide what Mushroom order maximizes profit")


# ---------------------------------------------------------------------------
# Helper: eyeball the crossed region so you can reason about clearing.
# ---------------------------------------------------------------------------

def show_crossed_region(name: str, asks: list[Level], bids: list[Level], liq: float) -> None:
    print(f"\n=== {name} (liquidation {liq}) ===")
    print("Crossed asks (price <= best bid):")
    best_bid = bids[0].price
    for a in asks:
        if a.price <= best_bid:
            print(f"  ask {a.price:>3} x {a.volume:>6}")
    print("Crossed bids (price >= best ask):")
    best_ask = asks[0].price
    for b in bids:
        if b.price >= best_ask:
            print(f"  bid {b.price:>3} x {b.volume:>6}")


if __name__ == "__main__":
    show_crossed_region("Dryland Flax", FLAX_ASKS, FLAX_BIDS, LIQUIDATION_FLAX)
    show_crossed_region("Ember Mushroom", MUSHROOM_ASKS, MUSHROOM_BIDS, LIQUIDATION_MUSHROOM)

    # Uncomment once you have filled in the decision functions:
    # print("\nFlax order:    ", decide_flax_order())
    # print("Mushroom order:", decide_mushroom_order())
