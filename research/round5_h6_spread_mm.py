"""H6 (Round 5): Which products are best market-making candidates?

For market making to be profitable on a product:
  - Spread should be wide enough that quoting inside earns >0 per round trip
  - Volatility should be low enough that we don't get adversely selected
  - Liquidity at top-of-book should be enough to fill our quotes

Score per product:
  mm_score = mean_spread / mid_price_volatility   # higher = better

Also compute:
  spread_5_or_more_pct: % of timestamps where spread >= 5 (room to quote inside)
  median_top_size:      median min(bid_volume_1, ask_volume_1)

Run as: python3 research/round5_h6_spread_mm.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

DATA_DIR = Path(__file__).parent.parent / "data" / "round5"
DAYS = [2, 3, 4]
WIDE_SPREAD_THRESHOLD = 5
TOP_N = 15


def per_product_mm_metrics(df: pd.DataFrame) -> pd.DataFrame:
    df = df.dropna(subset=["bid_price_1", "ask_price_1", "mid_price"]).copy()
    df["spread"] = df["ask_price_1"] - df["bid_price_1"]
    df["top_size"] = np.minimum(df["bid_volume_1"].fillna(0),
                                df["ask_volume_1"].fillna(0))

    rows = []
    for product, g in df.groupby("product"):
        mid_returns = np.log(g["mid_price"]).diff().dropna()
        vol = mid_returns.std() * 100
        wide_pct = (g["spread"] >= WIDE_SPREAD_THRESHOLD).mean() * 100
        rows.append({
            "product": product,
            "mean_spread": g["spread"].mean(),
            "median_spread": g["spread"].median(),
            "wide_pct": wide_pct,
            "median_top_size": g["top_size"].median(),
            "log_return_vol_pct": vol,
            "mm_score": g["spread"].mean() / max(vol, 1e-9),
        })
    return pd.DataFrame(rows).sort_values("mm_score", ascending=False)


def main() -> None:
    print("=" * 90)
    print("H6: Market-making viability — spread, volatility, top-of-book size")
    print("=" * 90)
    print(f"mm_score = mean_spread / log-return-volatility (per-tick %, all 3 days combined)")
    print(f"wide_pct = % of timestamps with spread >= {WIDE_SPREAD_THRESHOLD} (room to quote inside)")
    print()

    frames = [pd.read_csv(DATA_DIR / f"prices_round_5_day_{d}.csv", sep=";") for d in DAYS]
    df = pd.concat(frames, ignore_index=True)
    metrics = per_product_mm_metrics(df)

    print(f"Top {TOP_N} MM candidates:")
    print()
    cols = ["product", "mean_spread", "wide_pct", "median_top_size",
            "log_return_vol_pct", "mm_score"]
    fmt = {
        "mean_spread": "{:.2f}",
        "wide_pct": "{:.1f}",
        "median_top_size": "{:.0f}",
        "log_return_vol_pct": "{:.3f}",
        "mm_score": "{:.1f}",
    }
    print(metrics.head(TOP_N)[cols].to_string(
        index=False,
        formatters={c: lambda v, f=fmt[c]: f.format(v) for c in fmt},
    ))
    print()

    print(f"Bottom 5 (least viable for MM):")
    print(metrics.tail(5)[cols].to_string(
        index=False,
        formatters={c: lambda v, f=fmt[c]: f.format(v) for c in fmt},
    ))
    print()
    print("Interpretation:")
    print("  - High mm_score + high wide_pct → quote inside; capture round trips")
    print("  - High mm_score + low wide_pct → narrow book, only fill at L2 / passive")
    print("  - Low mm_score → vol eats the spread; trend-follow or skip")


if __name__ == "__main__":
    main()
