from dash import Dash, html
from dashboard.layouts.sidebar import build_sidebar
from dashboard.layouts.market import build_market_panel
from dashboard.layouts.spread import build_spread_panel
from dashboard.layouts.depth import build_depth_panel
from dashboard.layouts.pnl import build_pnl_panel
from dashboard.layouts.trade_table import build_trade_table
from dashboard.callbacks.selectors import register_selector_callbacks
from dashboard.callbacks.market_cb import register_market_callbacks
from dashboard.callbacks.spread_cb import register_spread_callbacks
from dashboard.callbacks.depth_cb import register_depth_callbacks
from dashboard.callbacks.pnl_cb import register_pnl_callbacks
from dashboard.callbacks.table_cb import register_table_callbacks

app = Dash(__name__)

app.layout = html.Div(
    style={"display": "flex", "fontFamily": "system-ui, sans-serif", "height": "100vh"},
    children=[
        build_sidebar(),
        html.Div(
            style={"flex": 1, "overflowY": "auto", "padding": "16px"},
            children=[
                build_market_panel(),
                build_spread_panel(),
                build_depth_panel(),
                build_pnl_panel(),
                build_trade_table(),
            ],
        ),
    ],
)

register_selector_callbacks(app)
register_market_callbacks(app)
register_spread_callbacks(app)
register_depth_callbacks(app)
register_pnl_callbacks(app)
register_table_callbacks(app)

if __name__ == "__main__":
    app.run(debug=True, port=8050)
