import plotly.graph_objects as go
from dashboard.constants import SMALL_CHART_HEIGHT


def build_spread_figure(prices_df, downsample):
    fig = go.Figure()
    if prices_df.empty:
        return fig

    df = prices_df.iloc[::downsample]
    spread = df["ask_price_1"] - df["bid_price_1"]

    fig.add_trace(go.Scattergl(
        x=df["timestamp"],
        y=spread,
        mode="lines",
        line=dict(color="#9C27B0", width=1),
        name="Spread",
        hovertemplate="t=%{x}<br>spread=%{y:.1f}<extra></extra>",
    ))

    fig.update_layout(
        height=SMALL_CHART_HEIGHT,
        margin=dict(l=50, r=20, t=10, b=30),
        xaxis_title="Timestamp",
        yaxis_title="Spread",
        showlegend=False,
    )
    return fig
