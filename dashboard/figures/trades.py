import numpy as np
import plotly.graph_objects as go
from dashboard.constants import (
    BUY_COLOR, SELL_COLOR, OWN_TRADE_COLOR,
    BUY_MARKER, SELL_MARKER, OWN_MARKER,
    TRADE_SIZE_SCALE, NORM_RELATIVE_MID,
)


def add_trade_markers(fig, trades_df, normalization, prices_df=None):
    if trades_df.empty:
        return fig

    df = trades_df.copy()
    df["plot_price"] = df["price"]

    if normalization == NORM_RELATIVE_MID and prices_df is not None and not prices_df.empty:
        mid_at_trade = np.interp(df["timestamp"], prices_df["timestamp"], prices_df["mid_price"])
        df["plot_price"] = df["price"] - mid_at_trade

    buys = df[df["side"] == "buy"]
    sells = df[df["side"] == "sell"]

    def custom_for(subset):
        buyer = subset["buyer"].fillna("?") if "buyer" in subset.columns else ["?"] * len(subset)
        seller = subset["seller"].fillna("?") if "seller" in subset.columns else ["?"] * len(subset)
        return list(zip(subset["quantity"], buyer, seller))

    if not buys.empty:
        fig.add_trace(go.Scattergl(
            x=buys["timestamp"], y=buys["plot_price"],
            mode="markers",
            marker=dict(symbol=BUY_MARKER, size=buys["quantity"] * TRADE_SIZE_SCALE,
                        color=BUY_COLOR, opacity=0.8, line=dict(width=1, color="white")),
            name="Buy trades",
            customdata=custom_for(buys),
            hovertemplate="t=%{x}<br>price=%{y:.1f}<br>qty=%{customdata[0]}<br>%{customdata[1]} ← %{customdata[2]}<extra></extra>",
        ))

    if not sells.empty:
        fig.add_trace(go.Scattergl(
            x=sells["timestamp"], y=sells["plot_price"],
            mode="markers",
            marker=dict(symbol=SELL_MARKER, size=sells["quantity"] * TRADE_SIZE_SCALE,
                        color=SELL_COLOR, opacity=0.8, line=dict(width=1, color="white")),
            name="Sell trades",
            customdata=custom_for(sells),
            hovertemplate="t=%{x}<br>price=%{y:.1f}<br>qty=%{customdata[0]}<br>%{customdata[1]} ← %{customdata[2]}<extra></extra>",
        ))

    return fig


def add_own_trade_markers(fig, own_trades_df, normalization, prices_df=None):
    if own_trades_df.empty:
        return fig

    df = own_trades_df.copy()
    df["plot_price"] = df["price"].astype(float)

    if normalization == NORM_RELATIVE_MID and prices_df is not None and not prices_df.empty:
        mid_at_trade = np.interp(df["timestamp"], prices_df["timestamp"], prices_df["mid_price"])
        df["plot_price"] = df["price"].astype(float) - mid_at_trade

    buys = df[df["side"] == "buy"]
    sells = df[df["side"] == "sell"]

    if not buys.empty:
        fig.add_trace(go.Scattergl(
            x=buys["timestamp"], y=buys["plot_price"],
            mode="markers",
            marker=dict(symbol=OWN_MARKER, size=6, color=OWN_TRADE_COLOR,
                        line=dict(width=1.5, color=OWN_TRADE_COLOR)),
            name="Own buys",
            customdata=buys["quantity"],
            hovertemplate="t=%{x}<br>bought@%{y:.1f}<br>qty=%{customdata}<extra></extra>",
        ))

    if not sells.empty:
        fig.add_trace(go.Scattergl(
            x=sells["timestamp"], y=sells["plot_price"],
            mode="markers",
            marker=dict(symbol=OWN_MARKER, size=6, color="#E040FB",
                        line=dict(width=1.5, color="#E040FB")),
            name="Own sells",
            customdata=sells["quantity"],
            hovertemplate="t=%{x}<br>sold@%{y:.1f}<br>qty=%{customdata}<extra></extra>",
        ))

    return fig
