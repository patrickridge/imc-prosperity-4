"""Parameter sweep for the SNACKPACK MM strategy.

Tries combinations of INVENTORY_PENALTY, OBI_SKEW, and EDGE (quote offset).
Writes a tweaked strategy to /tmp, runs backtester via subprocess, parses
'Total profit' from stdout. Sorts results best-first.

Run as: python3 research/round5_snackpack_sweep.py
"""
from __future__ import annotations

import re
import subprocess
import tempfile
from itertools import product
from pathlib import Path

REPO = Path(__file__).parent.parent
STRATEGY_TEMPLATE = (REPO / "strategies" / "r5_snackpack_mm.py").read_text()

DAYS = [2, 3, 4]
INVENTORY_PENALTIES = [0.1, 0.3, 0.5, 0.8]
OBI_SKEWS           = [0.2, 0.5, 0.8, 1.2]
EDGES               = [1, 2]
MATCH_TRADERS_FLAG = ""


def write_variant(inv_penalty, obi_skew, edge):
    text = STRATEGY_TEMPLATE
    text = re.sub(r"^INVENTORY_PENALTY = .*$",
                  f"INVENTORY_PENALTY = {inv_penalty}", text, flags=re.M)
    text = re.sub(r"^OBI_SKEW = .*$", f"OBI_SKEW = {obi_skew}", text, flags=re.M)
    text = re.sub(r"int\(fair - 1\)", f"int(fair - {edge})", text)
    text = re.sub(r"int\(fair \+ 1\)", f"int(fair + {edge})", text)
    tmp = Path(tempfile.NamedTemporaryFile(suffix=".py", delete=False, dir=REPO / "strategies").name)
    tmp.write_text(text)
    return tmp


def run_backtest(strategy_path, day):
    cmd = ["python3", "-m", "backtester",
           str(strategy_path.relative_to(REPO)), f"5-{day}",
           "--data", "data/", "--no-out"]
    out = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, timeout=180)
    match = re.search(r"Total profit:\s*([-\d,]+)", out.stdout)
    if not match:
        return None
    return int(match.group(1).replace(",", ""))


def main():
    combos = list(product(INVENTORY_PENALTIES, OBI_SKEWS, EDGES))
    print(f"Sweeping {len(combos)} combinations × {len(DAYS)} days "
          f"= {len(combos) * len(DAYS)} backtests")
    print()

    results = []
    for i, (inv, obi, edge) in enumerate(combos, 1):
        strategy_path = write_variant(inv, obi, edge)
        try:
            day_pnls = [run_backtest(strategy_path, d) for d in DAYS]
        finally:
            strategy_path.unlink(missing_ok=True)

        if any(p is None for p in day_pnls):
            print(f"  [{i}/{len(combos)}] inv={inv} obi={obi} edge={edge}  FAILED")
            continue
        total = sum(day_pnls)
        results.append((inv, obi, edge, day_pnls, total))
        print(f"  [{i}/{len(combos)}] inv={inv} obi={obi} edge={edge}  "
              f"days={day_pnls}  total={total:+,}")

    print()
    print("=" * 78)
    print("Top 10 by total PnL across 3 days:")
    print("=" * 78)
    print(f"{'inv':>6} {'obi':>6} {'edge':>5} {'day2':>10} {'day3':>10} {'day4':>10} {'total':>10}")
    for inv, obi, edge, days, total in sorted(results, key=lambda r: -r[4])[:10]:
        d2, d3, d4 = days
        print(f"{inv:>6.1f} {obi:>6.1f} {edge:>5d} {d2:>+10,} {d3:>+10,} {d4:>+10,} {total:>+10,}")


if __name__ == "__main__":
    main()
