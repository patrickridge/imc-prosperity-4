from dash import html, dcc
from dashboard.figures.category_overlay import category_options


def build_category_overlay_panel():
    return html.Div(
        style={"marginTop": "16px"},
        children=[
            html.H4("Category Overlay", style={"marginBottom": "4px"}),
            html.Div(
                style={"display": "flex", "gap": "12px", "alignItems": "center",
                       "marginBottom": "8px"},
                children=[
                    html.Label("Category", style={"fontWeight": "bold"}),
                    dcc.Dropdown(
                        id="category-selector",
                        options=category_options(),
                        value="PEBBLES",
                        clearable=False,
                        style={"minWidth": "220px"},
                    ),
                    dcc.Checklist(
                        id="category-normalize",
                        options=[{"label": " normalize to start (% change)", "value": "norm"}],
                        value=["norm"],
                    ),
                ],
            ),
            dcc.Graph(id="category-overlay-chart", config={"scrollZoom": True}),
        ],
    )
