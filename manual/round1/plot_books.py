"""
Visualise the round 1 manual auction books.

Top row: the order book (bids left, asks right, volume on x-axis, price on y).
Bottom row: cumulative bids ≥ p and cumulative asks ≤ p, which is what the
auction actually cares about. Clearing price = argmax of min(bids, asks).

Run: python3 manual/round1/plot_books.py
"""

import matplotlib.pyplot as plt
from welcome_auction import FLAX_ASKS, FLAX_BIDS, MUSHROOM_ASKS, MUSHROOM_BIDS


def cumulative_bids_at_or_above(bids, price_grid):
    return [sum(b.volume for b in bids if b.price >= p) for p in price_grid]


def cumulative_asks_at_or_below(asks, price_grid):
    return [sum(a.volume for a in asks if a.price <= p) for p in price_grid]


def plot_book(ax, name, asks, bids):
    bid_prices = [b.price for b in bids]
    bid_vols = [b.volume for b in bids]
    ask_prices = [a.price for a in asks]
    ask_vols = [a.volume for a in asks]

    ax.barh(bid_prices, [-v for v in bid_vols], color="#2a9d8f", label="bids")
    ax.barh(ask_prices, ask_vols, color="#e76f51", label="asks")
    ax.axvline(0, color="black", linewidth=0.5)
    ax.set_title(f"{name} — order book")
    ax.set_xlabel("volume (bids negative, asks positive)")
    ax.set_ylabel("price")
    ax.legend(loc="upper right")


def plot_clearing(ax, name, asks, bids):
    lo = min(a.price for a in asks) - 1
    hi = max(b.price for b in bids) + 2
    grid = list(range(lo, hi + 1))
    bid_curve = cumulative_bids_at_or_above(bids, grid)
    ask_curve = cumulative_asks_at_or_below(asks, grid)
    volume = [min(b, a) for b, a in zip(bid_curve, ask_curve)]

    clearing_price = max(grid, key=lambda i: (volume[grid.index(i)], i))

    ax.plot(grid, bid_curve, "o-", color="#2a9d8f", label="bids ≥ p")
    ax.plot(grid, ask_curve, "o-", color="#e76f51", label="asks ≤ p")
    ax.plot(grid, volume, "o--", color="#264653", label="volume traded")
    ax.axvline(clearing_price, color="#e9c46a", linewidth=2,
               label=f"clearing p* = {clearing_price}")
    ax.set_title(f"{name} — clearing curves")
    ax.set_xlabel("price")
    ax.set_ylabel("cumulative volume")
    ax.legend(loc="upper right")


def main():
    fig, axes = plt.subplots(2, 2, figsize=(13, 9))

    plot_book(axes[0, 0], "Flax", FLAX_ASKS, FLAX_BIDS)
    plot_book(axes[0, 1], "Mushroom", MUSHROOM_ASKS, MUSHROOM_BIDS)
    plot_clearing(axes[1, 0], "Flax", FLAX_ASKS, FLAX_BIDS)
    plot_clearing(axes[1, 1], "Mushroom", MUSHROOM_ASKS, MUSHROOM_BIDS)

    plt.tight_layout()
    out_path = "manual/round1/books.png"
    plt.savefig(out_path, dpi=120)
    print(f"saved {out_path}")


if __name__ == "__main__":
    main()
