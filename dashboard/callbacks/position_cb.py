import os
import plotly.graph_objects as go
from dash import Input, Output
from dashboard.data_loader import load_backtest_log, get_position_over_time
from dashboard.constants import POSITION_COLOR, SMALL_CHART_HEIGHT


COMPARE_COLOR = "#FF5722"

R5_CATEGORIES = [
    "GALAXY_SOUNDS", "SLEEP_POD", "MICROCHIP", "PEBBLES", "ROBOT",
    "UV_VISOR", "TRANSLATOR", "PANEL", "OXYGEN_SHAKE", "SNACKPACK",
]
R5_POSITION_LIMIT = 10

POSITION_LIMITS = {
    "ASH_COATED_OSMIUM": 80,
    "INTARIAN_PEPPER_ROOT": 80,
    "HYDROGEL_PACK": 200,
    "VELVETFRUIT_EXTRACT": 200,
    "VEV_4000": 300, "VEV_4500": 300, "VEV_5000": 300, "VEV_5100": 300,
    "VEV_5200": 300, "VEV_5300": 300, "VEV_5400": 300, "VEV_5500": 300,
    "VEV_6000": 300, "VEV_6500": 300,
}
DEFAULT_LIMIT = 200


def position_limit_for(product):
    if product in POSITION_LIMITS:
        return POSITION_LIMITS[product]
    if any(product.startswith(prefix + "_") for prefix in R5_CATEGORIES):
        return R5_POSITION_LIMIT
    return DEFAULT_LIMIT


def short_log_name(path):
    if not path:
        return ""
    return os.path.basename(path).replace(".log", "")


def add_position_trace(fig, bt_log, product, color, label_suffix=""):
    bt_data = load_backtest_log(bt_log)
    pos_df = get_position_over_time(bt_data, product)
    if pos_df.empty:
        return
    fig.add_trace(go.Scattergl(
        x=pos_df["timestamp"], y=pos_df["position"],
        mode="lines", line=dict(color=color, width=1.5),
        name=f"Position{label_suffix}",
        hovertemplate=f"t=%{{x}}<br>pos=%{{y}}{label_suffix}<extra></extra>",
    ))


def register_position_callbacks(app):
    @app.callback(
        Output("position-chart", "figure"),
        Input("product-selector", "value"),
        Input("backtest-selector", "value"),
        Input("backtest-compare", "value"),
    )
    def update_position(product, bt_log, compare_log):
        fig = go.Figure()
        fig.update_layout(
            height=SMALL_CHART_HEIGHT,
            margin=dict(l=50, r=20, t=10, b=30),
            xaxis_title="Timestamp",
            yaxis_title="Position",
        )

        if not bt_log or not product:
            fig.add_annotation(
                text="Select a backtest log to view position",
                xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False,
            )
            return fig

        primary_label = f" ({short_log_name(bt_log)})" if compare_log else ""
        add_position_trace(fig, bt_log, product, POSITION_COLOR, primary_label)

        if compare_log and compare_log != bt_log:
            compare_label = f" ({short_log_name(compare_log)})"
            add_position_trace(fig, compare_log, product, COMPARE_COLOR, compare_label)

        limit = position_limit_for(product)
        fig.add_hline(y=limit, line_dash="dash", line_color="red",
                      annotation_text=f"+{limit} limit")
        fig.add_hline(y=-limit, line_dash="dash", line_color="red",
                      annotation_text=f"-{limit} limit")
        fig.add_hline(y=0, line_color="#ccc", line_width=0.5)

        return fig
