from dash import html, dcc


def build_pnl_panel():
    return html.Div([
        html.H4("Profit & Loss", style={"marginBottom": "4px"}),
        dcc.Graph(id="pnl-chart"),
    ])
