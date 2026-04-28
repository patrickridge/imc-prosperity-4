import os
import plotly.graph_objects as go
from dash import Input, Output
from dashboard.data_loader import load_backtest_log, get_algo_pnl
from dashboard.constants import PNL_COLOR, SMALL_CHART_HEIGHT


COMPARE_COLOR = "#FF5722"


def add_pnl_traces(fig, bt_log, product, color, label_suffix=""):
    bt_data = load_backtest_log(bt_log)

    product_pnl = get_algo_pnl(bt_data, product)
    if not product_pnl.empty:
        fig.add_trace(go.Scattergl(
            x=product_pnl["timestamp"], y=product_pnl["profit_and_loss"],
            mode="lines", line=dict(color=color, width=1.5),
            name=f"{product} PnL{label_suffix}",
            hovertemplate=f"t=%{{x}}<br>PnL=%{{y:,.0f}}{label_suffix}<extra></extra>",
        ))

    total_pnl = get_algo_pnl(bt_data)
    if not total_pnl.empty:
        fig.add_trace(go.Scattergl(
            x=total_pnl["timestamp"], y=total_pnl["profit_and_loss"],
            mode="lines", line=dict(color=color, width=1, dash="dot"),
            name=f"Total PnL{label_suffix}",
            hovertemplate=f"t=%{{x}}<br>Total=%{{y:,.0f}}{label_suffix}<extra></extra>",
        ))


def short_log_name(path):
    if not path:
        return ""
    return os.path.basename(path).replace(".log", "")


def register_pnl_callbacks(app):
    @app.callback(
        Output("pnl-chart", "figure"),
        Input("product-selector", "value"),
        Input("backtest-selector", "value"),
        Input("backtest-compare", "value"),
    )
    def update_pnl(product, bt_log, compare_log):
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

        primary_label = f" ({short_log_name(bt_log)})" if compare_log else ""
        add_pnl_traces(fig, bt_log, product, PNL_COLOR, primary_label)

        if compare_log and compare_log != bt_log:
            compare_label = f" ({short_log_name(compare_log)})"
            add_pnl_traces(fig, compare_log, product, COMPARE_COLOR, compare_label)

        return fig
