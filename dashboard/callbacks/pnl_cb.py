import plotly.graph_objects as go
from dash import Input, Output
from dashboard.data_loader import load_prices, filter_by_product
from dashboard.constants import PNL_COLOR, SMALL_CHART_HEIGHT


def register_pnl_callbacks(app):
    @app.callback(
        Output("pnl-chart", "figure"),
        Input("round-selector", "value"),
        Input("day-selector", "value"),
        Input("product-selector", "value"),
        Input("downsample", "value"),
    )
    def update_pnl(round_num, day, product, downsample):
        if not all([round_num, day, product]):
            return {}

        prices = filter_by_product(load_prices(round_num, day), product)
        if prices.empty or "profit_and_loss" not in prices.columns:
            return {}

        df = prices.iloc[::max(1, int(downsample or 1))]
        fig = go.Figure()
        fig.add_trace(go.Scattergl(
            x=df["timestamp"],
            y=df["profit_and_loss"],
            mode="lines",
            line=dict(color=PNL_COLOR, width=1.5),
            name="PnL",
            hovertemplate="t=%{x}<br>PnL=%{y:.2f}<extra></extra>",
        ))
        fig.update_layout(
            height=SMALL_CHART_HEIGHT,
            margin=dict(l=50, r=20, t=10, b=30),
            xaxis_title="Timestamp",
            yaxis_title="PnL",
            showlegend=False,
        )
        return fig
