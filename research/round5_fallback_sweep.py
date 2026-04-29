"""Parameter sweep for the fallback MM strategy.

Sweeps OBI_SKEW, INVENTORY_PENALTY, EDGE on R5 days 2/3/4.

Run as: python3 research/round5_fallback_sweep.py
"""
from __future__ import annotations

import re
import subprocess
import tempfile
from itertools import product
from pathlib import Path

REPO = Path(__file__).parent.parent
STRATEGY_TEMPLATE = (REPO / "strategies" / "r5_fallback_mm.py").read_text()

DAYS = [2, 3, 4]
OBI_SKEWS = [0.3, 0.5, 0.8, 1.2]
INVENTORY_PENALTIES = [0.2, 0.5, 0.8]
EDGES = [1, 2, 3]


def write_variant(obi_skew, inv_penalty, edge):
    text = STRATEGY_TEMPLATE
    text = re.sub(r"^OBI_SKEW = .*$", f"OBI_SKEW = {obi_skew}", text, flags=re.M)
    text = re.sub(r"^INVENTORY_PENALTY = .*$",
                  f"INVENTORY_PENALTY = {inv_penalty}", text, flags=re.M)
    text = re.sub(r"^EDGE = .*$", f"EDGE = {edge}", text, flags=re.M)
    tmp = Path(tempfile.NamedTemporaryFile(suffix=".py", delete=False, dir=REPO / "strategies").name)
    tmp.write_text(text)
    return tmp


def run_backtest(strategy_path, day):
    cmd = ["python3", "-m", "backtester",
           str(strategy_path.relative_to(REPO)), f"5-{day}",
           "--data", "data/", "--no-out"]
    out = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, timeout=300)
    match = re.search(r"Total profit:\s*([-\d,]+)", out.stdout)
    if not match:
        return None
    return int(match.group(1).replace(",", ""))


def main():
    combos = list(product(OBI_SKEWS, INVENTORY_PENALTIES, EDGES))
    print(f"Sweeping {len(combos)} combinations × {len(DAYS)} days "
          f"= {len(combos) * len(DAYS)} backtests")
    print()

    results = []
    for i, (obi, inv, edge) in enumerate(combos, 1):
        strategy_path = write_variant(obi, inv, edge)
        try:
            day_pnls = [run_backtest(strategy_path, d) for d in DAYS]
        finally:
            strategy_path.unlink(missing_ok=True)

        if any(p is None for p in day_pnls):
            print(f"  [{i}/{len(combos)}] obi={obi} inv={inv} edge={edge}  FAILED")
            continue
        total = sum(day_pnls)
        results.append((obi, inv, edge, day_pnls, total))
        print(f"  [{i}/{len(combos)}] obi={obi} inv={inv} edge={edge}  "
              f"days={day_pnls}  total={total:+,}")

    print()
    print("=" * 78)
    print("Top 10:")
    print("=" * 78)
    print(f"{'obi':>5} {'inv':>5} {'edge':>5} {'day2':>10} {'day3':>10} {'day4':>10} {'total':>10}")
    for obi, inv, edge, days, total in sorted(results, key=lambda r: -r[4])[:10]:
        d2, d3, d4 = days
        print(f"{obi:>5.1f} {inv:>5.1f} {edge:>5d} {d2:>+10,} {d3:>+10,} {d4:>+10,} {total:>+10,}")


if __name__ == "__main__":
    main()
