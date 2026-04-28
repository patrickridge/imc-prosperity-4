"""H12 (Round 5): Are there outlier trade sizes that flag informed flow?

Trader IDs are stripped from R5 trades, but informed traders often leave
a footprint via abnormally large trades. This script:
  - Reports the trade-size distribution per product
  - Flags products with a long right tail (informed activity)
  - Looks at price impact of large trades vs small trades

Run as: python3 research/round5_h12_trade_size.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

DATA_DIR = Path(__file__).parent.parent / "data" / "round5"
DAYS = [2, 3, 4]
LARGE_TRADE_QUANTILE = 0.95
TOP_N = 12


def load_all_trades() -> pd.DataFrame:
    frames = []
    for day in DAYS:
        df = pd.read_csv(DATA_DIR / f"trades_round_5_day_{day}.csv", sep=";")
        df["day"] = day
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def load_all_prices() -> pd.DataFrame:
    frames = []
    for day in DAYS:
        df = pd.read_csv(DATA_DIR / f"prices_round_5_day_{day}.csv", sep=";")
        df["day"] = day
        frames.append(df[["day", "timestamp", "product", "mid_price"]])
    return pd.concat(frames, ignore_index=True)


def size_summary(trades: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for product, g in trades.groupby("symbol"):
        q = g["quantity"]
        rows.append({
            "product": product,
            "n_trades": len(g),
            "median": q.median(),
            "p95": q.quantile(0.95),
            "max": q.max(),
            "tail_ratio": q.quantile(0.95) / q.median() if q.median() > 0 else float("nan"),
        })
    return pd.DataFrame(rows).sort_values("tail_ratio", ascending=False)


def price_impact(trades: pd.DataFrame, prices: pd.DataFrame, product: str) -> dict:
    pt = trades[trades["symbol"] == product].copy()
    pp = prices[prices["product"] == product].copy()
    if pt.empty or pp.empty:
        return {"product": product, "large_impact_bp": float("nan"),
                "small_impact_bp": float("nan")}

    threshold = pt["quantity"].quantile(LARGE_TRADE_QUANTILE)
    pt["is_large"] = pt["quantity"] >= threshold
    merged = pd.merge_asof(
        pt.sort_values("timestamp"),
        pp.sort_values("timestamp"),
        on="timestamp", by="day", direction="backward",
    )
    merged["future_mid"] = merged.groupby("day")["mid_price"].shift(-5)
    merged["impact_bp"] = (merged["future_mid"] - merged["mid_price"]) / merged["mid_price"] * 10000

    large = merged[merged["is_large"]]["impact_bp"].mean()
    small = merged[~merged["is_large"]]["impact_bp"].mean()
    return {"product": product, "large_impact_bp": large, "small_impact_bp": small}


def main() -> None:
    print("=" * 84)
    print("H12: Trade-size distribution + price impact of large trades")
    print("=" * 84)
    print()

    trades = load_all_trades()
    prices = load_all_prices()

    sizes = size_summary(trades)
    print(f"Top {TOP_N} products by tail ratio (p95 / median trade size):")
    print(sizes.head(TOP_N).to_string(index=False,
        float_format=lambda x: f"{x:.2f}"))
    print()

    print(f"Price impact (basis points) 5 ticks after a large (>p95) vs small trade:")
    print()
    impact_rows = [price_impact(trades, prices, p) for p in sizes.head(TOP_N)["product"]]
    impact_df = pd.DataFrame(impact_rows)
    print(impact_df.to_string(index=False, float_format=lambda x: f"{x:+.2f}"))
    print()
    print("Interpretation:")
    print("  - large_impact_bp >> small_impact_bp → big trades move the price (informed)")
    print("  - similar values → trade size carries no information; just MM noise")


if __name__ == "__main__":
    main()
