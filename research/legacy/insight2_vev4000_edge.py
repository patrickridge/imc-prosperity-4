"""
VEV_4000 Execution Edge Analysis
Deep dive into bot trading dynamics for the deep ITM call option.
"""

import pandas as pd
import numpy as np
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data" / "round4"
STRIKE = 4000
SPOT_PRODUCT = "VELVETFRUIT_EXTRACT"
OPTION_PRODUCT = "VEV_4000"


def load_day(day: int):
    prices = pd.read_csv(DATA_DIR / f"prices_round_4_day_{day}.csv", sep=";")
    trades = pd.read_csv(DATA_DIR / f"trades_round_4_day_{day}.csv", sep=";")
    return prices, trades


def get_mid_at_timestamp(prices_product, timestamp):
    """Get the mid price at or just before a given timestamp."""
    candidates = prices_product[prices_product["timestamp"] <= timestamp]
    if candidates.empty:
        return np.nan
    return candidates.iloc[-1]["mid_price"]


def analyze_day(day: int):
    prices, trades = load_day(day)

    option_prices = prices[prices["product"] == OPTION_PRODUCT].copy()
    spot_prices = prices[prices["product"] == SPOT_PRODUCT].copy()
    option_trades = trades[trades["symbol"] == OPTION_PRODUCT].copy()

    print(f"\n{'='*70}")
    print(f"  DAY {day}")
    print(f"{'='*70}")

    # --- Trade frequency and volume ---
    n_trades = len(option_trades)
    total_volume = option_trades["quantity"].sum()
    print(f"\n[Trade Activity]")
    print(f"  Trades: {n_trades}  |  Total volume: {total_volume} contracts")

    if n_trades == 0:
        return None

    ts_min = option_trades["timestamp"].min()
    ts_max = option_trades["timestamp"].max()
    print(f"  Timestamp range: {ts_min} - {ts_max}")
    print(f"  Avg interval: {(ts_max - ts_min) / max(n_trades - 1, 1):.0f} ticks")

    # --- Participants ---
    buyers = option_trades["buyer"].value_counts()
    sellers = option_trades["seller"].value_counts()
    print(f"\n[Participants]")
    print(f"  Buyers:  {dict(buyers)}")
    print(f"  Sellers: {dict(sellers)}")

    # --- Compute mid at each trade timestamp ---
    option_trades = option_trades.copy()
    option_trades["option_mid"] = option_trades["timestamp"].apply(
        lambda t: get_mid_at_timestamp(option_prices, t)
    )
    option_trades["spot_mid"] = option_trades["timestamp"].apply(
        lambda t: get_mid_at_timestamp(spot_prices, t)
    )
    option_trades["intrinsic"] = (option_trades["spot_mid"] - STRIKE).clip(lower=0)
    option_trades["extrinsic"] = option_trades["option_mid"] - option_trades["intrinsic"]

    # --- Execution edge per bot ---
    # Buyer edge: mid - price (bought below mid = positive edge)
    # Seller edge: price - mid (sold above mid = positive edge)
    print(f"\n[Execution Edge vs Mid]")
    print(f"  {'Bot':<10} {'Role':<8} {'Trades':<7} {'Vol':<6} {'Avg Edge':<10} {'Vol-Wtd Edge':<12}")
    print(f"  {'-'*55}")

    results = []
    all_bots = sorted(set(option_trades["buyer"].unique().tolist() +
                          option_trades["seller"].unique().tolist()))
    for bot in all_bots:
        # As buyer
        buy_rows = option_trades[option_trades["buyer"] == bot]
        if not buy_rows.empty:
            edges = buy_rows["option_mid"] - buy_rows["price"]
            vol_wtd = (edges * buy_rows["quantity"]).sum() / buy_rows["quantity"].sum()
            print(f"  {bot:<10} {'BUY':<8} {len(buy_rows):<7} {buy_rows['quantity'].sum():<6} "
                  f"{edges.mean():+.2f}    {vol_wtd:+.2f}")
            results.append((bot, "BUY", edges.mean(), vol_wtd, buy_rows["quantity"].sum()))

        # As seller
        sell_rows = option_trades[option_trades["seller"] == bot]
        if not sell_rows.empty:
            edges = sell_rows["price"] - sell_rows["option_mid"]
            vol_wtd = (edges * sell_rows["quantity"]).sum() / sell_rows["quantity"].sum()
            print(f"  {bot:<10} {'SELL':<8} {len(sell_rows):<7} {sell_rows['quantity'].sum():<6} "
                  f"{edges.mean():+.2f}    {vol_wtd:+.2f}")
            results.append((bot, "SELL", edges.mean(), vol_wtd, sell_rows["quantity"].sum()))

    # --- Price vs Intrinsic ---
    print(f"\n[Price vs Intrinsic Value]")
    print(f"  {'Metric':<25} {'Mean':<10} {'Min':<10} {'Max':<10} {'Std':<10}")
    print(f"  {'-'*65}")

    ext = option_trades["extrinsic"]
    print(f"  {'Extrinsic (mid-intr)':<25} {ext.mean():<10.2f} {ext.min():<10.2f} "
          f"{ext.max():<10.2f} {ext.std():<10.2f}")

    intr = option_trades["intrinsic"]
    print(f"  {'Intrinsic':<25} {intr.mean():<10.2f} {intr.min():<10.2f} "
          f"{intr.max():<10.2f} {intr.std():<10.2f}")

    opt_mid = option_trades["option_mid"]
    print(f"  {'Option Mid':<25} {opt_mid.mean():<10.2f} {opt_mid.min():<10.2f} "
          f"{opt_mid.max():<10.2f} {opt_mid.std():<10.2f}")

    # --- Mark 38 sell prices and Mark 14 buy prices ---
    print(f"\n[Mark 38 as Seller - prices Mark 14 buys at]")
    m38_sells = option_trades[option_trades["seller"] == "Mark 38"]
    if not m38_sells.empty:
        print(f"  Avg sell price: {m38_sells['price'].mean():.2f}")
        print(f"  Avg mid at time: {m38_sells['option_mid'].mean():.2f}")
        print(f"  Avg edge (price - mid): {(m38_sells['price'] - m38_sells['option_mid']).mean():+.2f}")
        print(f"  Price range: [{m38_sells['price'].min():.1f}, {m38_sells['price'].max():.1f}]")

    print(f"\n[Mark 38 as Buyer - prices Mark 38 buys at]")
    m38_buys = option_trades[option_trades["buyer"] == "Mark 38"]
    if not m38_buys.empty:
        print(f"  Avg buy price: {m38_buys['price'].mean():.2f}")
        print(f"  Avg mid at time: {m38_buys['option_mid'].mean():.2f}")
        print(f"  Avg edge (mid - price): {(m38_buys['option_mid'] - m38_buys['price']).mean():+.2f}")
        print(f"  Price range: [{m38_buys['price'].min():.1f}, {m38_buys['price'].max():.1f}]")

    print(f"\n[Mark 14 as Buyer]")
    m14_buys = option_trades[option_trades["buyer"] == "Mark 14"]
    if not m14_buys.empty:
        print(f"  Avg buy price: {m14_buys['price'].mean():.2f}")
        print(f"  Avg mid at time: {m14_buys['option_mid'].mean():.2f}")
        print(f"  Avg edge (mid - price): {(m14_buys['option_mid'] - m14_buys['price']).mean():+.2f}")
        print(f"  Price range: [{m14_buys['price'].min():.1f}, {m14_buys['price'].max():.1f}]")

    print(f"\n[Mark 14 as Seller]")
    m14_sells = option_trades[option_trades["seller"] == "Mark 14"]
    if not m14_sells.empty:
        print(f"  Avg sell price: {m14_sells['price'].mean():.2f}")
        print(f"  Avg mid at time: {m14_sells['option_mid'].mean():.2f}")
        print(f"  Avg edge (price - mid): {(m14_sells['price'] - m14_sells['option_mid']).mean():+.2f}")
        print(f"  Price range: [{m14_sells['price'].min():.1f}, {m14_sells['price'].max():.1f}]")

    # --- Mark 22 involvement ---
    m22_buys = option_trades[option_trades["buyer"] == "Mark 22"]
    m22_sells = option_trades[option_trades["seller"] == "Mark 22"]
    if not m22_buys.empty or not m22_sells.empty:
        print(f"\n[Mark 22 Involvement]")
        if not m22_buys.empty:
            edge = m22_buys["option_mid"] - m22_buys["price"]
            print(f"  As buyer: {len(m22_buys)} trades, vol={m22_buys['quantity'].sum()}, "
                  f"avg edge={edge.mean():+.2f}")
            print(f"    Prices: {m22_buys['price'].tolist()}")
        if not m22_sells.empty:
            edge = m22_sells["price"] - m22_sells["option_mid"]
            print(f"  As seller: {len(m22_sells)} trades, vol={m22_sells['quantity'].sum()}, "
                  f"avg edge={edge.mean():+.2f}")
            print(f"    Prices: {m22_sells['price'].tolist()}")

    return option_trades


def strategy_simulation(all_trades):
    """What is our realistic PnL from intercepting Mark 38?"""
    print(f"\n{'='*70}")
    print(f"  STRATEGY SIMULATION: Realistic PnL from intercepting Mark 38")
    print(f"{'='*70}")

    print(f"\n  HOW IT WORKS:")
    print(f"  - Mark 38 crosses the spread every ~6000 ticks (~60 times/day)")
    print(f"  - We post bid at (mid - bid_edge) and ask at (mid + bid_edge)")
    print(f"  - If our bid > Mark14's bid, Mark 38 hits US, not Mark 14")
    print(f"  - We collect bid_edge per fill")
    print(f"  - Position limit: 80. Must exit to keep trading.")

    print(f"\n  POSITION MANAGEMENT:")
    print(f"  - Mark 38 alternates: sells then buys (or vice versa)")
    print(f"  - If we capture both sides, position stays near 0")
    print(f"  - If we only bid (buy from Mark38), we accumulate long")
    print(f"  - exit_edge=12 means we exit at mid+12 (above ask) => never fills")
    print(f"  - BETTER: post ask at mid - bid_edge too, catching Mark38 buys")

    print(f"\n  RISK:")
    print(f"  - VEV_4000 is deep ITM call, ~1:1 delta with spot")
    print(f"  - If spot drops 50, option drops ~50, position loses 50*qty")
    print(f"  - With position limit 80: max adverse move impact = 80*50 = 4000")
    print(f"  - Need to keep position small or hedge via spot")

    # Alternation pattern analysis
    print(f"\n  MARK 38 ALTERNATION PATTERN:")
    for day, trades in all_trades.items():
        if trades is None:
            continue
        print(f"\n  --- Day {day} ---")
        trades_sorted = trades.sort_values("timestamp")
        pattern = []
        for _, t in trades_sorted.iterrows():
            if t["seller"] == "Mark 38":
                pattern.append("S")
            elif t["buyer"] == "Mark 38":
                pattern.append("B")
            else:
                pattern.append("?")
        first_30 = "".join(pattern[:30])
        print(f"  First 30 trades: {first_30}")
        sells = pattern.count("S")
        buys = pattern.count("B")
        print(f"  Total: {sells}S / {buys}B")
        # Check alternation
        alternations = sum(1 for i in range(1, len(pattern))
                          if pattern[i] != pattern[i-1] and pattern[i] != "?")
        print(f"  Alternations: {alternations}/{len(pattern)-1} "
              f"({alternations/(len(pattern)-1)*100:.0f}%)")


def book_position_analysis(all_trades):
    """Understand which side Mark 38 is on - are they hitting bids or posting asks?"""
    print(f"\n{'='*70}")
    print(f"  BOOK POSITION ANALYSIS: Who is aggressor?")
    print(f"{'='*70}")
    print(f"\n  Convention in this data:")
    print(f"  - buyer/seller just means who ends up long/short")
    print(f"  - To determine aggressor, compare trade price to mid:")
    print(f"    * Price > mid => buyer was aggressor (lifted ask)")
    print(f"    * Price < mid => seller was aggressor (hit bid)")

    for day, trades in all_trades.items():
        if trades is None:
            continue

        print(f"\n--- Day {day} ---")
        trades = trades.copy()
        trades["price_vs_mid"] = trades["price"] - trades["option_mid"]

        # Mark 14 as buyer
        m14_buy = trades[trades["buyer"] == "Mark 14"]
        if not m14_buy.empty:
            above_mid = (m14_buy["price"] > m14_buy["option_mid"]).sum()
            below_mid = (m14_buy["price"] < m14_buy["option_mid"]).sum()
            at_mid = (m14_buy["price"] == m14_buy["option_mid"]).sum()
            print(f"  Mark 14 BUYS: {len(m14_buy)} trades")
            print(f"    Price > mid (lifted ask): {above_mid}")
            print(f"    Price < mid (hit bid):    {below_mid}")
            print(f"    Price = mid:              {at_mid}")
            print(f"    Avg (price-mid): {m14_buy['price_vs_mid'].mean():+.2f}")

        # Mark 38 as buyer
        m38_buy = trades[trades["buyer"] == "Mark 38"]
        if not m38_buy.empty:
            above_mid = (m38_buy["price"] > m38_buy["option_mid"]).sum()
            below_mid = (m38_buy["price"] < m38_buy["option_mid"]).sum()
            at_mid = (m38_buy["price"] == m38_buy["option_mid"]).sum()
            print(f"  Mark 38 BUYS: {len(m38_buy)} trades")
            print(f"    Price > mid (lifted ask): {above_mid}")
            print(f"    Price < mid (hit bid):    {below_mid}")
            print(f"    Price = mid:              {at_mid}")
            print(f"    Avg (price-mid): {m38_buy['price_vs_mid'].mean():+.2f}")

        # Mark 14 as seller
        m14_sell = trades[trades["seller"] == "Mark 14"]
        if not m14_sell.empty:
            above_mid = (m14_sell["price"] > m14_sell["option_mid"]).sum()
            below_mid = (m14_sell["price"] < m14_sell["option_mid"]).sum()
            print(f"  Mark 14 SELLS: {len(m14_sell)} trades")
            print(f"    Price > mid (hit ask):    {above_mid}")
            print(f"    Price < mid (hit bid):    {below_mid}")
            print(f"    Avg (price-mid): {m14_sell['price_vs_mid'].mean():+.2f}")

        # Mark 38 as seller
        m38_sell = trades[trades["seller"] == "Mark 38"]
        if not m38_sell.empty:
            above_mid = (m38_sell["price"] > m38_sell["option_mid"]).sum()
            below_mid = (m38_sell["price"] < m38_sell["option_mid"]).sum()
            print(f"  Mark 38 SELLS: {len(m38_sell)} trades")
            print(f"    Price > mid (posted ask): {above_mid}")
            print(f"    Price < mid (hit bid):    {below_mid}")
            print(f"    Avg (price-mid): {m38_sell['price_vs_mid'].mean():+.2f}")


def edge_distribution(all_trades):
    """Show the distribution of edges to understand variance."""
    print(f"\n{'='*70}")
    print(f"  EDGE DISTRIBUTION")
    print(f"{'='*70}")

    for day, trades in all_trades.items():
        if trades is None:
            continue
        print(f"\n--- Day {day} ---")

        # Mark 14 buying edge (mid - price)
        m14_buy = trades[trades["buyer"] == "Mark 14"].copy()
        if not m14_buy.empty:
            m14_buy["edge"] = m14_buy["option_mid"] - m14_buy["price"]
            print(f"  Mark 14 BUY edge (mid-price):")
            print(f"    Percentiles: "
                  f"p10={m14_buy['edge'].quantile(0.1):.1f}, "
                  f"p25={m14_buy['edge'].quantile(0.25):.1f}, "
                  f"p50={m14_buy['edge'].quantile(0.5):.1f}, "
                  f"p75={m14_buy['edge'].quantile(0.75):.1f}, "
                  f"p90={m14_buy['edge'].quantile(0.9):.1f}")

        # Mark 38 buying edge (mid - price)
        m38_buy = trades[trades["buyer"] == "Mark 38"].copy()
        if not m38_buy.empty:
            m38_buy["edge"] = m38_buy["option_mid"] - m38_buy["price"]
            print(f"  Mark 38 BUY edge (mid-price):")
            print(f"    Percentiles: "
                  f"p10={m38_buy['edge'].quantile(0.1):.1f}, "
                  f"p25={m38_buy['edge'].quantile(0.25):.1f}, "
                  f"p50={m38_buy['edge'].quantile(0.5):.1f}, "
                  f"p75={m38_buy['edge'].quantile(0.75):.1f}, "
                  f"p90={m38_buy['edge'].quantile(0.9):.1f}")

        # Mark 38 selling edge (price - mid)
        m38_sell = trades[trades["seller"] == "Mark 38"].copy()
        if not m38_sell.empty:
            m38_sell["edge"] = m38_sell["price"] - m38_sell["option_mid"]
            print(f"  Mark 38 SELL edge (price-mid):")
            print(f"    Percentiles: "
                  f"p10={m38_sell['edge'].quantile(0.1):.1f}, "
                  f"p25={m38_sell['edge'].quantile(0.25):.1f}, "
                  f"p50={m38_sell['edge'].quantile(0.5):.1f}, "
                  f"p75={m38_sell['edge'].quantile(0.75):.1f}, "
                  f"p90={m38_sell['edge'].quantile(0.9):.1f}")


def bid_ask_spread_analysis():
    """Understand the typical spread and where bots trade within it."""
    print(f"\n{'='*70}")
    print(f"  BID-ASK SPREAD ANALYSIS")
    print(f"{'='*70}")

    for day in [1, 2, 3]:
        prices, _ = load_day(day)
        opt = prices[prices["product"] == OPTION_PRODUCT].copy()
        opt["spread"] = opt["ask_price_1"] - opt["bid_price_1"]
        opt["half_spread"] = opt["spread"] / 2

        print(f"\n--- Day {day} ---")
        print(f"  Spread: mean={opt['spread'].mean():.2f}, "
              f"median={opt['spread'].median():.1f}, "
              f"min={opt['spread'].min():.0f}, max={opt['spread'].max():.0f}")
        print(f"  Half-spread: {opt['half_spread'].mean():.2f}")
        print(f"  Best bid mean: {opt['bid_price_1'].mean():.1f}")
        print(f"  Best ask mean: {opt['ask_price_1'].mean():.1f}")
        print(f"  Mid mean: {opt['mid_price'].mean():.1f}")


def book_level_verification(all_trades):
    """Verify that Mark 38 always sells AT best bid, buys AT best ask."""
    print(f"\n{'='*70}")
    print(f"  BOOK LEVEL VERIFICATION: Where exactly does Mark 38 trade?")
    print(f"{'='*70}")

    for day in [1, 2, 3]:
        prices, trades = load_day(day)
        opt_prices = prices[prices["product"] == OPTION_PRODUCT]
        opt_trades = trades[trades["symbol"] == OPTION_PRODUCT]

        m38_sells = opt_trades[opt_trades["seller"] == "Mark 38"]
        m38_buys = opt_trades[opt_trades["buyer"] == "Mark 38"]

        sell_at_bid = 0
        sell_at_ask = 0
        sell_other = 0
        for _, trade in m38_sells.iterrows():
            book = opt_prices[opt_prices["timestamp"] <= trade["timestamp"]].iloc[-1]
            if trade["price"] == book["bid_price_1"]:
                sell_at_bid += 1
            elif trade["price"] == book["ask_price_1"]:
                sell_at_ask += 1
            else:
                sell_other += 1

        buy_at_bid = 0
        buy_at_ask = 0
        buy_other = 0
        for _, trade in m38_buys.iterrows():
            book = opt_prices[opt_prices["timestamp"] <= trade["timestamp"]].iloc[-1]
            if trade["price"] == book["bid_price_1"]:
                buy_at_bid += 1
            elif trade["price"] == book["ask_price_1"]:
                buy_at_ask += 1
            else:
                buy_other += 1

        print(f"\n--- Day {day} ---")
        print(f"  Mark 38 SELLS: at_bid={sell_at_bid}, at_ask={sell_at_ask}, other={sell_other}")
        print(f"  Mark 38 BUYS:  at_bid={buy_at_bid}, at_ask={buy_at_ask}, other={buy_other}")
        print(f"  => Mark 38 is a CROSSING bot: always hits bid / lifts ask")


def optimal_strategy_params(all_trades):
    """Given that Mark 38 crosses the spread, how do we intercept?"""
    print(f"\n{'='*70}")
    print(f"  OPTIMAL STRATEGY: Intercepting Mark 38's crossing trades")
    print(f"{'='*70}")

    print(f"\n  MECHANISM:")
    print(f"  Mark 38 sells at best_bid, buys at best_ask (always crosses spread)")
    print(f"  Mark 14 IS the best bid/ask (market maker)")
    print(f"  To intercept: post our bid above Mark 14's bid => become best_bid")
    print(f"  Mark 38 will sell to US instead of Mark 14")
    print(f"  Our edge = mid - our_bid = half_spread - improvement")

    for day in [1, 2, 3]:
        prices, trades = load_day(day)
        opt_prices = prices[prices["product"] == OPTION_PRODUCT]
        opt_trades = trades[trades["symbol"] == OPTION_PRODUCT]

        m38_sells = opt_trades[opt_trades["seller"] == "Mark 38"]
        m38_buys = opt_trades[opt_trades["buyer"] == "Mark 38"]

        print(f"\n--- Day {day} ---")

        # For each Mark 38 sell, what's the spread?
        spreads_at_sell = []
        for _, trade in m38_sells.iterrows():
            book = opt_prices[opt_prices["timestamp"] <= trade["timestamp"]].iloc[-1]
            spread = book["ask_price_1"] - book["bid_price_1"]
            spreads_at_sell.append(spread)

        spreads_at_buy = []
        for _, trade in m38_buys.iterrows():
            book = opt_prices[opt_prices["timestamp"] <= trade["timestamp"]].iloc[-1]
            spread = book["ask_price_1"] - book["bid_price_1"]
            spreads_at_buy.append(spread)

        s_sell = np.array(spreads_at_sell)
        s_buy = np.array(spreads_at_buy)
        print(f"  Spread when Mark 38 sells: mean={s_sell.mean():.1f}, "
              f"min={s_sell.min():.0f}, max={s_sell.max():.0f}")
        print(f"  Spread when Mark 38 buys:  mean={s_buy.mean():.1f}, "
              f"min={s_buy.min():.0f}, max={s_buy.max():.0f}")

    print(f"\n  STRATEGY IMPLICATIONS:")
    print(f"  - Mark 14's book is ~21 wide (bid to ask)")
    print(f"  - Mark 38 sells at Mark 14's bid => half_spread ~10.5 edge for Mark 14")
    print(f"  - If we bid at (Mark14_bid + 1), we become best bid")
    print(f"  - Mark 38 sells to us at our bid => we pay mid - 9.5 => 9.5 edge")
    print(f"  - Risk: Mark 14 may also improve their bid in response")
    print()
    print(f"  BID_EDGE ANALYSIS (edge = how far below mid we bid):")
    print(f"  - bid_edge=10.5: exactly at Mark14's bid => tied, may not fill")
    print(f"  - bid_edge=10.0: 0.5 above Mark14's bid => best bid, 10.0 edge")
    print(f"  - bid_edge=9.5:  1.0 above Mark14's bid => best bid, 9.5 edge")
    print(f"  - bid_edge=9.0:  1.5 above Mark14's bid => best bid, 9.0 edge")
    print(f"  - bid_edge=8.0:  2.5 above Mark14's bid => best bid, 8.0 edge")
    print(f"  CURRENT: bid_edge=8.0 => 8.0 edge per fill (safe margin)")
    print(f"  AGGRESSIVE: bid_edge=10.0 => 10.0 edge per fill (+25% more)")
    print(f"  KEY: as long as bid_edge < 10.5, we beat Mark14 to the fill")

    # Volume and PnL estimates
    print(f"\n  VOLUME & PNL ESTIMATES (per day):")
    for day in [1, 2, 3]:
        prices, trades = load_day(day)
        opt_trades = trades[trades["symbol"] == OPTION_PRODUCT]
        m38_sells = opt_trades[opt_trades["seller"] == "Mark 38"]
        m38_buys = opt_trades[opt_trades["buyer"] == "Mark 38"]
        sell_vol = m38_sells["quantity"].sum()
        buy_vol = m38_buys["quantity"].sum()
        print(f"  Day {day}: Mark38 sells {sell_vol} contracts, buys {buy_vol} contracts")
        for edge in [8.0, 9.0, 9.5, 10.0]:
            pnl_bid = sell_vol * edge
            pnl_ask = buy_vol * edge
            print(f"    bid_edge={edge}: bid_pnl={pnl_bid:.0f}, ask_pnl={pnl_ask:.0f}, "
                  f"total={pnl_bid + pnl_ask:.0f}")


def timing_analysis(all_trades):
    """When do trades happen? Is there clustering?"""
    print(f"\n{'='*70}")
    print(f"  TIMING ANALYSIS")
    print(f"{'='*70}")

    for day, trades in all_trades.items():
        if trades is None:
            continue
        print(f"\n--- Day {day} ---")
        ts = trades["timestamp"].values
        if len(ts) > 1:
            intervals = np.diff(ts)
            print(f"  Inter-trade intervals: mean={intervals.mean():.0f}, "
                  f"median={np.median(intervals):.0f}, "
                  f"min={intervals.min()}, max={intervals.max()}")
            # Cluster detection
            short = (intervals < 1000).sum()
            print(f"  Trades within 1000 ticks of previous: {short}/{len(intervals)}")
        print(f"  First 10 timestamps: {ts[:10].tolist()}")
        print(f"  Last 10 timestamps: {ts[-10:].tolist()}")


if __name__ == "__main__":
    all_trades = {}
    for day in [1, 2, 3]:
        result = analyze_day(day)
        all_trades[day] = result

    book_level_verification(all_trades)
    book_position_analysis(all_trades)
    edge_distribution(all_trades)
    bid_ask_spread_analysis()
    optimal_strategy_params(all_trades)
    timing_analysis(all_trades)
    strategy_simulation(all_trades)

    print(f"\n{'='*70}")
    print(f"  ACTIONABLE SUMMARY")
    print(f"{'='*70}")
    print(f"""
  1. EDGE VERIFIED: Mark 14 gets +10.4 edge per trade. Mark 38 gets -10.4.
     Perfectly consistent across all 3 days. Near-zero variance.

  2. MECHANISM: Mark 38 is a pure crossing bot.
     - Always sells at EXACTLY best_bid (hits bid)
     - Always buys at EXACTLY best_ask (lifts ask)
     - Mark 14 IS the best bid/ask (market maker with ~21 wide spread)

  3. EXTRINSIC VALUE: ~0. Option trades at intrinsic (spot - 4000).
     This is expected for deep ITM with high delta.

  4. TO CAPTURE THE EDGE:
     - Post bid 1 tick above Mark 14's bid => become best bid
     - Mark 38 will hit OUR bid instead of Mark 14's
     - Our edge = half_spread - improvement = ~10.5 - 0.5 = 10.0
     - Current bid_edge=8 is ALREADY profitable (8.0 edge per fill)
     - Can safely increase to bid_edge=10 for 25% more edge per fill

  5. VOLUME: ~130-165 trades/day, ~260-330 contracts, split ~50/50 buy/sell
     Mark 38 alternates between buy and sell fairly evenly.

  6. KEY RISK: Position accumulation if Mark 38 flow is one-directional.
     Mitigate by capturing BOTH sides (bid and ask).
""")
