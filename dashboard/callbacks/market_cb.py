from dash import Input, Output
from dashboard.data_loader import load_prices, load_trades, filter_by_product, add_trade_sides
from dashboard.figures.orderbook import build_orderbook_scatter
from dashboard.figures.trades import add_trade_markers


def register_market_callbacks(app):
    @app.callback(
        Output("market-chart", "figure"),
        Input("round-selector", "value"),
        Input("day-selector", "value"),
        Input("product-selector", "value"),
        Input("normalization", "value"),
        Input("downsample", "value"),
    )
    def update_market(round_num, day, product, normalization, downsample):
        if not all([round_num, day, product]):
            return {}

        prices = filter_by_product(load_prices(round_num, day), product)
        trades = filter_by_product(load_trades(round_num, day), product, col="symbol")
        trades = add_trade_sides(trades, prices)
        downsample = max(1, int(downsample or 1))

        fig = build_orderbook_scatter(prices, trades, normalization, downsample)
        add_trade_markers(fig, trades, normalization, prices_df=prices)
        return fig
