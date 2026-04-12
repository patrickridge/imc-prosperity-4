from dash import html, dcc


def build_spread_panel():
    return html.Div([
        html.H4("Spread", style={"marginBottom": "4px"}),
        dcc.Graph(id="spread-chart"),
    ])
