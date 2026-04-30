import json
from pathlib import Path

VELVETFRUIT_ANCHOR = 5_255.0
VELVETFRUIT_ENTRY_EDGE = 12.0
VELVETFRUIT_LIMIT = 200

def analyze_log(log_path):
    with open(log_path) as f:
        lines = f.readlines()

    results = {
        "long_count": 0,
        "short_count": 0,
        "long_fill_qty": 0,
        "short_fill_qty": 0,
    }

    for line in lines:
        line = line.strip()
        if not line:
            continue

        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue

        if "state" not in data or "order_depths" not in data["state"]:
            continue

        od = data["state"]["order_depths"].get("VELVETFRUIT_EXTRACT")
        if od is None or not od["buy_orders"] or not od["sell_orders"]:
            continue

        bid = max(od["buy_orders"].keys())
        ask = min(od["sell_orders"].keys())
        mid = (bid + ask) / 2.0

        pos = data["state"]["position"].get("VELVETFRUIT_EXTRACT", 0)

        if mid < VELVETFRUIT_ANCHOR - VELVETFRUIT_ENTRY_EDGE and pos < VELVETFRUIT_LIMIT:
            results["long_count"] += 1
            ask_qty = abs(od["sell_orders"][ask])
            qty = min(20, ask_qty, VELVETFRUIT_LIMIT - pos)
            if qty > 0:
                results["long_fill_qty"] += qty

        if mid > VELVETFRUIT_ANCHOR + VELVETFRUIT_ENTRY_EDGE and pos > -VELVETFRUIT_LIMIT:
            results["short_count"] += 1
            bid_qty = od["buy_orders"][bid]
            qty = min(20, bid_qty, VELVETFRUIT_LIMIT + pos)
            if qty > 0:
                results["short_fill_qty"] += qty

    return results

def main():
    backtests_dir = Path("/sessions/amazing-upbeat-volta/mnt/imc-prosperity-4/backtests")
    log_files = sorted(backtests_dir.glob("*.log"), key=lambda p: p.stat().st_mtime, reverse=True)

    if not log_files:
        print("No backtest logs found")
        return

    latest_log = log_files[0]
    print(f"Analyzing: {latest_log.name}")
    print()

    results = analyze_log(latest_log)

    print("VELVETFRUIT Long-Short Balance Analysis")
    print("=" * 60)
    print(f"LONG trigger count:     {results['long_count']}")
    print(f"SHORT trigger count:    {results['short_count']}")
    print(f"LONG filled qty:        {results['long_fill_qty']}")
    print(f"SHORT filled qty:       {results['short_fill_qty']}")
    print()

    if results['long_count'] > 0:
        print(f"Avg fill/long trigger:  {results['long_fill_qty'] / results['long_count']:.2f}")
    if results['short_count'] > 0:
        print(f"Avg fill/short trigger: {results['short_fill_qty'] / results['short_count']:.2f}")

    ratio = results['long_count'] / results['short_count'] if results['short_count'] > 0 else float('inf')
    print(f"\nLONG:SHORT trigger ratio: {ratio:.2f}:1")

if __name__ == "__main__":
    main()
