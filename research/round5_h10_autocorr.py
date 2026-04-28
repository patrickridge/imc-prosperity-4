"""H10 (Round 5): Return autocorrelation — momentum or mean-reversion at each lag?

For each product, compute autocorrelation of log returns at lags 1, 5, 10, 50.
  positive ACF → momentum (returns continue)
  negative ACF → reversal (returns flip)
  near zero    → no edge from past return alone

Run as: python3 research/round5_h10_autocorr.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

DATA_DIR = Path(__file__).parent.parent / "data" / "round5"
DAYS = [2, 3, 4]
LAGS = [1, 5, 10, 50]
SIGNAL_THRESHOLD = 0.03   # |corr| above this is treated as a real signal


def returns_for_product(product: str) -> pd.Series:
    series = []
    for day in DAYS:
        df = pd.read_csv(DATA_DIR / f"prices_round_5_day_{day}.csv", sep=";")
        sub = df[df["product"] == product].sort_values("timestamp")
        if not sub.empty:
            series.append(np.log(sub["mid_price"]).diff().dropna())
    return pd.concat(series) if series else pd.Series(dtype=float)


def autocorr(returns: pd.Series, lag: int) -> float:
    if len(returns) < lag + 50:
        return float("nan")
    return returns.autocorr(lag)


def main() -> None:
    print("=" * 78)
    print("H10: Return autocorrelation — momentum vs reversal at lags 1, 5, 10, 50")
    print("=" * 78)
    print(f"|corr| > {SIGNAL_THRESHOLD} = signal worth using")
    print()

    df = pd.read_csv(DATA_DIR / f"prices_round_5_day_{DAYS[0]}.csv", sep=";")
    products = sorted(df["product"].unique())

    rows = []
    for product in products:
        returns = returns_for_product(product)
        rows.append({
            "product": product,
            **{f"lag_{k}": autocorr(returns, k) for k in LAGS},
        })

    out = pd.DataFrame(rows)
    out["abs_max"] = out[[f"lag_{k}" for k in LAGS]].abs().max(axis=1)
    out = out.sort_values("abs_max", ascending=False)

    print("Top 15 products by |max autocorrelation|:")
    print()
    cols = ["product"] + [f"lag_{k}" for k in LAGS]
    print(out.head(15)[cols].to_string(index=False, float_format=lambda x: f"{x:+.3f}"))
    print()

    momentum = out[out["lag_1"] > SIGNAL_THRESHOLD]
    reversal = out[out["lag_1"] < -SIGNAL_THRESHOLD]
    print(f"Momentum at lag 1 (positive ACF): {len(momentum)} products")
    print(f"Reversal at lag 1 (negative ACF): {len(reversal)} products")
    if len(reversal):
        print()
        print("Strongest lag-1 reversal (good for MR / quote-skewing strategies):")
        print(reversal.head(8)[cols].to_string(index=False, float_format=lambda x: f"{x:+.3f}"))


if __name__ == "__main__":
    main()
