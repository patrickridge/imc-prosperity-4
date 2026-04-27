"""Per-bot, per-product trade analysis for Round 4.

Loads trade + price data, computes mid at time of trade,
and estimates each bot's PnL on HYDROGEL_PACK and VELVETFRUIT_EXTRACT.
"""

import pandas as pd
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data" / "round4"
PRODUCTS = ["HYDROGEL_PACK", "VELVETFRUIT_EXTRACT"]


def load_trades():
    frames = []
    for day in range(1, 4):
        path = DATA_DIR / f"trades_round_4_day_{day}.csv"
        df = pd.read_csv(path, sep=";")
        df["day"] = day
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def load_mid_prices():
    """Build a lookup: (day, timestamp, product) -> mid_price."""
    frames = []
    for day in range(1, 4):
        path = DATA_DIR / f"prices_round_4_day_{day}.csv"
        df = pd.read_csv(path, sep=";")
        frames.append(df)
    prices = pd.concat(frames, ignore_index=True)
    prices = prices[["day", "timestamp", "product", "mid_price"]]
    return prices.set_index(["day", "timestamp", "product"])["mid_price"]


def unpivot_trades(trades):
    """Turn each trade into two rows: one BUY, one SELL."""
    buys = trades.rename(columns={"buyer": "bot", "seller": "counterparty"})
    buys["side"] = "BUY"

    sells = trades.rename(columns={"seller": "bot", "buyer": "counterparty"})
    sells["side"] = "SELL"

    return pd.concat([buys, sells], ignore_index=True)


def attach_mid(actions, mid_lookup):
    """Attach the most recent mid price to each trade action."""
    mids = []
    for _, row in actions.iterrows():
        key = (row["day"], row["timestamp"], row["symbol"])
        if key in mid_lookup:
            mids.append(mid_lookup[key])
        else:
            mids.append(None)
    actions["mid"] = mids
    return actions


def compute_edge_per_trade(actions):
    """Edge = how much better than mid the bot traded.

    BUY below mid  -> positive edge (good buy)
    SELL above mid -> positive edge (good sell)
    """
    edge = actions["mid"] - actions["price"]
    edge = edge.where(actions["side"] == "BUY", -edge)
    actions["edge"] = edge
    return actions


def summarize(actions):
    """Per (bot, product, side) summary."""
    grouped = actions.groupby(["bot", "symbol", "side"])
    summary = grouped.agg(
        trade_count=("quantity", "size"),
        total_qty=("quantity", "sum"),
        avg_price=("price", "mean"),
        avg_mid=("mid", "mean"),
        avg_edge=("edge", "mean"),
        total_edge=("edge", "sum"),
    ).round(2)
    return summary.sort_values("total_edge", ascending=False)


def main():
    trades = load_trades()
    trades = trades[trades["symbol"].isin(PRODUCTS)]

    mid_lookup = load_mid_prices()

    actions = unpivot_trades(trades)
    actions = attach_mid(actions, mid_lookup)
    actions = compute_edge_per_trade(actions)

    print(" Per-bot, per-product summary \n")
    print(summarize(actions).to_string())


if __name__ == "__main__":
    main()
