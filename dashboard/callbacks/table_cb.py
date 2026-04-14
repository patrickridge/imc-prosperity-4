from dash import Input, Output
from dashboard.data_loader import load_prices, load_trades, filter_by_product, add_trade_sides


def register_table_callbacks(app):
    @app.callback(
        Output("trade-table", "data"),
        Input("round-selector", "value"),
        Input("day-selector", "value"),
        Input("product-selector", "value"),
    )
    def update_table(round_num, day, product):
        if not all([round_num, day, product]):
            return []

        prices = filter_by_product(load_prices(round_num, day), product)
        trades = filter_by_product(load_trades(round_num, day), product, col="symbol")
        trades = add_trade_sides(trades, prices)

        if trades.empty:
            return []
        return trades.to_dict("records")
