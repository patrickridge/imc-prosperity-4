"""
Bio-Pod manual challenge expected-profit calculator.

Reserve prices uniform on {670, 675, ..., 920} (51 values).
Two bids: b1, b2 with b1 < b2.
- If b1 >= reserve: trade at b1.            profit = 920 - b1
- Else if b2 >= reserve AND b2 >= avg_b2:    trade at b2.  profit = 920 - b2
- Else if b2 >= reserve AND b2 <  avg_b2:    trade at b2 with penalty.
    profit = (920 - b2) * ((920 - avg_b2) / (920 - b2)) ** 3
                       = (920 - avg_b2) ** 3 / (920 - b2) ** 2
"""

from itertools import product

RESERVES = list(range(670, 925, 5))
SETTLE = 920


def expected_profit_per_counterparty(b1: int, b2: int, avg_b2: float) -> float:
    if b1 >= b2:
        return 0.0
    n = len(RESERVES)
    p_b1 = sum(1 for r in RESERVES if r <= b1) / n
    p_b2 = sum(1 for r in RESERVES if b1 < r <= b2) / n
    pay_b1 = SETTLE - b1
    if b2 >= avg_b2:
        pay_b2 = SETTLE - b2
    else:
        pay_b2 = (SETTLE - avg_b2) ** 3 / (SETTLE - b2) ** 2
    return p_b1 * pay_b1 + p_b2 * pay_b2


def grid(b1_range, b2_range, avg_b2):
    rows = []
    for b1, b2 in product(b1_range, b2_range):
        if b1 >= b2:
            continue
        ev = expected_profit_per_counterparty(b1, b2, avg_b2)
        rows.append((round(ev, 2), b1, b2))
    rows.sort(reverse=True)
    return rows[:10]


if __name__ == "__main__":
    for assumed_avg_b2 in (820, 840, 850, 860, 880):
        print(f"\n=== assumed avg_b2 = {assumed_avg_b2} ===")
        print("EV    b1   b2")
        for ev, b1, b2 in grid(range(750, 810, 5), range(820, 905, 5), assumed_avg_b2):
            print(f"{ev:6.2f} {b1}  {b2}")
