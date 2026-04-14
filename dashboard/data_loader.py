import os
import glob
import json
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
    return pd.read_csv(path, sep=CSV_SEPARATOR)


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


# --- Backtest log loading ---

def list_backtest_logs():
    if not os.path.isdir(BACKTESTS_DIR):
        return []
    logs = sorted(glob.glob(os.path.join(BACKTESTS_DIR, "*.log")))
    return [os.path.basename(f) for f in logs]


def _parse_log_sections(text):
    activities_start = text.find("Activities log:\n")
    trades_start = text.find("Trade History:\n")

    sandbox_text = text[:activities_start] if activities_start > 0 else ""
    activities_text = text[activities_start:trades_start] if activities_start > 0 else ""
    trades_text = text[trades_start:] if trades_start > 0 else ""

    return sandbox_text, activities_text, trades_text


def _parse_activities(activities_text):
    lines = activities_text.strip().split("\n")
    header_idx = next((i for i, l in enumerate(lines) if l.startswith("day;")), None)
    if header_idx is None:
        return pd.DataFrame()
    csv_text = "\n".join(lines[header_idx:])
    from io import StringIO
    return pd.read_csv(StringIO(csv_text), sep=";")


def _parse_trades(trades_text):
    bracket_start = trades_text.find("[")
    bracket_end = trades_text.rfind("]")
    if bracket_start < 0 or bracket_end < 0:
        return pd.DataFrame()
    json_text = trades_text[bracket_start:bracket_end + 1]
    # Handle trailing commas before closing braces/brackets
    import re
    json_text = re.sub(r',\s*}', '}', json_text)
    json_text = re.sub(r',\s*]', ']', json_text)
    trades = json.loads(json_text)
    if not trades:
        return pd.DataFrame()
    return pd.DataFrame(trades)


@functools.lru_cache(maxsize=8)
def load_backtest_log(filename):
    path = os.path.join(BACKTESTS_DIR, filename)
    if not os.path.exists(path):
        return None

    with open(path) as f:
        text = f.read()

    _, activities_text, trades_text = _parse_log_sections(text)
    activities = _parse_activities(activities_text)
    trades = _parse_trades(trades_text)

    return {"activities": activities, "trades": trades}


def get_own_trades(backtest_data, product):
    if backtest_data is None:
        return pd.DataFrame()
    trades = backtest_data["trades"]
    if trades.empty:
        return pd.DataFrame()

    own = trades[
        (trades["symbol"] == product) &
        ((trades["buyer"] == "SUBMISSION") | (trades["seller"] == "SUBMISSION"))
    ].copy()

    if own.empty:
        return own

    own["side"] = own.apply(
        lambda r: "buy" if r["buyer"] == "SUBMISSION" else "sell", axis=1
    )
    return own


def get_algo_pnl(backtest_data, product=None):
    if backtest_data is None:
        return pd.DataFrame()
    activities = backtest_data["activities"]
    if activities.empty:
        return pd.DataFrame()

    if product:
        return activities[activities["product"] == product][["timestamp", "profit_and_loss"]].copy()

    return activities.groupby("timestamp")["profit_and_loss"].sum().reset_index()


def get_position_over_time(backtest_data, product):
    own_trades = get_own_trades(backtest_data, product)
    if own_trades.empty:
        return pd.DataFrame()

    rows = []
    position = 0
    for _, trade in own_trades.sort_values("timestamp").iterrows():
        qty = trade["quantity"]
        if trade["side"] == "buy":
            position += qty
        else:
            position -= qty
        rows.append({"timestamp": trade["timestamp"], "position": position})

    return pd.DataFrame(rows)
