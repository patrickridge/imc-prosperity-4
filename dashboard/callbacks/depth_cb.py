from dash import Input, Output
from dashboard.data_loader import load_prices, filter_by_product
from dashboard.figures.lob_depth import build_depth_figure


def register_depth_callbacks(app):
    @app.callback(
        Output("depth-chart", "figure"),
        Input("round-selector", "value"),
        Input("day-selector", "value"),
        Input("product-selector", "value"),
        Input("downsample", "value"),
    )
    def update_depth(round_num, day, product, downsample):
        if not all([round_num, day, product]):
            return {}
        prices = filter_by_product(load_prices(round_num, day), product)
        return build_depth_figure(prices, max(1, int(downsample or 1)))
