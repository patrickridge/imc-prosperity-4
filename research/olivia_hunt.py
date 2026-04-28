"""
Olivia Hunt: find informed traders ("Mark XX") in R4 trade data.

R4 reveals buyer/seller IDs. We're looking for traders who consistently
buy near daily lows and sell near daily highs — the Olivia pattern from P3.
"""

import pandas as pd
from pathlib import Path

ROUND = 4
DAYS = [1, 2, 3]
DATA_DIR = Path(__file__).parent.parent / "data" / f"round{ROUND}"


def load_trades(day):
    path = DATA_DIR / f"trades_round_{ROUND}_day_{day}.csv"
    return pd.read_csv(path, sep=";")


def load_prices(day):
    path = DATA_DIR / f"prices_round_{ROUND}_day_{day}.csv"
    return pd.read_csv(path, sep=";")


def daily_extremes_by_symbol(prices_df):
    mid = (prices_df["bid_price_1"] + prices_df["ask_price_1"]) / 2
    prices_df = prices_df.assign(mid=mid)
    return prices_df.groupby("product")["mid"].agg(["min", "max"]).to_dict("index")


def trader_extreme_score(trades, extremes, tolerance_frac=0.02):
    """For each trader, count buys near daily low and sells near daily high."""
    rows = []
    for symbol, ext in extremes.items():
        symbol_trades = trades[trades["symbol"] == symbol]
        low_threshold = ext["min"] * (1 + tolerance_frac)
        high_threshold = ext["max"] * (1 - tolerance_frac)

        for trader in set(symbol_trades["buyer"]) | set(symbol_trades["seller"]):
            if pd.isna(trader):
                continue
            buys = symbol_trades[symbol_trades["buyer"] == trader]
            sells = symbol_trades[symbol_trades["seller"] == trader]
            buys_at_low = (buys["price"] <= low_threshold).sum()
            sells_at_high = (sells["price"] >= high_threshold).sum()
            rows.append({
                "trader": trader,
                "symbol": symbol,
                "n_buys": len(buys),
                "buys_at_low": buys_at_low,
                "n_sells": len(sells),
                "sells_at_high": sells_at_high,
                "low_buy_rate": buys_at_low / max(len(buys), 1),
                "high_sell_rate": sells_at_high / max(len(sells), 1),
            })
    return pd.DataFrame(rows)


def run_full_analysis():
    all_results = []
    for day in DAYS:
        trades = load_trades(day)
        prices = load_prices(day)
        extremes = daily_extremes_by_symbol(prices)
        scored = trader_extreme_score(trades, extremes)
        scored["day"] = day
        all_results.append(scored)

    combined = pd.concat(all_results, ignore_index=True)
    return combined


def top_olivia_candidates(combined, min_trades=20):
    summary = combined.groupby("trader").agg(
        total_buys=("n_buys", "sum"),
        total_sells=("n_sells", "sum"),
        total_buys_at_low=("buys_at_low", "sum"),
        total_sells_at_high=("sells_at_high", "sum"),
    ).reset_index()
    summary = summary[summary["total_buys"] + summary["total_sells"] >= min_trades]
    summary["combined_score"] = (
        summary["total_buys_at_low"] / summary["total_buys"].clip(lower=1)
        + summary["total_sells_at_high"] / summary["total_sells"].clip(lower=1)
    )
    return summary.sort_values("combined_score", ascending=False)


if __name__ == "__main__":
    combined = run_full_analysis()
    print("=== TOP OLIVIA CANDIDATES ===")
    print(top_olivia_candidates(combined).head(15).to_string())
    print("\n=== PER SYMBOL BREAKDOWN (TOP TRADER) ===")
    top_trader = top_olivia_candidates(combined).iloc[0]["trader"]
    print(combined[combined["trader"] == top_trader].to_string())
