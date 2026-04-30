"""
Compute mean implied vol per strike per day using correct historical TTE.
TTE: day 0 = 8 days, day 1 = 7 days, day 2 = 6 days.
"""
from math import log, sqrt, exp, erf
import pandas as pd

STRIKES = {
    "VEV_4000": 4000, "VEV_4500": 4500, "VEV_5000": 5000, "VEV_5100": 5100,
    "VEV_5200": 5200, "VEV_5300": 5300, "VEV_5400": 5400, "VEV_5500": 5500,
}
TTE_DAYS = {0: 8.0, 1: 7.0, 2: 6.0}


def norm_cdf(x):
    return 0.5 * (1 + erf(x / sqrt(2)))


def bs_call(spot, strike, T, sigma):
    if T <= 0 or sigma <= 0:
        return max(spot - strike, 0.0)
    d1 = (log(spot / strike) + 0.5 * sigma * sigma * T) / (sigma * sqrt(T))
    d2 = d1 - sigma * sqrt(T)
    return spot * norm_cdf(d1) - strike * norm_cdf(d2)


def implied_vol(market, spot, strike, T):
    intrinsic = max(spot - strike, 0.0)
    if market <= intrinsic + 0.05:
        return None
    lo, hi = 0.01, 3.0
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if bs_call(spot, strike, T, mid) < market:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def main():
    print(f"{'strike':>10} {'day':>4} {'spot':>8} {'mkt':>9} {'IV':>7}")
    iv_table = {}
    for day in [0, 1, 2]:
        T = TTE_DAYS[day] / 365.0
        df = pd.read_csv(f"data/round3/prices_round_3_day_{day}.csv", sep=";")
        spot = df[df["product"] == "VELVETFRUIT_EXTRACT"]["mid_price"].mean()
        for sym, K in STRIKES.items():
            mkt = df[df["product"] == sym]["mid_price"].mean()
            iv = implied_vol(mkt, spot, K, T)
            iv_str = f"{iv:.3f}" if iv is not None else "  n/a"
            print(f"{sym:>10} {day:>4} {spot:>8.1f} {mkt:>9.2f} {iv_str:>7}")
            iv_table.setdefault(sym, []).append(iv)
        print()
    print("\nMean IV across days (correct TTE):")
    for sym, ivs in iv_table.items():
        valid = [i for i in ivs if i is not None]
        mean_iv = sum(valid) / len(valid) if valid else None
        print(f"  {sym}: {mean_iv:.3f}" if mean_iv else f"  {sym}: n/a")


if __name__ == "__main__":
    main()
