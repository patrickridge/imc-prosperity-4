import plotly.graph_objects as go
from dashboard.constants import (
    BID_COLORS, ASK_COLORS, DOT_SIZE_BASE, DOT_OPACITY_BY_LEVEL,
    LOB_LEVELS, PRICE_BID_COLS, PRICE_ASK_COLS,
    VOLUME_BID_COLS, VOLUME_ASK_COLS, NORM_RELATIVE_MID,
)


def build_orderbook_scatter(prices_df, trades_df, normalization, downsample):
    fig = go.Figure()
    if prices_df.empty:
        return fig

    df = prices_df.iloc[::downsample].copy()
    ts = df["timestamp"]
    offset = df["mid_price"] if normalization == NORM_RELATIVE_MID else 0

    for level in range(LOB_LEVELS):
        bid_prices = df[PRICE_BID_COLS[level]] - offset
        ask_prices = df[PRICE_ASK_COLS[level]] - offset
        bid_volumes = df[VOLUME_BID_COLS[level]]
        ask_volumes = df[VOLUME_ASK_COLS[level]]
        opacity = DOT_OPACITY_BY_LEVEL[level]
        level_label = f"L{level + 1}"

        fig.add_trace(go.Scattergl(
            x=ts, y=bid_prices,
            mode="markers",
            marker=dict(size=DOT_SIZE_BASE, color=BID_COLORS[level], opacity=opacity),
            name=f"Bid {level_label}",
            customdata=bid_volumes,
            hovertemplate="t=%{x}<br>bid=%{y:.1f}<br>vol=%{customdata}<extra></extra>",
        ))

        fig.add_trace(go.Scattergl(
            x=ts, y=ask_prices,
            mode="markers",
            marker=dict(size=DOT_SIZE_BASE, color=ASK_COLORS[level], opacity=opacity),
            name=f"Ask {level_label}",
            customdata=ask_volumes,
            hovertemplate="t=%{x}<br>ask=%{y:.1f}<br>vol=%{customdata}<extra></extra>",
        ))

    fig.update_layout(
        height=400,
        margin=dict(l=50, r=20, t=30, b=30),
        xaxis_title="Timestamp",
        yaxis_title="Price" if normalization != NORM_RELATIVE_MID else "Price (relative)",
        legend=dict(orientation="h", y=1.02, x=0),
        hovermode="closest",
    )
    return fig
