"""
Round 5 algo: first-pass exploration over all 50 products and 3 days.

Output: a single tabular summary printed to stdout. Lead with insight.

  python3 research/round5_explore.py
  python3 research/round5_explore.py --category PEBBLES   # zoom one group
  python3 research/round5_explore.py --plot               # save PNG to research/findings/
"""
from __future__ import annotations

import argparse
import os
from collections import defaultdict
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "round5"
DAYS = [2, 3, 4]

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


def product_to_category(product: str) -> str:
    for cat in CATEGORIES:
        if product.startswith(cat):
            return cat
    return "UNKNOWN"


def load_all_days() -> pd.DataFrame:
    frames = []
    for day in DAYS:
        path = DATA_DIR / f"prices_round_5_day_{day}.csv"
        df = pd.read_csv(path, sep=";")
        df["day"] = day
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def per_product_stats(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for product, g in df.groupby("product"):
        mid = g["mid_price"].dropna()
        first, last = mid.iloc[0], mid.iloc[-1]
        rows.append({
            "category": product_to_category(product),
            "product": product,
            "min": mid.min(),
            "max": mid.max(),
            "mean": mid.mean(),
            "std": mid.std(),
            "range_pct": (mid.max() - mid.min()) / mid.mean() * 100,
            "drift_pct": (last - first) / first * 100,
        })
    return pd.DataFrame(rows).sort_values(["category", "range_pct"], ascending=[True, False])


def category_correlation(df: pd.DataFrame, category: str) -> pd.DataFrame:
    products = [f"{category}_{v}" for v in CATEGORIES[category]]
    pivot = df[df["product"].isin(products)].pivot_table(
        index=["day", "timestamp"], columns="product", values="mid_price"
    )
    return pivot.corr()


def print_summary(stats: pd.DataFrame) -> None:
    pd.set_option("display.width", 120)
    pd.set_option("display.max_rows", 60)

    print("=" * 78)
    print("Round 5 algo — per-product mid-price summary (3 days combined)")
    print("=" * 78)
    cols = ["category", "product", "mean", "std", "range_pct", "drift_pct"]
    print(stats[cols].to_string(index=False, float_format=lambda x: f"{x:.2f}"))

    print()
    print("=" * 78)
    print("Category dispersion (mean range_pct, sorted high-to-low — "
          "where the action is)")
    print("=" * 78)
    by_cat = stats.groupby("category")[["range_pct", "std"]].mean().sort_values(
        "range_pct", ascending=False)
    print(by_cat.to_string(float_format=lambda x: f"{x:.2f}"))

    print()
    print("=" * 78)
    print("Top 5 most volatile products and biggest drifts")
    print("=" * 78)
    print("\nMost volatile:")
    print(stats.nlargest(5, "range_pct")[cols].to_string(index=False, float_format=lambda x: f"{x:.2f}"))
    print("\nBiggest absolute drift over 3 days:")
    drifts = stats.assign(abs_drift=stats["drift_pct"].abs()).nlargest(5, "abs_drift")
    print(drifts[cols].to_string(index=False, float_format=lambda x: f"{x:.2f}"))


def print_category_corr(df: pd.DataFrame, category: str) -> None:
    print()
    print("=" * 78)
    print(f"Within-{category} correlation matrix (mid_price, all 3 days)")
    print("=" * 78)
    corr = category_correlation(df, category)
    print(corr.to_string(float_format=lambda x: f"{x:+.2f}"))


def maybe_save_plot(df: pd.DataFrame, category: str | None) -> None:
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not installed — skipping plot")
        return

    out_dir = Path(__file__).resolve().parent / "findings"
    out_dir.mkdir(exist_ok=True)
    targets = [category] if category else list(CATEGORIES.keys())

    for cat in targets:
        products = [f"{cat}_{v}" for v in CATEGORIES[cat]]
        sub = df[df["product"].isin(products)].copy()
        if sub.empty:
            continue
        sub["t"] = sub["day"] * 1_000_000 + sub["timestamp"]
        fig, ax = plt.subplots(figsize=(10, 4))
        for prod, g in sub.groupby("product"):
            ax.plot(g["t"], g["mid_price"], label=prod.replace(cat + "_", ""), linewidth=0.8)
        ax.set_title(f"{cat} mid-prices — round 5 days {DAYS}")
        ax.legend(loc="upper right", fontsize=8)
        ax.set_xlabel("day*1M + timestamp")
        ax.set_ylabel("mid")
        out = out_dir / f"round5_{cat.lower()}.png"
        fig.tight_layout()
        fig.savefig(out, dpi=120)
        plt.close(fig)
        print(f"saved {out}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--category", help="restrict to one category (e.g. PEBBLES)")
    parser.add_argument("--plot", action="store_true", help="save mid-price PNGs")
    args = parser.parse_args()

    df = load_all_days()
    stats = per_product_stats(df)

    if args.category:
        stats = stats[stats["category"] == args.category]

    print_summary(stats)

    if args.category:
        print_category_corr(df, args.category)
    else:
        for cat in CATEGORIES:
            print_category_corr(df, cat)

    if args.plot:
        maybe_save_plot(df, args.category)


if __name__ == "__main__":
    main()
