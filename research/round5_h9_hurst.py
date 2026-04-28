"""H9 (Round 5): Trending vs mean-reverting per product (Hurst exponent).

Hurst exponent H from rescaled-range analysis:
  H ~ 0.5  → random walk
  H < 0.5  → mean-reverting (the lower the more reversion)
  H > 0.5  → persistent trend (the higher the stronger)

We can't run statsmodels' ADF here (not installed), so Hurst is the simple
proxy. Output classifies each of the 50 products.

Run as: python3 research/round5_h9_hurst.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

DATA_DIR = Path(__file__).parent.parent / "data" / "round5"
DAYS = [2, 3, 4]
LAGS = [10, 20, 50, 100, 200, 500, 1000]


def hurst_exponent(price_series: pd.Series) -> float:
    log_price = np.log(price_series.dropna())
    if len(log_price) < max(LAGS) * 2:
        return float("nan")
    rs_values = []
    valid_lags = []
    for lag in LAGS:
        diffs = log_price.diff(lag).dropna()
        if len(diffs) < 10 or diffs.std() == 0:
            continue
        rs_values.append(diffs.std())
        valid_lags.append(lag)
    if len(valid_lags) < 3:
        return float("nan")
    log_lags = np.log(valid_lags)
    log_rs = np.log(rs_values)
    slope = np.polyfit(log_lags, log_rs, 1)[0]
    return slope


def classify(h: float) -> str:
    if np.isnan(h):
        return "—"
    if h < 0.40:
        return "strong MR"
    if h < 0.48:
        return "MR"
    if h < 0.52:
        return "random walk"
    if h < 0.60:
        return "trend"
    return "strong trend"


def main() -> None:
    print("=" * 78)
    print("H9: Hurst exponent per product — trending vs mean-reverting")
    print("=" * 78)
    print("H<0.5 → mean-reverting | H≈0.5 → random walk | H>0.5 → trending")
    print()

    rows = []
    for day in DAYS:
        df = pd.read_csv(DATA_DIR / f"prices_round_5_day_{day}.csv", sep=";")
        for product, g in df.groupby("product"):
            h = hurst_exponent(g.sort_values("timestamp")["mid_price"])
            rows.append({"day": day, "product": product, "hurst": h})

    df = pd.DataFrame(rows)
    by_product = df.groupby("product")["hurst"].mean().reset_index()
    by_product["class"] = by_product["hurst"].apply(classify)
    by_product = by_product.sort_values("hurst")

    print("Most mean-reverting:")
    print(by_product.head(10).to_string(index=False, float_format=lambda x: f"{x:.3f}"))
    print()
    print("Most trending:")
    print(by_product.tail(10).to_string(index=False, float_format=lambda x: f"{x:.3f}"))
    print()

    counts = by_product["class"].value_counts()
    print("Classification counts:")
    for c, n in counts.items():
        print(f"  {c:<14} {n}")


if __name__ == "__main__":
    main()
