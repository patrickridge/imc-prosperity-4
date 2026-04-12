from dash import html, dcc


def build_market_panel():
    return html.Div([
        html.H4("Order Book & Trades", style={"marginBottom": "4px"}),
        dcc.Graph(id="market-chart", config={"scrollZoom": True}),
    ])
