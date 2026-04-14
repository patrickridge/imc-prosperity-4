import plotly.graph_objects as go
from dashboard.constants import (
    BID_COLORS, ASK_COLORS, LOB_LEVELS,
    VOLUME_BID_COLS, VOLUME_ASK_COLS, SMALL_CHART_HEIGHT,
)


def build_depth_figure(prices_df, downsample):
    fig = go.Figure()
    if prices_df.empty:
        return fig

    df = prices_df.iloc[::downsample]
    ts = df["timestamp"]

    for level in range(LOB_LEVELS):
        bid_vol = df[VOLUME_BID_COLS[level]].fillna(0)
        fig.add_trace(go.Scatter(
            x=ts, y=-bid_vol,
            stackgroup="bids",
            fillcolor=BID_COLORS[level],
            line=dict(width=0),
            name=f"Bid L{level + 1}",
        ))

    for level in range(LOB_LEVELS):
        ask_vol = df[VOLUME_ASK_COLS[level]].fillna(0)
        fig.add_trace(go.Scatter(
            x=ts, y=ask_vol,
            stackgroup="asks",
            fillcolor=ASK_COLORS[level],
            line=dict(width=0),
            name=f"Ask L{level + 1}",
        ))

    fig.update_layout(
        height=SMALL_CHART_HEIGHT,
        margin=dict(l=50, r=20, t=10, b=30),
        xaxis_title="Timestamp",
        yaxis_title="Volume",
        legend=dict(orientation="h", y=1.02, x=0, font=dict(size=9)),
    )
    return fig
