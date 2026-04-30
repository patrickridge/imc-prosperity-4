"""
Simulate UV_VISOR pair trading signals on OOS data.

Tests:
- RA (RED-AMBER) and MO (MAGENTA-ORANGE) spreads
- Multiple EMA window scales: 10/80, 20/160, 50/400, 100/800
- MO in both directions: current (LONG_MAG/SHORT_ORG when spread UP)
  and reversed (SHORT_MAG/LONG_ORG when spread DOWN)
- Multiple position sizes for MO: 3 and 10
"""

import csv
from collections import defaultdict


CSV_PATH = "/home/vscode/repos/imc-prosperity-4/research/oos_v10.csv"

PRODUCTS = [
    "UV_VISOR_RED",
    "UV_VISOR_AMBER",
    "UV_VISOR_MAGENTA",
    "UV_VISOR_ORANGE",
    "UV_VISOR_YELLOW",
]


# ── Load data ──

def load_data():
    """Returns {product: [(ts, bid1, ask1, mid), ...]} sorted by ts."""
    rows = defaultdict(list)
    with open(CSV_PATH) as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["product"] not in PRODUCTS:
                continue
            ts = int(row["ts"])
            bid1 = int(row["bid1"]) if row["bid1"] else None
            ask1 = int(row["ask1"]) if row["ask1"] else None
            # mid is in "pnl" column (CSV has empty "mid" col, actual mid is last)
            mid_str = row["pnl"] if row["pnl"] else row["mid"]
            if not mid_str:
                continue
            mid = float(mid_str)
            if bid1 is None or ask1 is None:
                continue
            rows[row["product"]].append((ts, bid1, ask1, mid))

    for p in rows:
        rows[p].sort(key=lambda x: x[0])
    return dict(rows)


# ── EMA helpers ──

def ema_update(prev, x, window):
    alpha = 2.0 / (window + 1.0)
    if prev is None:
        return x
    return alpha * x + (1.0 - alpha) * prev


def compute_trend(spreads, fast_w, slow_w, vol_w=500, vol_mult=8.0, min_denom=50.0):
    """
    Returns list of (trend_raw, trend_score) for each tick.
    """
    fast_ema = None
    slow_ema = None
    vol_ema = None
    prev_spread = None
    results = []

    for s in spreads:
        dspread = 0.0 if prev_spread is None else s - prev_spread
        fast_ema = ema_update(fast_ema, s, fast_w)
        slow_ema = ema_update(slow_ema, s, slow_w)
        vol_ema = ema_update(vol_ema, abs(dspread), vol_w)
        prev_spread = s

        trend_raw = fast_ema - slow_ema
        trend_score = trend_raw / max(vol_ema * vol_mult, min_denom)
        results.append((trend_raw, trend_score))

    return results


# ── Signal state machine ──

def simulate_signal(
    trends,
    spreads,
    entry_raw,
    entry_score,
    trailing_stop,
    check_positive=True,
):
    """
    Returns list of bools: True when signal is ACTIVE.
    check_positive=True: enter when trend_raw > entry_raw (current logic)
    check_positive=False: enter when trend_raw < -entry_raw (reversed)
    """
    active = False
    peak_spread = None
    signals = []

    for i, (trend_raw, trend_score) in enumerate(trends):
        spread = spreads[i]

        if not active:
            if check_positive:
                should_enter = trend_raw > entry_raw and trend_score > entry_score
            else:
                should_enter = trend_raw < -entry_raw and trend_score < -entry_score

            if should_enter:
                active = True
                peak_spread = spread
        else:
            if check_positive:
                peak_spread = max(peak_spread, spread)
                trailing_hit = peak_spread - spread > trailing_stop
            else:
                peak_spread = min(peak_spread, spread)
                trailing_hit = spread - peak_spread > trailing_stop

            if trailing_hit:
                active = False
                peak_spread = None

        signals.append(active)

    return signals


# ── PnL simulation ──

def simulate_pnl(
    signals,
    long_product_data,
    short_product_data,
    long_target,
    short_target,
):
    """
    When signal is active, hold target positions.
    When inactive, target = 0.
    Cross the spread to get into / out of positions.
    Returns (long_pnl, short_pnl, total_pnl, num_active_ticks, entry_tick).
    """
    long_pos = 0
    short_pos = 0
    long_pnl = 0.0
    short_pnl = 0.0
    entry_tick = None

    for i, sig in enumerate(signals):
        _, l_bid, l_ask, l_mid = long_product_data[i]
        _, s_bid, s_ask, s_mid = short_product_data[i]

        if sig:
            l_target = long_target
            s_target = short_target
        else:
            l_target = 0
            s_target = 0

        # Execute long leg
        l_delta = l_target - long_pos
        if l_delta > 0:
            long_pnl -= l_delta * l_ask  # buying at ask
        elif l_delta < 0:
            long_pnl -= l_delta * l_bid  # selling at bid (delta is negative)
        long_pos = l_target

        # Execute short leg
        s_delta = s_target - short_pos
        if s_delta > 0:
            short_pnl -= s_delta * s_ask
        elif s_delta < 0:
            short_pnl -= s_delta * s_bid
        short_pos = s_target

        if sig and entry_tick is None:
            entry_tick = i

    # Mark-to-market remaining positions at final mid
    _, l_bid, l_ask, l_mid = long_product_data[-1]
    _, s_bid, s_ask, s_mid = short_product_data[-1]

    if long_pos > 0:
        long_pnl += long_pos * l_bid
    elif long_pos < 0:
        long_pnl += long_pos * l_ask

    if short_pos > 0:
        short_pnl += short_pos * s_bid
    elif short_pos < 0:
        short_pnl += short_pos * s_ask

    num_active = sum(signals)
    return long_pnl, short_pnl, long_pnl + short_pnl, num_active, entry_tick


# ── Main ──

def main():
    data = load_data()

    red_data = data["UV_VISOR_RED"]
    amber_data = data["UV_VISOR_AMBER"]
    mag_data = data["UV_VISOR_MAGENTA"]
    org_data = data["UV_VISOR_ORANGE"]

    n = len(red_data)
    print(f"Ticks: {n}")
    print(f"RED  first/last mid: {red_data[0][3]:.1f} -> {red_data[-1][3]:.1f}  drift={red_data[-1][3]-red_data[0][3]:+.1f}")
    print(f"AMBER first/last mid: {amber_data[0][3]:.1f} -> {amber_data[-1][3]:.1f}  drift={amber_data[-1][3]-amber_data[0][3]:+.1f}")
    print(f"MAG  first/last mid: {mag_data[0][3]:.1f} -> {mag_data[-1][3]:.1f}  drift={mag_data[-1][3]-mag_data[0][3]:+.1f}")
    print(f"ORG  first/last mid: {org_data[0][3]:.1f} -> {org_data[-1][3]:.1f}  drift={org_data[-1][3]-org_data[0][3]:+.1f}")

    ra_spreads = [red_data[i][3] - amber_data[i][3] for i in range(n)]
    mo_spreads = [mag_data[i][3] - org_data[i][3] for i in range(n)]

    print(f"\nRA spread first/last: {ra_spreads[0]:.1f} -> {ra_spreads[-1]:.1f}  drift={ra_spreads[-1]-ra_spreads[0]:+.1f}")
    print(f"MO spread first/last: {mo_spreads[0]:.1f} -> {mo_spreads[-1]:.1f}  drift={mo_spreads[-1]-mo_spreads[0]:+.1f}")

    # ── Window scales to test ──
    window_configs = [
        (10, 80),
        (20, 160),
        (50, 400),
        (100, 800),
    ]

    # RA entry params
    ra_entry_raw = 80.0
    ra_entry_score = 1.0
    ra_trailing = 1500.0

    # MO entry params
    mo_entry_raw = 45.0
    mo_entry_score = 0.8
    mo_trailing = 1000.0

    # ── RA tests ──
    print("\n" + "=" * 80)
    print("RA CORE (LONG RED / SHORT AMBER, target +10 / -10)")
    print("=" * 80)
    for fast_w, slow_w in window_configs:
        trends = compute_trend(ra_spreads, fast_w, slow_w)
        signals = simulate_signal(trends, ra_spreads, ra_entry_raw, ra_entry_score, ra_trailing, check_positive=True)
        l_pnl, s_pnl, total, n_active, entry_t = simulate_pnl(signals, red_data, amber_data, 10, -10)
        print(f"  FAST={fast_w:3d} SLOW={slow_w:3d} | RED={l_pnl:+8.0f} AMBER={s_pnl:+8.0f} | total={total:+8.0f} | active={n_active:4d}/{n} ticks | entry_tick={entry_t}")

    # ── MO tests: current direction (spread UP = LONG MAG / SHORT ORG) ──
    print("\n" + "=" * 80)
    print("MO CURRENT DIRECTION (LONG MAGENTA / SHORT ORANGE when spread UP)")
    print("=" * 80)
    for fast_w, slow_w in window_configs:
        trends = compute_trend(mo_spreads, fast_w, slow_w)
        signals = simulate_signal(trends, mo_spreads, mo_entry_raw, mo_entry_score, mo_trailing, check_positive=True)

        # Size = 3
        l_pnl3, s_pnl3, total3, n_active3, entry_t3 = simulate_pnl(signals, mag_data, org_data, 3, -3)
        # Size = 10
        l_pnl10, s_pnl10, total10, n_active10, entry_t10 = simulate_pnl(signals, mag_data, org_data, 10, -10)

        print(f"  FAST={fast_w:3d} SLOW={slow_w:3d} | sz=3: MAG={l_pnl3:+8.0f} ORG={s_pnl3:+8.0f} total={total3:+8.0f} | sz=10: total={total10:+8.0f} | active={n_active3:4d}/{n} entry={entry_t3}")

    # ── MO tests: REVERSED direction (SHORT MAGENTA / LONG ORANGE when spread DOWN) ──
    print("\n" + "=" * 80)
    print("MO REVERSED DIRECTION (SHORT MAGENTA / LONG ORANGE when spread DOWN)")
    print("=" * 80)
    for fast_w, slow_w in window_configs:
        trends = compute_trend(mo_spreads, fast_w, slow_w)
        signals = simulate_signal(trends, mo_spreads, mo_entry_raw, mo_entry_score, mo_trailing, check_positive=False)

        # Size = 3  (reversed: short MAG, long ORG)
        l_pnl3, s_pnl3, total3, n_active3, entry_t3 = simulate_pnl(signals, org_data, mag_data, 3, -3)
        # Size = 10
        l_pnl10, s_pnl10, total10, n_active10, entry_t10 = simulate_pnl(signals, org_data, mag_data, 10, -10)

        print(f"  FAST={fast_w:3d} SLOW={slow_w:3d} | sz=3: ORG={l_pnl3:+8.0f} MAG={s_pnl3:+8.0f} total={total3:+8.0f} | sz=10: total={total10:+8.0f} | active={n_active3:4d}/{n} entry={entry_t3}")

    # ── Also test with lower entry thresholds for MO ──
    print("\n" + "=" * 80)
    print("MO REVERSED with LOWER thresholds (entry_raw=20, entry_score=0.4)")
    print("=" * 80)
    low_entry_raw = 20.0
    low_entry_score = 0.4
    for fast_w, slow_w in window_configs:
        trends = compute_trend(mo_spreads, fast_w, slow_w)
        signals = simulate_signal(trends, mo_spreads, low_entry_raw, low_entry_score, mo_trailing, check_positive=False)

        l_pnl3, s_pnl3, total3, n_active3, entry_t3 = simulate_pnl(signals, org_data, mag_data, 3, -3)
        l_pnl10, s_pnl10, total10, n_active10, entry_t10 = simulate_pnl(signals, org_data, mag_data, 10, -10)

        print(f"  FAST={fast_w:3d} SLOW={slow_w:3d} | sz=3: ORG={l_pnl3:+8.0f} MAG={s_pnl3:+8.0f} total={total3:+8.0f} | sz=10: total={total10:+8.0f} | active={n_active3:4d}/{n} entry={entry_t3}")

    # ── Also test MO REVERSED with even lower thresholds ──
    print("\n" + "=" * 80)
    print("MO REVERSED with MINIMAL thresholds (entry_raw=10, entry_score=0.2)")
    print("=" * 80)
    min_entry_raw = 10.0
    min_entry_score = 0.2
    for fast_w, slow_w in window_configs:
        trends = compute_trend(mo_spreads, fast_w, slow_w)
        signals = simulate_signal(trends, mo_spreads, min_entry_raw, min_entry_score, mo_trailing, check_positive=False)

        l_pnl3, s_pnl3, total3, n_active3, entry_t3 = simulate_pnl(signals, org_data, mag_data, 3, -3)
        l_pnl10, s_pnl10, total10, n_active10, entry_t10 = simulate_pnl(signals, org_data, mag_data, 10, -10)

        print(f"  FAST={fast_w:3d} SLOW={slow_w:3d} | sz=3: ORG={l_pnl3:+8.0f} MAG={s_pnl3:+8.0f} total={total3:+8.0f} | sz=10: total={total10:+8.0f} | active={n_active3:4d}/{n} entry={entry_t3}")

    # ── Detailed trend analysis for MO to understand why it doesn't trigger ──
    print("\n" + "=" * 80)
    print("MO TREND DIAGNOSTICS (current 100/800 windows)")
    print("=" * 80)
    trends_100_800 = compute_trend(mo_spreads, 100, 800)
    raw_values = [t[0] for t in trends_100_800]
    score_values = [t[1] for t in trends_100_800]
    print(f"  trend_raw  min={min(raw_values):+.2f}  max={max(raw_values):+.2f}")
    print(f"  trend_score min={min(score_values):+.4f}  max={max(score_values):+.4f}")
    print(f"  Current entry requires: trend_raw > +45 AND trend_score > +0.8")
    print(f"  Reversed entry requires: trend_raw < -45 AND trend_score < -0.8")

    for fast_w, slow_w in window_configs:
        trends = compute_trend(mo_spreads, fast_w, slow_w)
        raw_vals = [t[0] for t in trends]
        score_vals = [t[1] for t in trends]
        print(f"\n  FAST={fast_w:3d} SLOW={slow_w:3d}:")
        print(f"    trend_raw  min={min(raw_vals):+.2f}  max={max(raw_vals):+.2f}")
        print(f"    trend_score min={min(score_vals):+.4f}  max={max(score_vals):+.4f}")

        # Find first tick where thresholds are crossed in each direction
        for th_raw, th_score in [(45, 0.8), (20, 0.4), (10, 0.2)]:
            first_pos = None
            first_neg = None
            for i, (r, s) in enumerate(trends):
                if first_pos is None and r > th_raw and s > th_score:
                    first_pos = i
                if first_neg is None and r < -th_raw and s < -th_score:
                    first_neg = i
            print(f"    threshold raw={th_raw} score={th_score}: first_pos_cross={first_pos} first_neg_cross={first_neg}")

    # ── RA with smaller windows too ──
    print("\n" + "=" * 80)
    print("RA DIAGNOSTICS")
    print("=" * 80)
    for fast_w, slow_w in window_configs:
        trends = compute_trend(ra_spreads, fast_w, slow_w)
        raw_vals = [t[0] for t in trends]
        score_vals = [t[1] for t in trends]
        print(f"  FAST={fast_w:3d} SLOW={slow_w:3d}: raw min/max={min(raw_vals):+.1f}/{max(raw_vals):+.1f}  score min/max={min(score_vals):+.3f}/{max(score_vals):+.3f}")

    # ── Best combo: RA + MO reversed ──
    print("\n" + "=" * 80)
    print("COMBINED RA + MO REVERSED (best configs)")
    print("=" * 80)

    # RA with 100/800 (confirmed)
    ra_trends = compute_trend(ra_spreads, 100, 800)
    ra_signals = simulate_signal(ra_trends, ra_spreads, 80.0, 1.0, 1500.0, check_positive=True)
    ra_l, ra_s, ra_tot, ra_act, _ = simulate_pnl(ra_signals, red_data, amber_data, 10, -10)

    # Try all MO reversed configs
    print(f"  RA alone (100/800): RED={ra_l:+.0f} AMBER={ra_s:+.0f} total={ra_tot:+.0f} active={ra_act}")
    for fast_w, slow_w in window_configs:
        for th_raw, th_score in [(45, 0.8), (20, 0.4), (10, 0.2)]:
            for trail in [500, 1000, 1500]:
                mo_trends = compute_trend(mo_spreads, fast_w, slow_w)
                mo_sigs = simulate_signal(mo_trends, mo_spreads, th_raw, th_score, trail, check_positive=False)
                mo_l, mo_s, mo_tot, mo_act, mo_entry = simulate_pnl(mo_sigs, org_data, mag_data, 10, -10)
                if mo_act > 0:
                    combined = ra_tot + mo_tot
                    print(f"  MO_REV f={fast_w:3d} s={slow_w:3d} raw={th_raw:2.0f} sc={th_score:.1f} trail={trail:4d} | ORG={mo_l:+8.0f} MAG={mo_s:+8.0f} total={mo_tot:+8.0f} active={mo_act:4d} entry={mo_entry} | COMBINED={combined:+.0f}")


if __name__ == "__main__":
    main()
