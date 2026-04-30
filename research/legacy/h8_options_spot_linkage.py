"""
H8: Do VEV option trades predict VE spot price moves?

Mark 22, Mark 01, and Mark 14 all trade VEV options.
If informed flow hits options first, option trade observation
might predict spot direction even after the 1-tick delay.

Test: when bot trades a VEV option at observation time T,
measure VE spot mid change from T to T+k (k=1,5,10,20,50).
"""

import pandas as pd
import numpy as np
from scipy import stats

DATA_DIR = "data/round4"
DAYS = [1, 2, 3]
VE_SPOT = "VELVETFRUIT_EXTRACT"
OPTION_BOTS = ["Mark 22", "Mark 01", "Mark 14"]
LOOKAHEADS = [1, 2, 5, 10, 20, 50]


def load_day(day):
    prices = pd.read_csv(f"{DATA_DIR}/prices_round_4_day_{day}.csv", sep=";")
    trades = pd.read_csv(f"{DATA_DIR}/trades_round_4_day_{day}.csv", sep=";")
    return prices, trades


def get_ve_spot_series(prices):
    """Return sorted arrays of (timestamps, mid_prices) for VE spot."""
    ve = prices[prices["product"] == VE_SPOT][["timestamp", "mid_price"]].copy()
    ve = ve.sort_values("timestamp").reset_index(drop=True)
    return ve["timestamp"].values, ve["mid_price"].values


def get_bot_option_trades(trades, bot):
    """Get all VEV option trades for a bot with direction."""
    vev_symbols = [s for s in trades["symbol"].unique() if s.startswith("VEV_")]

    is_buyer = (trades["buyer"] == bot) & (trades["symbol"].isin(vev_symbols))
    is_seller = (trades["seller"] == bot) & (trades["symbol"].isin(vev_symbols))

    buys = trades[is_buyer].copy()
    buys["direction"] = 1
    sells = trades[is_seller].copy()
    sells["direction"] = -1

    combined = pd.concat([buys, sells]).sort_values("timestamp").reset_index(drop=True)
    return combined


def measure_spot_impact(bot):
    """Measure VE spot move after bot's option trades."""
    results = {la: [] for la in LOOKAHEADS}
    per_day_counts = []
    per_strike_results = {}

    for day in DAYS:
        prices, trades = load_day(day)
        ve_ts, ve_mid = get_ve_spot_series(prices)

        option_trades = get_bot_option_trades(trades, bot)
        if option_trades.empty:
            per_day_counts.append(0)
            continue

        # Aggregate net direction per (timestamp, symbol)
        grouped = option_trades.groupby(["timestamp", "symbol"]).agg(
            net_dir=("direction", "sum"),
            n_trades=("direction", "count"),
        ).reset_index()

        per_day_counts.append(len(grouped))

        for _, row in grouped.iterrows():
            ts = row["timestamp"]
            direction = np.sign(row["net_dir"])
            strike = row["symbol"]
            if direction == 0:
                continue

            # Find VE spot mid at this observation timestamp
            idx = np.searchsorted(ve_ts, ts)
            if idx >= len(ve_ts) or ve_ts[idx] != ts:
                # No exact match — skip
                continue

            base_price = ve_mid[idx]
            for la in LOOKAHEADS:
                future_idx = idx + la
                if future_idx < len(ve_mid):
                    move = direction * (ve_mid[future_idx] - base_price)
                    results[la].append(move)

                    # Per-strike tracking
                    key = (strike, la)
                    if key not in per_strike_results:
                        per_strike_results[key] = []
                    per_strike_results[key].append(move)

    return results, per_day_counts, per_strike_results


def print_results(bot, results, day_counts):
    """Print formatted results."""
    total_n = sum(day_counts)
    print(f"\n  {bot} option trades -> VE spot (n={total_n}, days: {day_counts})")
    print(f"  {'lag':>5} {'mean':>7} {'median':>7} {'t-stat':>7} {'p-val':>7} {'hit%':>6} {'n':>5}")
    print(f"  {'-'*5} {'-'*7} {'-'*7} {'-'*7} {'-'*7} {'-'*6} {'-'*5}")

    for la in LOOKAHEADS:
        vals = results[la]
        if not vals:
            print(f"  {f'+{la}':>5} {'—':>7}")
            continue
        arr = np.array(vals)
        mean = arr.mean()
        median = np.median(arr)
        n = len(arr)
        stderr = arr.std(ddof=1) / np.sqrt(n)
        t_stat = mean / stderr if stderr > 0 else 0
        p_val = 2 * (1 - stats.t.cdf(abs(t_stat), df=n - 1))
        hit = np.mean(arr > 0)
        sig = " *" if p_val < 0.05 else "  " if p_val < 0.10 else ""
        print(
            f"  {f'+{la}':>5} {mean:>+7.2f} {median:>+7.1f} "
            f"{t_stat:>+7.2f} {p_val:>7.4f} {hit:>5.1%} {n:>5}{sig}"
        )


def print_strike_breakdown(bot, per_strike_results):
    """Show results broken down by strike."""
    strikes = sorted(set(k[0] for k in per_strike_results.keys()))
    la_show = 10  # Show t+10 breakdown

    print(f"\n  {bot} per-strike breakdown (t+{la_show}):")
    print(f"  {'strike':<10} {'mean':>7} {'t-stat':>7} {'n':>5}")
    print(f"  {'-'*10} {'-'*7} {'-'*7} {'-'*5}")

    for strike in strikes:
        key = (strike, la_show)
        if key not in per_strike_results or len(per_strike_results[key]) < 5:
            continue
        arr = np.array(per_strike_results[key])
        mean = arr.mean()
        stderr = arr.std(ddof=1) / np.sqrt(len(arr))
        t_stat = mean / stderr if stderr > 0 else 0
        print(f"  {strike:<10} {mean:>+7.2f} {t_stat:>+7.2f} {len(arr):>5}")


def check_timing_overlap(bot):
    """Do option trades happen at same timestamps as spot trades?"""
    print(f"\n  {bot} timing overlap: option vs spot trades")

    for day in DAYS:
        _, trades = load_day(day)
        option_trades = get_bot_option_trades(trades, bot)
        spot_trades = trades[
            ((trades["buyer"] == bot) | (trades["seller"] == bot))
            & (trades["symbol"] == VE_SPOT)
        ]

        opt_ts = set(option_trades["timestamp"].unique())
        spot_ts = set(spot_trades["timestamp"].unique())
        overlap = opt_ts & spot_ts

        print(
            f"    Day {day}: option_ts={len(opt_ts)}, spot_ts={len(spot_ts)}, "
            f"overlap={len(overlap)} ({len(overlap)/max(len(opt_ts),1):.0%})"
        )


def main():
    print("=" * 60)
    print("H8: VEV OPTION TRADES -> VE SPOT PRICE IMPACT")
    print("=" * 60)
    print("\nDo bot option trades predict spot direction?")
    print("Positive mean = option trade predicted spot move correctly.")

    for bot in OPTION_BOTS:
        results, day_counts, per_strike = measure_spot_impact(bot)
        print_results(bot, results, day_counts)
        print_strike_breakdown(bot, per_strike)

    print("\n" + "=" * 60)
    print("TIMING OVERLAP: Do option and spot trades co-occur?")
    print("=" * 60)

    for bot in OPTION_BOTS:
        check_timing_overlap(bot)

    print("\n" + "=" * 60)
    print("INTERPRETATION")
    print("=" * 60)
    print("""
If signal is significant at t+1 but decays: already priced in (same problem as spot).
If signal grows from t+1 to t+10+: genuine lead from options to spot.
If option/spot timestamps overlap heavily: same event, not a lead.
High overlap + no signal growth = options don't add information beyond spot.
Low overlap + signal growth = actionable options-first signal.
""")


if __name__ == "__main__":
    main()
