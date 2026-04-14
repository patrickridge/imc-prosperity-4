from dash import Input, Output
from dashboard.data_loader import list_available_data, get_products


def register_selector_callbacks(app):
    @app.callback(
        Output("day-selector", "options"),
        Output("day-selector", "value"),
        Input("round-selector", "value"),
    )
    def update_days(round_num):
        if not round_num:
            return [], None
        available = list_available_data()
        days = sorted(d for r, d in available if r == round_num)
        options = [{"label": f"Day {d}", "value": d} for d in days]
        default = days[0] if days else None
        return options, default

    @app.callback(
        Output("product-selector", "options"),
        Output("product-selector", "value"),
        Input("round-selector", "value"),
        Input("day-selector", "value"),
    )
    def update_products(round_num, day):
        if not round_num or not day:
            return [], None
        products = get_products(round_num, day)
        options = [{"label": p, "value": p} for p in products]
        default = products[0] if products else None
        return options, default
