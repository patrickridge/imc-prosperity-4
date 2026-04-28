"""H8 (Round 5): What latent factors drive returns across the 50 products?

PCA on the 50-product log-return matrix per day. If PC1 explains a large
fraction (>60%), the market has a "common factor" and individual product
strategies bleed into broad market exposure. PC2/PC3 reveal sector-like
structure.

Output:
  - Variance explained per PC
  - PC1 loadings: products with the largest abs loading drive the market
  - For each category, average abs loading on PC1 — indicates whether the
    category moves with the market or has idiosyncratic structure

Run as: python3 research/round5_h8_pca.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

DATA_DIR = Path(__file__).parent.parent / "data" / "round5"
DAYS = [2, 3, 4]
N_PCS_TO_REPORT = 5
TOP_LOADINGS = 8


def load_returns_matrix() -> pd.DataFrame:
    frames = []
    for day in DAYS:
        df = pd.read_csv(DATA_DIR / f"prices_round_5_day_{day}.csv", sep=";")
        pivot = df.pivot_table(index="timestamp", columns="product", values="mid_price")
        log_returns = np.log(pivot).diff().dropna()
        frames.append(log_returns)
    return pd.concat(frames).dropna(axis=1)


def run_pca(returns: pd.DataFrame, n_components: int):
    centered = returns - returns.mean()
    cov = centered.cov().values
    eigvals, eigvecs = np.linalg.eigh(cov)
    order = eigvals.argsort()[::-1]
    eigvals = eigvals[order][:n_components]
    eigvecs = eigvecs[:, order][:, :n_components]
    explained = eigvals / eigvals.sum() if eigvals.sum() > 0 else eigvals
    loadings = pd.DataFrame(eigvecs, index=returns.columns,
                            columns=[f"PC{i+1}" for i in range(n_components)])
    return explained, loadings


def category_of(product: str) -> str:
    for prefix in ["GALAXY_SOUNDS", "SLEEP_POD", "MICROCHIP", "PEBBLES", "ROBOT",
                   "UV_VISOR", "TRANSLATOR", "PANEL", "OXYGEN_SHAKE", "SNACKPACK"]:
        if product.startswith(prefix):
            return prefix
    return "?"


def main() -> None:
    print("=" * 84)
    print("H8: PCA on 50-product log returns — what factors drive the market?")
    print("=" * 84)
    print()

    returns = load_returns_matrix()
    print(f"Return matrix: {returns.shape[0]:,} ticks x {returns.shape[1]} products")
    print()

    explained, loadings = run_pca(returns, n_components=N_PCS_TO_REPORT)

    print("Variance explained per principal component:")
    cumulative = 0.0
    for i, v in enumerate(explained):
        cumulative += v
        print(f"  PC{i+1}: {v*100:>5.1f}%   (cumulative {cumulative*100:.1f}%)")
    print()

    print(f"Top {TOP_LOADINGS} products by |PC1 loading| (the 'market' factor):")
    pc1 = loadings["PC1"].abs().sort_values(ascending=False).head(TOP_LOADINGS)
    for product, val in pc1.items():
        sign = "+" if loadings.loc[product, "PC1"] > 0 else "-"
        print(f"  {product:<32} {sign}{val:.3f}")
    print()

    print("Average |PC1 loading| per category (higher = more market-driven):")
    df = loadings.copy()
    df["category"] = [category_of(p) for p in df.index]
    by_cat = df.groupby("category")["PC1"].apply(lambda s: s.abs().mean())
    for cat, val in by_cat.sort_values(ascending=False).items():
        print(f"  {cat:<14} {val:.3f}")
    print()

    print("Interpretation:")
    print("  - PC1 share > 60% → strong common factor; idiosyncratic strategies will")
    print("    track the market by default. Hedge by being market-neutral.")
    print("  - PC1 share < 40% → products are mostly independent; less hedging needed.")


if __name__ == "__main__":
    main()
