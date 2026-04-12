from dash import html, dcc


def build_depth_panel():
    return html.Div([
        html.H4("LOB Depth", style={"marginBottom": "4px"}),
        dcc.Graph(id="depth-chart"),
    ])
