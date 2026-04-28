"""H11 (Round 5): When during the trading day is volatility highest?

Intraday volatility profile per category. Splits each day into 10 buckets
of equal length and computes return std per bucket. Useful for:
  - knowing when to widen quotes (high-vol windows)
  - knowing when MM is safest (low-vol windows)
  - detecting if the strategy should switch modes mid-day

Run as: python3 research/round5_h11_vol_intraday.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

DATA_DIR = Path(__file__).parent.parent / "data" / "round5"
DAYS = [2, 3, 4]
N_BUCKETS = 10

CATEGORIES = ["GALAXY_SOUNDS", "SLEEP_POD", "MICROCHIP", "PEBBLES", "ROBOT",
              "UV_VISOR", "TRANSLATOR", "PANEL", "OXYGEN_SHAKE", "SNACKPACK"]


def category_of(product: str) -> str:
    for prefix in CATEGORIES:
        if product.startswith(prefix):
            return prefix
    return "?"


def bucketed_vol(day: int) -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / f"prices_round_5_day_{day}.csv", sep=";")
    df = df.sort_values(["product", "timestamp"])
    df["log_return"] = df.groupby("product")["mid_price"].transform(
        lambda s: np.log(s).diff()
    )
    ts_min = df["timestamp"].min()
    ts_max = df["timestamp"].max()
    bucket_size = (ts_max - ts_min) / N_BUCKETS
    df["bucket"] = ((df["timestamp"] - ts_min) // bucket_size).clip(0, N_BUCKETS - 1).astype(int)
    df["category"] = df["product"].apply(category_of)
    return (df.groupby(["category", "bucket"])["log_return"]
              .std().mul(100).reset_index().rename(columns={"log_return": "vol_pct"}))


def main() -> None:
    print("=" * 84)
    print("H11: Intraday volatility profile per category")
    print("=" * 84)
    print(f"Each day split into {N_BUCKETS} equal buckets; vol = std of log returns (%)")
    print("Average across all 3 days:")
    print()

    frames = [bucketed_vol(d) for d in DAYS]
    combined = pd.concat(frames).groupby(["category", "bucket"])["vol_pct"].mean().reset_index()
    pivot = combined.pivot(index="category", columns="bucket", values="vol_pct")

    bucket_labels = [f"b{i}" for i in range(N_BUCKETS)]
    pivot.columns = bucket_labels
    pivot["max_bucket"] = pivot.idxmax(axis=1)
    pivot["max_vol"] = pivot[bucket_labels].max(axis=1)
    pivot["min_vol"] = pivot[bucket_labels].min(axis=1)
    pivot["max_min_ratio"] = pivot["max_vol"] / pivot["min_vol"]

    print(pivot[bucket_labels].to_string(float_format=lambda x: f"{x:.3f}"))
    print()
    print("Bucket of peak vol + max/min ratio (>2 = strong intraday pattern):")
    print(pivot[["max_bucket", "max_vol", "min_vol", "max_min_ratio"]].to_string(
        float_format=lambda x: f"{x:.3f}"))
    print()
    print("Implication:")
    print("  - Categories with high max/min ratio: widen quotes during peak bucket.")
    print("  - Flat profile (~1.0 ratio): vol is constant; quote uniformly all day.")


if __name__ == "__main__":
    main()
