"""Analyze OOS submission logs.

Single log:  python3 utils/analyze_logs.py path/to/575780.zip
Diff mode:   python3 utils/analyze_logs.py old.zip new.zip
"""
import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# --- Column indices in activitiesLog CSV ---
COL_DAY = 0
COL_TS = 1
COL_PRODUCT = 2
COL_BID1 = 3
COL_BIDVOL1 = 4
COL_BID2 = 5
COL_BIDVOL2 = 6
COL_ASK1 = 9
COL_ASKVOL1 = 10
COL_ASK2 = 11
COL_ASKVOL2 = 12
COL_MID = 15
COL_PNL = 16

# Bleed detection: minimum PnL drop to flag as a drawdown episode
BLEED_MIN_DROP = 200
# How many worst episodes to show per product
BLEED_TOP_N = 3


def load_log(path):
    if path.endswith('.zip'):
        import zipfile
        with zipfile.ZipFile(path) as z:
            # Prefer .json over .log for OOS format
            for suffix in ('.json', '.log'):
                for name in z.namelist():
                    if name.endswith(suffix):
                        return json.loads(z.read(name))
    with open(path) as f:
        return json.load(f)


def parse_activities(data):
    lines = data['activitiesLog'].strip().split('\n')
    rows = [line.split(';') for line in lines[1:]]
    return rows


def safe_float(val):
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def safe_int(val):
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


def build_product_pnl_series(rows):
    """Return {product: [(ts, pnl), ...]} sorted by timestamp."""
    series = {}
    for r in rows:
        product = r[COL_PRODUCT]
        ts = int(r[COL_TS])
        pnl = safe_float(r[COL_PNL])
        if pnl is None:
            continue
        series.setdefault(product, []).append((ts, pnl))
    for product in series:
        series[product].sort()
    return series


def get_final_pnl(pnl_series):
    """Return {product: final_pnl} from series."""
    return {p: vals[-1][1] for p, vals in pnl_series.items()}


def find_drawdown_episodes(pnl_vals):
    """Find drawdown episodes in a PnL series.

    Returns list of (peak_ts, trough_ts, drop_amount, peak_pnl, trough_pnl)
    sorted by drop_amount descending.
    """
    if len(pnl_vals) < 2:
        return []

    episodes = []
    peak_ts, peak_pnl = pnl_vals[0]
    trough_ts, trough_pnl = pnl_vals[0]

    for ts, pnl in pnl_vals[1:]:
        if pnl > peak_pnl:
            # Before moving peak forward, record the completed episode
            drop = peak_pnl - trough_pnl
            if drop >= BLEED_MIN_DROP:
                episodes.append((peak_ts, trough_ts, drop, peak_pnl, trough_pnl))
            peak_ts, peak_pnl = ts, pnl
            trough_ts, trough_pnl = ts, pnl
        elif pnl < trough_pnl:
            trough_ts, trough_pnl = ts, pnl

    # Final episode
    drop = peak_pnl - trough_pnl
    if drop >= BLEED_MIN_DROP:
        episodes.append((peak_ts, trough_ts, drop, peak_pnl, trough_pnl))

    episodes.sort(key=lambda e: e[2], reverse=True)
    return episodes


def get_book_snapshot(rows, product, ts):
    """Get order book state at a specific (product, ts)."""
    for r in rows:
        if r[COL_PRODUCT] == product and int(r[COL_TS]) == ts:
            bid1 = safe_int(r[COL_BID1])
            ask1 = safe_int(r[COL_ASK1])
            bid_vol1 = safe_int(r[COL_BIDVOL1])
            ask_vol1 = safe_int(r[COL_ASKVOL1])
            mid = safe_float(r[COL_MID])
            spread = (ask1 - bid1) if bid1 and ask1 else None
            obi = None
            if bid_vol1 and ask_vol1:
                total = bid_vol1 + abs(ask_vol1)
                if total > 0:
                    obi = (bid_vol1 - abs(ask_vol1)) / total
            return {
                'bid': bid1, 'ask': ask1, 'mid': mid, 'spread': spread,
                'bid_vol': bid_vol1, 'ask_vol': ask_vol1, 'obi': obi,
            }
    return None


# ─── Output sections ───────────────────────────────────────────────

def print_header(title):
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print(f"{'─' * 60}")


def print_pnl_table(pnl_series):
    final = get_final_pnl(pnl_series)
    total = sum(final.values())

    print_header(f"PNL BY PRODUCT  (total: {total:>+,.0f})")

    sorted_products = sorted(final.items(), key=lambda x: x[1])

    bleeders = [(p, v) for p, v in sorted_products if v < -50]
    flat = [(p, v) for p, v in sorted_products if -50 <= v <= 50]
    winners = [(p, v) for p, v in sorted_products if v > 50]

    if bleeders:
        print("  BLEEDERS:")
        for p, v in bleeders:
            print(f"    {p:45s} {v:>+9,.0f}")

    if flat:
        print(f"  FLAT ({len(flat)} products):")
        names = [p for p, _ in flat]
        for i in range(0, len(names), 3):
            chunk = names[i:i+3]
            print(f"    {', '.join(chunk)}")

    if winners:
        print("  WINNERS:")
        for p, v in winners:
            print(f"    {p:45s} {v:>+9,.0f}")


def print_trajectory(pnl_series):
    ts_total = {}
    for product, vals in pnl_series.items():
        for ts, pnl in vals:
            ts_total[ts] = ts_total.get(ts, 0) + pnl

    timestamps = sorted(ts_total.keys())
    n = len(timestamps)
    if n == 0:
        return

    print_header("PNL TRAJECTORY")
    checkpoints = [0, n // 4, n // 2, 3 * n // 4, n - 1]
    labels = ["start", "25%", "50%", "75%", "end"]
    for label, idx in zip(labels, checkpoints):
        ts = timestamps[idx]
        print(f"  {label:>5s}  ts={ts:>6d}  pnl={ts_total[ts]:>+10,.0f}")


def print_bleeds(pnl_series, rows):
    print_header("DRAWDOWN EPISODES  (worst per product)")

    any_bleeds = False
    final = get_final_pnl(pnl_series)
    active = [p for p in sorted(final, key=lambda x: final[x]) if abs(final[p]) > 10]

    for product in active:
        episodes = find_drawdown_episodes(pnl_series[product])
        if not episodes:
            continue

        any_bleeds = True
        top = episodes[:BLEED_TOP_N]
        print(f"\n  {product}  (final: {final[product]:>+,.0f})")

        for peak_ts, trough_ts, drop, peak_pnl, trough_pnl in top:
            duration = trough_ts - peak_ts
            book_at_peak = get_book_snapshot(rows, product, peak_ts)
            book_at_trough = get_book_snapshot(rows, product, trough_ts)

            print(f"    drop={drop:>+6,.0f}  ts={peak_ts:>6d}→{trough_ts:>6d}  ({duration:,d} ticks)")

            if book_at_peak:
                bp = book_at_peak
                spread_str = f"spread={bp['spread']}" if bp['spread'] else "spread=?"
                obi_str = f"obi={bp['obi']:+.2f}" if bp['obi'] is not None else "obi=?"
                mid_str = f"mid={bp['mid']:.0f}" if bp['mid'] else "mid=?"
                print(f"      at peak:   {mid_str}  {spread_str}  {obi_str}")

            if book_at_trough:
                bt = book_at_trough
                spread_str = f"spread={bt['spread']}" if bt['spread'] else "spread=?"
                obi_str = f"obi={bt['obi']:+.2f}" if bt['obi'] is not None else "obi=?"
                mid_str = f"mid={bt['mid']:.0f}" if bt['mid'] else "mid=?"
                print(f"      at trough: {mid_str}  {spread_str}  {obi_str}")

    if not any_bleeds:
        print("  No drawdown episodes above threshold.")


def print_spreads(rows):
    print_header("EXCHANGE SPREADS  (traded products only)")

    pnl_by_product = {}
    spread_data = {}

    for r in rows:
        product = r[COL_PRODUCT]
        pnl = safe_float(r[COL_PNL])
        if pnl is not None:
            pnl_by_product[product] = pnl

        bid1 = safe_int(r[COL_BID1])
        ask1 = safe_int(r[COL_ASK1])
        if bid1 and ask1:
            spread_data.setdefault(product, []).append(ask1 - bid1)

    active = {p for p, v in pnl_by_product.items() if abs(v) > 10}

    for prod in sorted(active):
        if prod in spread_data:
            s = spread_data[prod]
            print(f"  {prod:45s} mean={sum(s)/len(s):>5.1f}  min={min(s)}  max={max(s)}")


# ─── Diff mode ─────────────────────────────────────────────────────

def print_diff(old_data, new_data):
    old_rows = parse_activities(old_data)
    new_rows = parse_activities(new_data)

    old_series = build_product_pnl_series(old_rows)
    new_series = build_product_pnl_series(new_rows)

    old_final = get_final_pnl(old_series)
    new_final = get_final_pnl(new_series)

    all_products = sorted(set(old_final) | set(new_final))

    old_total = sum(old_final.values())
    new_total = sum(new_final.values())
    delta_total = new_total - old_total

    print_header(f"DIFF  old={old_total:>+,.0f}  new={new_total:>+,.0f}  delta={delta_total:>+,.0f}")

    diffs = []
    for p in all_products:
        old_v = old_final.get(p, 0)
        new_v = new_final.get(p, 0)
        delta = new_v - old_v
        diffs.append((p, old_v, new_v, delta))

    diffs.sort(key=lambda x: x[3])

    regressed = [(p, o, n, d) for p, o, n, d in diffs if d < -50]
    improved = [(p, o, n, d) for p, o, n, d in diffs if d > 50]
    unchanged = [(p, o, n, d) for p, o, n, d in diffs if -50 <= d <= 50]

    if regressed:
        print("  REGRESSED:")
        for p, o, n, d in regressed:
            sign_flip = " !!FLIP" if (o > 0 and n < 0) or (o < 0 and n > 0) else ""
            print(f"    {p:40s} {o:>+8,.0f} → {n:>+8,.0f}  ({d:>+7,.0f}){sign_flip}")

    if unchanged:
        print(f"  UNCHANGED ({len(unchanged)} products)")

    if improved:
        print("  IMPROVED:")
        for p, o, n, d in improved:
            sign_flip = " !!FLIP" if (o > 0 and n < 0) or (o < 0 and n > 0) else ""
            print(f"    {p:40s} {o:>+8,.0f} → {n:>+8,.0f}  ({d:>+7,.0f}){sign_flip}")


# ─── Backtester-format sections (guarded) ──────────────────────────

def analyze_trades(data):
    if 'tradeHistory' not in data:
        return
    trades = data['tradeHistory']
    print_header(f"TRADE ANALYSIS  ({len(trades)} fills)")

    by_sym = {}
    for t in trades:
        by_sym.setdefault(t['symbol'], []).append(t)

    for sym, ts in sorted(by_sym.items()):
        buys = [t for t in ts if t['buyer'] == 'SUBMISSION']
        sells = [t for t in ts if t['seller'] == 'SUBMISSION']
        buy_vol = sum(t['quantity'] for t in buys)
        sell_vol = sum(t['quantity'] for t in sells)
        buy_cost = sum(t['price'] * t['quantity'] for t in buys)
        sell_rev = sum(t['price'] * t['quantity'] for t in sells)

        avg_buy = buy_cost / buy_vol if buy_vol else 0
        avg_sell = sell_rev / sell_vol if sell_vol else 0

        edge = f"edge/unit={avg_sell - avg_buy:,.1f}" if avg_buy and avg_sell else ""
        print(f"  {sym}: B {buy_vol} @ {avg_buy:,.0f}  S {sell_vol} @ {avg_sell:,.0f}  {edge}  net={buy_vol - sell_vol:+d}")


def analyze_errors(data):
    if 'logs' not in data:
        return
    logs = data['logs']
    errors = [l for l in logs if l.get('sandboxLog')]
    if not errors:
        return

    print_header(f"LIMIT VIOLATIONS  ({len(errors)} ticks)")
    by_product = {}
    for e in errors:
        for line in e['sandboxLog'].strip().split('\n'):
            if 'exceeded limit' in line.lower():
                parts = line.split('product ')
                if len(parts) > 1:
                    prod = parts[1].split(' exceeded')[0]
                    by_product[prod] = by_product.get(prod, 0) + 1
    for prod, count in sorted(by_product.items(), key=lambda x: -x[1]):
        print(f"  {prod}: {count}")


# ─── Main ──────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python3 utils/analyze_logs.py <log.zip>          # single log analysis")
        print("  python3 utils/analyze_logs.py <old.zip> <new.zip> # diff two runs")
        sys.exit(1)

    if len(sys.argv) >= 3:
        old_data = load_log(sys.argv[1])
        new_data = load_log(sys.argv[2])
        print_diff(old_data, new_data)
        print(f"\n{'═' * 60}")
        print(f"  FULL ANALYSIS OF NEW LOG")
        print(f"{'═' * 60}")
        data = new_data
    else:
        data = load_log(sys.argv[1])

    rows = parse_activities(data)
    pnl_series = build_product_pnl_series(rows)

    print_pnl_table(pnl_series)
    print_trajectory(pnl_series)
    print_bleeds(pnl_series, rows)
    print_spreads(rows)
    analyze_trades(data)
    analyze_errors(data)


if __name__ == "__main__":
    main()
