from dash import html, dcc


def build_position_panel():
    return html.Div([
        html.H4("Position", style={"marginBottom": "4px"}),
        dcc.Graph(id="position-chart"),
    ])
