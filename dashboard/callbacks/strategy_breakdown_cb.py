from dash import Input, Output
from dashboard.data_loader import load_backtest_log
from dashboard.figures.strategy_breakdown import build_strategy_breakdown


def register_strategy_breakdown_callbacks(app):
    @app.callback(
        Output("strategy-breakdown-chart", "figure"),
        Input("backtest-selector", "value"),
    )
    def update_strategy_breakdown(bt_log):
        if not bt_log:
            return build_strategy_breakdown(None)
        bt_data = load_backtest_log(bt_log)
        if bt_data is None:
            return build_strategy_breakdown(None)
        return build_strategy_breakdown(bt_data["activities"])
