"""Parameter sweep for the ROBOT_DISHES v2 regime-switch strategy.

Sweeps EDGE, MR_REGIME_MAX_ABS_RETURN, REGIME_WINDOW, MA_WINDOW.

Run as: python3 research/round5_robot_sweep.py
"""
from __future__ import annotations

import re
import subprocess
import tempfile
from itertools import product
from pathlib import Path

REPO = Path(__file__).parent.parent
STRATEGY_TEMPLATE = (REPO / "strategies" / "r5_robot_dishes_mr.py").read_text()

DAYS = [2, 3, 4]
EDGES = [2, 3, 4]
REGIME_THRESHOLDS = [3, 4, 6, 8]
MA_WINDOWS = [10, 15, 25]


def write_variant(edge, regime_threshold, ma_window):
    text = STRATEGY_TEMPLATE
    text = re.sub(r"^EDGE = .*$", f"EDGE = {edge}", text, flags=re.M)
    text = re.sub(r"^MR_REGIME_MAX_ABS_RETURN = .*$",
                  f"MR_REGIME_MAX_ABS_RETURN = {regime_threshold}", text, flags=re.M)
    text = re.sub(r"^MA_WINDOW = .*$", f"MA_WINDOW = {ma_window}", text, flags=re.M)
    tmp = Path(tempfile.NamedTemporaryFile(suffix=".py", delete=False, dir=REPO / "strategies").name)
    tmp.write_text(text)
    return tmp


def run_backtest(strategy_path, day):
    cmd = ["python3", "-m", "backtester",
           str(strategy_path.relative_to(REPO)), f"5-{day}",
           "--data", "data/", "--no-out"]
    out = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, timeout=120)
    match = re.search(r"Total profit:\s*([-\d,]+)", out.stdout)
    if not match:
        return None
    return int(match.group(1).replace(",", ""))


def main():
    combos = list(product(EDGES, REGIME_THRESHOLDS, MA_WINDOWS))
    print(f"Sweeping {len(combos)} combinations × {len(DAYS)} days")
    print()

    results = []
    for i, (edge, thr, win) in enumerate(combos, 1):
        strategy_path = write_variant(edge, thr, win)
        try:
            day_pnls = [run_backtest(strategy_path, d) for d in DAYS]
        finally:
            strategy_path.unlink(missing_ok=True)

        if any(p is None for p in day_pnls):
            print(f"  [{i}/{len(combos)}] edge={edge} thr={thr} win={win}  FAILED")
            continue
        total = sum(day_pnls)
        results.append((edge, thr, win, day_pnls, total))
        print(f"  [{i}/{len(combos)}] edge={edge} thr={thr} win={win}  "
              f"days={day_pnls}  total={total:+,}")

    print()
    print("=" * 78)
    print("Top 10:")
    print("=" * 78)
    print(f"{'edge':>5} {'thr':>5} {'win':>5} {'day2':>10} {'day3':>10} {'day4':>10} {'total':>10}")
    for edge, thr, win, days, total in sorted(results, key=lambda r: -r[4])[:10]:
        d2, d3, d4 = days
        print(f"{edge:>5d} {thr:>5d} {win:>5d} {d2:>+10,} {d3:>+10,} {d4:>+10,} {total:>+10,}")


if __name__ == "__main__":
    main()
