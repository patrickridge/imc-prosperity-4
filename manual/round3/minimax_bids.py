"""Minimax opportunity cost optimization for Bid 1 in the Bio-Pod auction."""

import numpy as np

RESERVE_LOW = 670
RESERVE_HIGH = 920
RESERVE_RANGE = RESERVE_HIGH - RESERVE_LOW

V_MIN = 920
V_MAX = 1170
V_STEPS = 251

BID_MIN = 670
BID_MAX = 920
BID_STEPS = 251


def expected_profit(bid: float, resale_value: float) -> float:
    trade_probability = (bid - RESERVE_LOW) / RESERVE_RANGE
    surplus = resale_value - bid
    return trade_probability * surplus


def optimal_bid(resale_value: float) -> float:
    unconstrained = (resale_value + RESERVE_LOW) / 2
    return min(unconstrained, RESERVE_HIGH)


def opportunity_cost(bid: float, resale_value: float) -> float:
    best_profit = expected_profit(optimal_bid(resale_value), resale_value)
    actual_profit = expected_profit(bid, resale_value)
    if best_profit == 0:
        return 0.0
    return 1 - actual_profit / best_profit


def find_minimax_bid():
    bids = np.linspace(BID_MIN, BID_MAX, BID_STEPS)
    vs = np.linspace(V_MIN, V_MAX, V_STEPS)

    worst_cost_per_bid = []
    for bid in bids:
        worst = max(opportunity_cost(bid, v) for v in vs)
        worst_cost_per_bid.append(worst)

    worst_cost_per_bid = np.array(worst_cost_per_bid)
    best_idx = np.argmin(worst_cost_per_bid)

    return bids[best_idx], worst_cost_per_bid[best_idx]


def print_grid():
    bid_values = np.arange(670, 925, 15)
    v_values = [920, 960, 1000, 1050, 1100, 1170]

    header = f"{'Bid':>6}" + "".join(f"{'V='+str(v):>10}" for v in v_values) + f"{'Worst':>10}"
    print(header)
    print("-" * len(header))

    for bid in bid_values:
        losses = [opportunity_cost(bid, v) for v in v_values]
        worst = max(losses)
        row = f"{bid:>6.0f}"
        for loss in losses:
            row += f"{-loss*100:>9.1f}%"
        row += f"{-worst*100:>9.1f}%"
        print(row)


def bid2_scaling(bid, resale_value, mu):
    if bid >= mu:
        return 1.0
    ratio = (resale_value - mu) / (resale_value - bid)
    return min(ratio ** 3, 1.0)


def bid2_profit(bid, resale_value, mu):
    trade_probability = (bid - RESERVE_LOW) / RESERVE_RANGE
    surplus = resale_value - bid
    scaling = bid2_scaling(bid, resale_value, mu)
    return trade_probability * surplus * scaling


def bid2_optimal_profit(resale_value, mu):
    """Brute-force the best Bid 2 for a given (V, μ)."""
    bids = np.linspace(BID_MIN, BID_MAX, BID_STEPS)
    return max(bid2_profit(b, resale_value, mu) for b in bids)


def bid2_opportunity_cost(bid, resale_value, mu):
    best = bid2_optimal_profit(resale_value, mu)
    actual = bid2_profit(bid, resale_value, mu)
    if best <= 0:
        return 0.0
    return 1 - actual / best


def plot_bid2_heatmaps():
    import matplotlib.pyplot as plt

    candidate_bids = [860, 863, 866, 869, 872, 875]
    vs = np.linspace(V_MIN, V_MAX, 80)
    mus = np.linspace(830, 900, 80)

    fig, axes = plt.subplots(1, len(candidate_bids), figsize=(22, 4.5))
    fig.suptitle("Bid 2 opportunity cost (zoomed: 860–875)", y=1.02)

    for ax, bid in zip(axes, candidate_bids):
        grid = np.zeros((len(mus), len(vs)))
        for i, mu in enumerate(mus):
            for j, v in enumerate(vs):
                if mu >= v:
                    grid[i, j] = np.nan
                else:
                    grid[i, j] = bid2_opportunity_cost(bid, v, mu) * 100

        im = ax.imshow(
            grid, origin="lower", aspect="auto",
            extent=[V_MIN, V_MAX, 830, 900],
            vmin=0, vmax=30, cmap="RdYlGn_r",
        )
        ax.set_title(f"Bid = {bid}")
        ax.set_xlabel("V (resale value)")
        if bid == candidate_bids[0]:
            ax.set_ylabel("μ (population avg)")

    fig.colorbar(im, ax=axes, label="Opportunity cost %", shrink=0.8)
    plt.tight_layout()
    plt.savefig("research/bid2_heatmaps_zoomed.png", dpi=150, bbox_inches="tight")
    print("Saved research/bid2_heatmaps_zoomed.png")


if __name__ == "__main__":
    best_bid, best_worst_cost = find_minimax_bid()
    print(f"Minimax bid: {best_bid:.0f}")
    print(f"Worst-case opportunity cost: {best_worst_cost*100:.1f}%")
    print()
    print_grid()
    print()
    print("Generating Bid 2 heatmaps...")
    plot_bid2_heatmaps()
