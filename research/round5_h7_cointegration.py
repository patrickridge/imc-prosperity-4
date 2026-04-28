"""H7 (Round 5): Which within-category pairs are cointegrated?

H1 showed PEBBLES_XL/XS correlation breaks day 3, but cointegration is a
stronger property. For each product pair within a category, fit
    prod_b = beta * prod_a + alpha
and look at the residual. If the residual is mean-reverting (short half-life),
the pair is cointegrated and tradeable as a spread.

Half-life is computed from the AR(1) on residual changes:
    res_t - res_{t-1} = phi * res_{t-1} + noise
    half_life = -log(2) / log(1 + phi)

Short half-life (< 500 ticks) + stable beta day-to-day = good spread trade.

Run as: python3 research/round5_h7_cointegration.py
"""
from __future__ import annotations

from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd

DATA_DIR = Path(__file__).parent.parent / "data" / "round5"
DAYS = [2, 3, 4]
SHORT_HALF_LIFE = 500   # below this we call it "fast MR"
TOP_N = 12

CATEGORIES = {
    "GALAXY_SOUNDS": ["DARK_MATTER", "BLACK_HOLES", "PLANETARY_RINGS", "SOLAR_WINDS", "SOLAR_FLAMES"],
    "SLEEP_POD":     ["SUEDE", "LAMB_WOOL", "POLYESTER", "NYLON", "COTTON"],
    "MICROCHIP":     ["CIRCLE", "OVAL", "SQUARE", "RECTANGLE", "TRIANGLE"],
    "PEBBLES":       ["XS", "S", "M", "L", "XL"],
    "ROBOT":         ["VACUUMING", "MOPPING", "DISHES", "LAUNDRY", "IRONING"],
    "UV_VISOR":      ["YELLOW", "AMBER", "ORANGE", "RED", "MAGENTA"],
    "TRANSLATOR":    ["SPACE_GRAY", "ASTRO_BLACK", "ECLIPSE_CHARCOAL", "GRAPHITE_MIST", "VOID_BLUE"],
    "PANEL":         ["1X2", "2X2", "1X4", "2X4", "4X4"],
    "OXYGEN_SHAKE":  ["MORNING_BREATH", "EVENING_BREATH", "MINT", "CHOCOLATE", "GARLIC"],
    "SNACKPACK":     ["CHOCOLATE", "VANILLA", "PISTACHIO", "STRAWBERRY", "RASPBERRY"],
}


def load_pivot(category: str) -> pd.DataFrame:
    products = [f"{category}_{v}" for v in CATEGORIES[category]]
    frames = []
    for day in DAYS:
        df = pd.read_csv(DATA_DIR / f"prices_round_5_day_{day}.csv", sep=";")
        sub = df[df["product"].isin(products)]
        pivot = sub.pivot_table(index="timestamp", columns="product", values="mid_price")
        pivot["__day"] = day
        frames.append(pivot)
    return pd.concat(frames).dropna()


def half_life(residual: pd.Series) -> float:
    res = residual.dropna()
    if len(res) < 50:
        return float("nan")
    delta = res.diff().dropna()
    lagged = res.shift(1).dropna()
    n = min(len(delta), len(lagged))
    if n < 50:
        return float("nan")
    phi = np.cov(delta[-n:], lagged[-n:])[0, 1] / np.var(lagged[-n:])
    if 1 + phi <= 0 or 1 + phi >= 1:
        return float("inf")
    return -np.log(2) / np.log(1 + phi)


def test_pair(pivot: pd.DataFrame, a: str, b: str) -> dict:
    x = pivot[a].values
    y = pivot[b].values
    beta = np.cov(x, y)[0, 1] / np.var(x)
    alpha = y.mean() - beta * x.mean()
    residual = pd.Series(y - (beta * x + alpha))

    daily_betas = []
    for day, g in pivot.groupby("__day"):
        gx, gy = g[a].values, g[b].values
        if np.var(gx) > 0:
            daily_betas.append(np.cov(gx, gy)[0, 1] / np.var(gx))

    return {
        "beta": beta,
        "beta_std": np.std(daily_betas) if daily_betas else float("nan"),
        "half_life": half_life(residual),
        "residual_std": residual.std(),
    }


def main() -> None:
    print("=" * 90)
    print("H7: Within-category cointegration — which pairs make a tradeable spread?")
    print("=" * 90)
    print(f"Half-life < {SHORT_HALF_LIFE} ticks AND stable beta day-to-day = tradeable spread.")
    print()

    rows = []
    for category in CATEGORIES:
        pivot = load_pivot(category)
        for v_a, v_b in combinations(CATEGORIES[category], 2):
            a, b = f"{category}_{v_a}", f"{category}_{v_b}"
            stats = test_pair(pivot, a, b)
            rows.append({
                "category": category,
                "pair": f"{v_a} / {v_b}",
                **stats,
            })

    df = pd.DataFrame(rows).sort_values("half_life")

    print(f"Top {TOP_N} fastest-reverting pairs:")
    print()
    cols = ["category", "pair", "beta", "beta_std", "half_life", "residual_std"]
    fmt = lambda x: f"{x:.2f}" if abs(x) < 1e6 else "inf"
    print(df.head(TOP_N)[cols].to_string(index=False, float_format=fmt))
    print()

    actionable = df[(df["half_life"] < SHORT_HALF_LIFE) & (df["beta_std"] < 0.5)]
    print(f"Pairs with fast MR (half-life < {SHORT_HALF_LIFE}) AND stable beta (std<0.5): "
          f"{len(actionable)}/{len(df)}")
    if len(actionable):
        print(actionable[cols].to_string(index=False, float_format=fmt))


if __name__ == "__main__":
    main()
