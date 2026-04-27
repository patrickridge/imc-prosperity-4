"""
Cross-product signal analysis: Do bot trades on VE predict HP price moves (or vice versa)?
"""

import pandas as pd
import numpy as np

DATA_DIR = "data/round4"
DAYS = [1, 2, 3]
LOOKAHEADS = [1, 5, 10, 20]

VE = "VELVETFRUIT_EXTRACT"
HP = "HYDROGEL_PACK"

# Bots of interest
VE_SMART_BUYER = "Mark 67"
VE_DUMB_BOTS = ["Mark 49", "Mark 22"]
HP_BOTS = ["Mark 14", "Mark 38"]


def load_day(day):
    prices = pd.read_csv(f"{DATA_DIR}/prices_round_4_day_{day}.csv", sep=";")
    trades = pd.read_csv(f"{DATA_DIR}/trades_round_4_day_{day}.csv", sep=";")
    return prices, trades


def get_mid_prices(prices, product):
    subset = prices[prices["product"] == product][["timestamp", "mid_price"]].copy()
    subset = subset.sort_values("timestamp").reset_index(drop=True)
    return subset


def price_change_correlation():
    print("=" * 60)
    print("1. VE <-> HP PRICE CHANGE CORRELATION")
    print("=" * 60)

    for day in DAYS:
        prices, _ = load_day(day)
        ve_mid = get_mid_prices(prices, VE).rename(columns={"mid_price": "ve_mid"})
        hp_mid = get_mid_prices(prices, HP).rename(columns={"mid_price": "hp_mid"})

        merged = pd.merge(ve_mid, hp_mid, on="timestamp", how="inner")
        merged["ve_diff"] = merged["ve_mid"].diff()
        merged["hp_diff"] = merged["hp_mid"].diff()
        merged = merged.dropna()

        corr = merged["ve_diff"].corr(merged["hp_diff"])
        print(f"  Day {day}: corr(dVE, dHP) = {corr:.4f}  (n={len(merged)})")

    # Also check lagged correlations
    print("\n  Lagged correlations (Day 1, best day for sample size):")
    prices, _ = load_day(1)
    ve_mid = get_mid_prices(prices, VE).rename(columns={"mid_price": "ve_mid"})
    hp_mid = get_mid_prices(prices, HP).rename(columns={"mid_price": "hp_mid"})
    merged = pd.merge(ve_mid, hp_mid, on="timestamp", how="inner")
    merged["ve_diff"] = merged["ve_mid"].diff()
    merged["hp_diff"] = merged["hp_mid"].diff()
    merged = merged.dropna()

    for lag in [1, 2, 3, 5, 10]:
        # Does VE change predict future HP change?
        corr_ve_leads = merged["ve_diff"].corr(merged["hp_diff"].shift(-lag))
        # Does HP change predict future VE change?
        corr_hp_leads = merged["hp_diff"].corr(merged["ve_diff"].shift(-lag))
        print(f"    lag={lag:2d}:  VE->HP {corr_ve_leads:+.4f}   HP->VE {corr_hp_leads:+.4f}")


def classify_trade_direction(trades, symbol, mark):
    """Return trades with a 'direction' column: +1 if mark is buyer, -1 if seller."""
    is_buyer = (trades["buyer"] == mark) & (trades["symbol"] == symbol)
    is_seller = (trades["seller"] == mark) & (trades["symbol"] == symbol)
    buys = trades[is_buyer].copy()
    buys["direction"] = 1
    sells = trades[is_seller].copy()
    sells["direction"] = -1
    combined = pd.concat([buys, sells]).sort_values("timestamp").reset_index(drop=True)
    return combined


def cross_product_impact(source_mark, source_product, target_product, label):
    """When source_mark trades source_product, what happens to target_product price?"""
    results_by_lookahead = {la: [] for la in LOOKAHEADS}
    total_trades = 0

    for day in DAYS:
        prices, trades = load_day(day)
        target_mid = get_mid_prices(prices, target_product)
        timestamps = target_mid["timestamp"].values
        mid_vals = target_mid["mid_price"].values

        bot_trades = classify_trade_direction(trades, source_product, source_mark)
        if bot_trades.empty:
            continue

        # Aggregate net direction per timestamp
        net_per_ts = bot_trades.groupby("timestamp")["direction"].sum().reset_index()
        total_trades += len(net_per_ts)

        for _, row in net_per_ts.iterrows():
            ts = row["timestamp"]
            direction = np.sign(row["direction"])
            if direction == 0:
                continue

            # Find the index in target_mid closest to this timestamp
            idx = np.searchsorted(timestamps, ts)
            if idx >= len(timestamps):
                continue

            base_price = mid_vals[idx]
            for la in LOOKAHEADS:
                future_idx = idx + la
                if future_idx < len(mid_vals):
                    future_price = mid_vals[future_idx]
                    # Positive = trade predicted target move correctly
                    signed_move = direction * (future_price - base_price)
                    results_by_lookahead[la].append(signed_move)

    print(f"\n  {label} (n={total_trades} trade-timestamps across 3 days):")
    for la in LOOKAHEADS:
        vals = results_by_lookahead[la]
        if not vals:
            print(f"    +{la:2d} ticks: no data")
            continue
        arr = np.array(vals)
        mean = arr.mean()
        stderr = arr.std() / np.sqrt(len(arr)) if len(arr) > 1 else float("inf")
        t_stat = mean / stderr if stderr > 0 else 0
        hit_rate = np.mean(arr > 0)
        print(
            f"    +{la:2d} ticks: mean={mean:+.2f}  "
            f"t={t_stat:+.2f}  hit={hit_rate:.1%}  n={len(arr)}"
        )


def same_product_impact(source_mark, product, label):
    """Sanity check: when mark trades product, what happens to SAME product?"""
    results_by_lookahead = {la: [] for la in LOOKAHEADS}
    total_trades = 0

    for day in DAYS:
        prices, trades = load_day(day)
        mid = get_mid_prices(prices, product)
        timestamps = mid["timestamp"].values
        mid_vals = mid["mid_price"].values

        bot_trades = classify_trade_direction(trades, product, source_mark)
        if bot_trades.empty:
            continue

        net_per_ts = bot_trades.groupby("timestamp")["direction"].sum().reset_index()
        total_trades += len(net_per_ts)

        for _, row in net_per_ts.iterrows():
            ts = row["timestamp"]
            direction = np.sign(row["direction"])
            if direction == 0:
                continue

            idx = np.searchsorted(timestamps, ts)
            if idx >= len(timestamps):
                continue

            base_price = mid_vals[idx]
            for la in LOOKAHEADS:
                future_idx = idx + la
                if future_idx < len(mid_vals):
                    future_price = mid_vals[future_idx]
                    signed_move = direction * (future_price - base_price)
                    results_by_lookahead[la].append(signed_move)

    print(f"\n  {label} (n={total_trades}):")
    for la in LOOKAHEADS:
        vals = results_by_lookahead[la]
        if not vals:
            print(f"    +{la:2d} ticks: no data")
            continue
        arr = np.array(vals)
        mean = arr.mean()
        stderr = arr.std() / np.sqrt(len(arr)) if len(arr) > 1 else float("inf")
        t_stat = mean / stderr if stderr > 0 else 0
        hit_rate = np.mean(arr > 0)
        print(
            f"    +{la:2d} ticks: mean={mean:+.2f}  "
            f"t={t_stat:+.2f}  hit={hit_rate:.1%}  n={len(arr)}"
        )


def main():
    # Part 1: Price correlation
    price_change_correlation()

    # Part 2: Same-product sanity checks
    print("\n" + "=" * 60)
    print("2. SAME-PRODUCT IMPACT (sanity check)")
    print("=" * 60)

    same_product_impact(VE_SMART_BUYER, VE, f"{VE_SMART_BUYER} trades VE -> VE price")
    for mark in VE_DUMB_BOTS:
        same_product_impact(mark, VE, f"{mark} trades VE -> VE price")
    for mark in HP_BOTS:
        same_product_impact(mark, HP, f"{mark} trades HP -> HP price")

    # Part 3: Cross-product impact - VE bots -> HP price
    print("\n" + "=" * 60)
    print("3. CROSS-PRODUCT: VE BOT TRADES -> HP PRICE")
    print("=" * 60)

    cross_product_impact(
        VE_SMART_BUYER, VE, HP, f"{VE_SMART_BUYER} trades VE -> HP price"
    )
    for mark in VE_DUMB_BOTS:
        cross_product_impact(mark, VE, HP, f"{mark} trades VE -> HP price")

    # Part 4: Cross-product impact - HP bots -> VE price
    print("\n" + "=" * 60)
    print("4. CROSS-PRODUCT: HP BOT TRADES -> VE PRICE")
    print("=" * 60)

    for mark in HP_BOTS:
        cross_product_impact(mark, HP, VE, f"{mark} trades HP -> VE price")

    # Part 5: Cross-trading bots (Mark 14, 22 trade BOTH products)
    print("\n" + "=" * 60)
    print("5. DUAL-PRODUCT BOTS: Mark 14 & Mark 22 trade both VE and HP")
    print("=" * 60)

    cross_product_impact("Mark 14", VE, HP, "Mark 14 trades VE -> HP price")
    cross_product_impact("Mark 14", HP, VE, "Mark 14 trades HP -> VE price")
    cross_product_impact("Mark 22", VE, HP, "Mark 22 trades VE -> HP price")
    cross_product_impact("Mark 22", HP, VE, "Mark 22 trades HP -> VE price")


if __name__ == "__main__":
    main()
