from dash import Input, Output
from dashboard.data_loader import load_prices, filter_by_product
from dashboard.figures.spread_fig import build_spread_figure


def register_spread_callbacks(app):
    @app.callback(
        Output("spread-chart", "figure"),
        Input("round-selector", "value"),
        Input("day-selector", "value"),
        Input("product-selector", "value"),
        Input("downsample", "value"),
    )
    def update_spread(round_num, day, product, downsample):
        if not all([round_num, day, product]):
            return {}
        prices = filter_by_product(load_prices(round_num, day), product)
        return build_spread_figure(prices, max(1, int(downsample or 1)))
