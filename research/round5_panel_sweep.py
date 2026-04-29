"""Parameter sweep for the PANEL spread strategy.

Sweeps ENTRY_Z, EXIT_Z, and WINDOW (rolling stats window) on R5 days 2/3/4.
Writes a tweaked strategy to strategies/, runs backtester via subprocess,
parses Total profit, sorts results best-first.

Run as: python3 research/round5_panel_sweep.py
"""
from __future__ import annotations

import re
import subprocess
import tempfile
from itertools import product
from pathlib import Path

REPO = Path(__file__).parent.parent
STRATEGY_TEMPLATE = (REPO / "strategies" / "r5_panel_spread.py").read_text()

DAYS = [2, 3, 4]
ENTRY_ZS = [1.5, 2.0, 2.5, 3.0]
EXIT_ZS = [0.0, 0.3, 0.5]
WINDOWS = [100, 200, 500]


def write_variant(entry_z, exit_z, window):
    text = STRATEGY_TEMPLATE
    text = re.sub(r"^WINDOW = .*$", f"WINDOW = {window}", text, flags=re.M)
    text = re.sub(r"^ENTRY_Z = .*$", f"ENTRY_Z = {entry_z}", text, flags=re.M)
    text = re.sub(r"^EXIT_Z = .*$", f"EXIT_Z = {exit_z}", text, flags=re.M)
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
    combos = list(product(ENTRY_ZS, EXIT_ZS, WINDOWS))
    print(f"Sweeping {len(combos)} combinations × {len(DAYS)} days "
          f"= {len(combos) * len(DAYS)} backtests")
    print()

    results = []
    for i, (entry, exit_, window) in enumerate(combos, 1):
        strategy_path = write_variant(entry, exit_, window)
        try:
            day_pnls = [run_backtest(strategy_path, d) for d in DAYS]
        finally:
            strategy_path.unlink(missing_ok=True)

        if any(p is None for p in day_pnls):
            print(f"  [{i}/{len(combos)}] entry={entry} exit={exit_} window={window}  FAILED")
            continue
        total = sum(day_pnls)
        results.append((entry, exit_, window, day_pnls, total))
        print(f"  [{i}/{len(combos)}] entry={entry} exit={exit_} window={window}  "
              f"days={day_pnls}  total={total:+,}")

    print()
    print("=" * 84)
    print("Top 10 by total PnL across 3 days:")
    print("=" * 84)
    print(f"{'entry':>6} {'exit':>6} {'window':>7} {'day2':>10} {'day3':>10} {'day4':>10} {'total':>10}")
    for entry, exit_, window, days, total in sorted(results, key=lambda r: -r[4])[:10]:
        d2, d3, d4 = days
        print(f"{entry:>6.1f} {exit_:>6.1f} {window:>7d} {d2:>+10,} {d3:>+10,} {d4:>+10,} {total:>+10,}")


if __name__ == "__main__":
    main()
