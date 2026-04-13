import plotly.graph_objects as go
from dash import Input, Output
from dashboard.data_loader import load_backtest_log, get_algo_pnl
from dashboard.constants import PNL_COLOR, SMALL_CHART_HEIGHT


def register_pnl_callbacks(app):
    @app.callback(
        Output("pnl-chart", "figure"),
        Input("product-selector", "value"),
        Input("backtest-selector", "value"),
    )
    def update_pnl(product, bt_log):
        fig = go.Figure()
        fig.update_layout(
            height=SMALL_CHART_HEIGHT,
            margin=dict(l=50, r=20, t=10, b=30),
            xaxis_title="Timestamp",
            yaxis_title="PnL",
        )

        if not bt_log:
            fig.add_annotation(
                text="Select a backtest log to view PnL",
                xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False,
            )
            return fig

        bt_data = load_backtest_log(bt_log)

        product_pnl = get_algo_pnl(bt_data, product)
        if not product_pnl.empty:
            fig.add_trace(go.Scattergl(
                x=product_pnl["timestamp"], y=product_pnl["profit_and_loss"],
                mode="lines", line=dict(color=PNL_COLOR, width=1.5),
                name=f"{product} PnL",
                hovertemplate="t=%{x}<br>PnL=%{y:,.0f}<extra></extra>",
            ))

        total_pnl = get_algo_pnl(bt_data)
        if not total_pnl.empty:
            fig.add_trace(go.Scattergl(
                x=total_pnl["timestamp"], y=total_pnl["profit_and_loss"],
                mode="lines", line=dict(color="#999", width=1, dash="dot"),
                name="Total PnL",
                hovertemplate="t=%{x}<br>Total=%{y:,.0f}<extra></extra>",
            ))

        return fig
