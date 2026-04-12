import os
import glob
import functools
import pandas as pd
import numpy as np
from dashboard.constants import CSV_SEPARATOR

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
BACKTESTS_DIR = os.path.join(os.path.dirname(__file__), "..", "backtests")


def list_available_data():
    rounds = sorted(glob.glob(os.path.join(DATA_DIR, "round*")))
    result = []
    for round_dir in rounds:
        round_num = os.path.basename(round_dir).replace("round", "")
        price_files = glob.glob(os.path.join(round_dir, "prices_*.csv"))
        for f in price_files:
            day = f.split("day_")[1].replace(".csv", "")
            result.append((round_num, day))
    return sorted(result)


@functools.lru_cache(maxsize=16)
def load_prices(round_num, day):
    path = os.path.join(DATA_DIR, f"round{round_num}", f"prices_round_{round_num}_day_{day}.csv")
    if not os.path.exists(path):
        return pd.DataFrame()
    return pd.read_csv(path, sep=CSV_SEPARATOR)


@functools.lru_cache(maxsize=16)
def load_trades(round_num, day):
    path = os.path.join(DATA_DIR, f"round{round_num}", f"trades_round_{round_num}_day_{day}.csv")
    if not os.path.exists(path):
        return pd.DataFrame()
    df = pd.read_csv(path, sep=CSV_SEPARATOR)
    return df


def infer_trade_side(trade_price, mid_price):
    if trade_price >= mid_price:
        return "buy"
    return "sell"


def add_trade_sides(trades_df, prices_df):
    if trades_df.empty or prices_df.empty:
        return trades_df

    mid_at_trade = np.interp(
        trades_df["timestamp"],
        prices_df["timestamp"],
        prices_df["mid_price"],
    )
    trades_df = trades_df.copy()
    trades_df["side"] = [
        infer_trade_side(p, m)
        for p, m in zip(trades_df["price"], mid_at_trade)
    ]
    return trades_df


def get_products(round_num, day):
    prices = load_prices(round_num, day)
    if prices.empty:
        return []
    return sorted(prices["product"].unique().tolist())


def filter_by_product(df, product, col="product"):
    if col not in df.columns:
        col = "symbol"
    if col not in df.columns:
        return df
    return df[df[col] == product].copy()
