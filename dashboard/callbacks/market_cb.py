from dash import Input, Output
from dashboard.data_loader import (
    load_prices, load_trades, load_backtest_log,
    filter_by_product, add_trade_sides, get_own_trades,
)
from dashboard.figures.orderbook import build_orderbook_scatter
from dashboard.figures.trades import add_trade_markers, add_own_trade_markers


def register_market_callbacks(app):
    @app.callback(
        Output("market-chart", "figure"),
        Input("round-selector", "value"),
        Input("day-selector", "value"),
        Input("product-selector", "value"),
        Input("normalization", "value"),
        Input("downsample", "value"),
        Input("backtest-selector", "value"),
    )
    def update_market(round_num, day, product, normalization, downsample, bt_log):
        if not all([round_num, day, product]):
            return {}

        prices = filter_by_product(load_prices(round_num, day), product)
        trades = filter_by_product(load_trades(round_num, day), product, col="symbol")
        trades = add_trade_sides(trades, prices)
        downsample = max(1, int(downsample or 1))

        fig = build_orderbook_scatter(prices, trades, normalization, downsample)
        add_trade_markers(fig, trades, normalization, prices_df=prices)

        if bt_log:
            bt_data = load_backtest_log(bt_log)
            own_trades = get_own_trades(bt_data, product)
            add_own_trade_markers(fig, own_trades, normalization, prices_df=prices)

        return fig
