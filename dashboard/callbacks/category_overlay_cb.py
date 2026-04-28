from dash import Input, Output
from dashboard.data_loader import load_prices
from dashboard.figures.category_overlay import build_category_overlay


def register_category_overlay_callbacks(app):
    @app.callback(
        Output("category-overlay-chart", "figure"),
        Input("round-selector", "value"),
        Input("day-selector", "value"),
        Input("category-selector", "value"),
        Input("category-normalize", "value"),
    )
    def update_category_overlay(round_num, day, category, normalize_value):
        if not all([round_num, day, category]):
            return {}
        prices = load_prices(round_num, day)
        normalize = bool(normalize_value and "norm" in normalize_value)
        return build_category_overlay(prices, category, normalize)
