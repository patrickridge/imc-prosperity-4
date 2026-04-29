from dash import html, dcc


def build_strategy_breakdown_panel():
    return html.Div(
        style={"marginTop": "16px"},
        children=[
            html.H4("Strategy Breakdown", style={"marginBottom": "4px"}),
            dcc.Graph(id="strategy-breakdown-chart"),
        ],
    )
