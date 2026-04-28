"""H4 (Round 5): Does order-book imbalance predict short-term returns?

Order-book imbalance (OBI) at L1:
    obi = (bid_volume_1 - ask_volume_1) / (bid_volume_1 + ask_volume_1)

If OBI > 0 at time t, more buyers than sellers → expect price up.
We test correlation(OBI_t, return_{t+k}) for k in {1, 5, 10, 50} ticks.

Strong correlation at small k → use OBI to skew quotes (microstructure edge).
Weak correlation everywhere → OBI noise, ignore.

Run as: python3 research/round5_h4_obi_signal.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

DATA_DIR = Path(__file__).parent.parent / "data" / "round5"
DAYS = [2, 3, 4]
HORIZONS = [1, 5, 10, 50]
TOP_N = 12   # show the strongest signals
MIN_ABS_CORR = 0.05  # below this we treat as noise


def compute_obi_signal(day: int) -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / f"prices_round_5_day_{day}.csv", sep=";")
    df = df.dropna(subset=["bid_volume_1", "ask_volume_1", "mid_price"])

    rows = []
    for product, g in df.groupby("product"):
        g = g.sort_values("timestamp").reset_index(drop=True)
        bv = g["bid_volume_1"].astype(float)
        av = g["ask_volume_1"].astype(float)
        denom = bv + av
        obi = (bv - av) / denom.where(denom > 0, np.nan)

        log_mid = np.log(g["mid_price"])
        out = {"product": product, "day": day}
        for k in HORIZONS:
            future_return = log_mid.shift(-k) - log_mid
            corr = obi.corr(future_return)
            out[f"corr_{k}"] = corr
        rows.append(out)

    return pd.DataFrame(rows)


def main() -> None:
    print("=" * 84)
    print("H4: Order-book imbalance → future return correlation")
    print("=" * 84)
    print("OBI = (bid_vol - ask_vol) / (bid_vol + ask_vol) at L1")
    print(f"Future return horizons (in 100-ts ticks): {HORIZONS}")
    print()

    frames = [compute_obi_signal(d) for d in DAYS]
    full = pd.concat(frames, ignore_index=True)

    # average across days for stability
    summary = full.groupby("product")[[f"corr_{k}" for k in HORIZONS]].mean()
    summary["abs_max"] = summary.abs().max(axis=1)

    print(f"Top {TOP_N} products by max |OBI-return correlation| (avg across 3 days):")
    print()
    cols = [f"corr_{k}" for k in HORIZONS]
    top = summary.nlargest(TOP_N, "abs_max")[cols]
    print(top.to_string(float_format=lambda x: f"{x:+.3f}"))
    print()

    actionable = (summary["abs_max"] >= MIN_ABS_CORR).sum()
    print(f"Products with |corr| >= {MIN_ABS_CORR} at any horizon: {actionable}/50")
    print()

    print("Day-by-day stability check (top product, all horizons):")
    top_product = summary["abs_max"].idxmax()
    print(f"  {top_product}:")
    for day in DAYS:
        row = full[(full["product"] == top_product) & (full["day"] == day)].iloc[0]
        vals = " ".join(f"k={k}: {row[f'corr_{k}']:+.3f}" for k in HORIZONS)
        print(f"    day {day}: {vals}")

    print()
    print("Interpretation:")
    print("  - corr_1 strongly positive → quote skewed by OBI captures next-tick edge")
    print("  - corr decaying with k → very short-lived signal, MM use only")
    print("  - corr near 0 everywhere → OBI is noise on this product")


if __name__ == "__main__":
    main()
