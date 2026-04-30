#!/usr/bin/env python3
"""
Infer VEV voucher payoff structure from end-of-day data.
Key question: at expiry, what is the settlement rule?
"""

import csv
from typing import Dict, List

def read_day(day: int) -> List[Dict]:
    path = f"data/round3/prices_round_3_day_{day}.csv"
    rows = []
    with open(path) as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            rows.append(row)
    return rows

def main():
    for day in range(3):
        data = read_day(day)

        last_timestamp = max(int(r["timestamp"]) for r in data)
        end_data = [r for r in data if int(r["timestamp"]) == last_timestamp]

        spot = None
        for r in end_data:
            if r["product"] == "VELVETFRUIT_EXTRACT":
                spot = float(r["mid_price"])
                break

        if spot is None:
            continue

        print(f"\n=== Day {day}, Final Spot: {spot:.1f} ===")

        vev_prices = {}
        for r in end_data:
            if r["product"].startswith("VEV_"):
                mid = float(r["mid_price"])
                vev_prices[r["product"]] = mid

        for symbol in sorted(vev_prices.keys()):
            strike = int(symbol.split("_")[1])
            market_mid = vev_prices[symbol]
            intrinsic = max(spot - strike, 0.0)
            extrinsic = market_mid - intrinsic

            print(f"{symbol:12} K={strike:5.0f}  Market={market_mid:7.1f}  "
                  f"Intrinsic={intrinsic:7.1f}  Extrinsic={extrinsic:7.1f}  "
                  f"Ratio={market_mid/max(intrinsic, 0.01):5.2f}")

        print("\nHypothesis: check if extrinsic is capped per strike")
        for symbol in sorted(vev_prices.keys()):
            strike = int(symbol.split("_")[1])
            market_mid = vev_prices[symbol]
            intrinsic = max(spot - strike, 0.0)
            extrinsic = market_mid - intrinsic
            distance_to_strike = strike - spot
            print(f"{symbol:12} extrinsic={extrinsic:6.2f}  "
                  f"(strike-spot)={distance_to_strike:6.1f}")

if __name__ == "__main__":
    main()
