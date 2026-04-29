from dash import Dash, html
from dashboard.layouts.sidebar import build_sidebar
from dashboard.layouts.market import build_market_panel
from dashboard.layouts.spread import build_spread_panel
from dashboard.layouts.depth import build_depth_panel
from dashboard.layouts.pnl import build_pnl_panel
from dashboard.layouts.position import build_position_panel
from dashboard.layouts.trade_table import build_trade_table
from dashboard.layouts.category_overlay import build_category_overlay_panel
from dashboard.layouts.strategy_breakdown import build_strategy_breakdown_panel
from dashboard.callbacks.selectors import register_selector_callbacks
from dashboard.callbacks.market_cb import register_market_callbacks
from dashboard.callbacks.spread_cb import register_spread_callbacks
from dashboard.callbacks.depth_cb import register_depth_callbacks
from dashboard.callbacks.pnl_cb import register_pnl_callbacks
from dashboard.callbacks.position_cb import register_position_callbacks
from dashboard.callbacks.table_cb import register_table_callbacks
from dashboard.callbacks.sync_zoom import register_sync_zoom
from dashboard.callbacks.category_overlay_cb import register_category_overlay_callbacks
from dashboard.callbacks.strategy_breakdown_cb import register_strategy_breakdown_callbacks

app = Dash(__name__, suppress_callback_exceptions=True)

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
                build_position_panel(),
                build_category_overlay_panel(),
                build_strategy_breakdown_panel(),
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
register_position_callbacks(app)
register_table_callbacks(app)
register_sync_zoom(app)
register_category_overlay_callbacks(app)
register_strategy_breakdown_callbacks(app)

if __name__ == "__main__":
    app.run(debug=True, port=8050)
