"""Score each Mark by future price change after their trades. Highest |score| = informed."""
import pandas as pd
from pathlib import Path

DATA = Path("/sessions/amazing-upbeat-volta/mnt/imc-prosperity-4/data/round4")
LOOKAHEAD = 5_000  # 5 ticks forward

def load_day(day):
    px = pd.read_csv(DATA / f"prices_round_4_day_{day}.csv", sep=";")
    tr = pd.read_csv(DATA / f"trades_round_4_day_{day}.csv", sep=";")
    return px, tr

def mid(px):
    px = px.copy()
    px["mid"] = (px["bid_price_1"] + px["ask_price_1"]) / 2
    return px[["timestamp", "product", "mid"]]

def score_traders(px, tr, product):
    p = mid(px[px["product"] == product]).sort_values("timestamp")
    p = p.drop_duplicates("timestamp")
    p = p.set_index("timestamp")["mid"]
    rows = []
    t = tr[tr["symbol"] == product]
    for trader in sorted(set(t["buyer"]) | set(t["seller"])):
        if not isinstance(trader, str): continue
        buys = t[t["buyer"] == trader]
        sells = t[t["seller"] == trader]
        b_sig, s_sig = 0.0, 0.0
        b_n, s_n = 0, 0
        for ts in buys["timestamp"]:
            ahead = ts + LOOKAHEAD
            if ts in p.index and ahead in p.index:
                b_sig += p.loc[ahead] - p.loc[ts]; b_n += 1
        for ts in sells["timestamp"]:
            ahead = ts + LOOKAHEAD
            if ts in p.index and ahead in p.index:
                s_sig += p.loc[ahead] - p.loc[ts]; s_n += 1
        rows.append({
            "trader": trader,
            "buy_n": b_n,
            "buy_avg_fwd": b_sig / b_n if b_n else 0,
            "sell_n": s_n,
            "sell_avg_fwd": s_sig / s_n if s_n else 0,
            "score": (b_sig / max(b_n,1)) - (s_sig / max(s_n,1)),
        })
    return pd.DataFrame(rows)

PRODUCTS = ["HYDROGEL_PACK", "VELVETFRUIT_EXTRACT"]
for day in [1, 2, 3]:
    px, tr = load_day(day)
    for prod in PRODUCTS:
        df = score_traders(px, tr, prod).sort_values("score", ascending=False)
        print(f"\n=== day {day} :: {prod} ===")
        print(df.to_string(index=False))
