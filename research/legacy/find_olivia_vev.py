"""Check informed-trader signal on VEV strikes too. Aggregate Mark behavior across all VEV strikes."""
import pandas as pd
from pathlib import Path

DATA = Path("/sessions/amazing-upbeat-volta/mnt/imc-prosperity-4/data/round4")
LOOKAHEAD = 5_000

def load_day(day):
    px = pd.read_csv(DATA / f"prices_round_4_day_{day}.csv", sep=";")
    tr = pd.read_csv(DATA / f"trades_round_4_day_{day}.csv", sep=";")
    return px, tr

VEV = [f"VEV_{s}" for s in [4000,4500,5000,5100,5200,5300,5400,5500,6000,6500]]
for day in [1,2,3]:
    px, tr = load_day(day)
    # mid lookups per product
    px["mid"] = (px["bid_price_1"] + px["ask_price_1"]) / 2
    rows = []
    traders = sorted(set(tr["buyer"]) | set(tr["seller"]))
    for trader in traders:
        if not isinstance(trader,str): continue
        b_sig = 0; b_n = 0; s_sig = 0; s_n = 0
        for prod in VEV:
            sub = tr[(tr["symbol"]==prod)]
            p = px[px["product"]==prod].set_index("timestamp")["mid"]
            for ts in sub[sub["buyer"]==trader]["timestamp"]:
                a = ts+LOOKAHEAD
                if ts in p.index and a in p.index:
                    b_sig += p.loc[a]-p.loc[ts]; b_n += 1
            for ts in sub[sub["seller"]==trader]["timestamp"]:
                a = ts+LOOKAHEAD
                if ts in p.index and a in p.index:
                    s_sig += p.loc[a]-p.loc[ts]; s_n += 1
        rows.append({"trader":trader,"buy_n":b_n,"buy_avg":b_sig/max(b_n,1),
                     "sell_n":s_n,"sell_avg":s_sig/max(s_n,1),
                     "score":(b_sig/max(b_n,1))-(s_sig/max(s_n,1))})
    print(f"\n=== day {day} :: VEV (all strikes) ===")
    print(pd.DataFrame(rows).sort_values("score",ascending=False).to_string(index=False))
