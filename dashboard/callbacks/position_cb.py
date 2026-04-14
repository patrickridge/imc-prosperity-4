import plotly.graph_objects as go
from dash import Input, Output
from dashboard.data_loader import load_backtest_log, get_position_over_time
from dashboard.constants import POSITION_COLOR, SMALL_CHART_HEIGHT


POSITION_LIMIT = 80


def register_position_callbacks(app):
    @app.callback(
        Output("position-chart", "figure"),
        Input("product-selector", "value"),
        Input("backtest-selector", "value"),
    )
    def update_position(product, bt_log):
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

        bt_data = load_backtest_log(bt_log)
        pos_df = get_position_over_time(bt_data, product)

        if pos_df.empty:
            return fig

        fig.add_trace(go.Scattergl(
            x=pos_df["timestamp"], y=pos_df["position"],
            mode="lines", line=dict(color=POSITION_COLOR, width=1.5),
            name="Position",
            hovertemplate="t=%{x}<br>pos=%{y}<extra></extra>",
        ))

        fig.add_hline(y=POSITION_LIMIT, line_dash="dash", line_color="red",
                      annotation_text=f"+{POSITION_LIMIT} limit")
        fig.add_hline(y=-POSITION_LIMIT, line_dash="dash", line_color="red",
                      annotation_text=f"-{POSITION_LIMIT} limit")
        fig.add_hline(y=0, line_color="#ccc", line_width=0.5)

        return fig
