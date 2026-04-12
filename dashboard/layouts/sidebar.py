from dash import html, dcc
from dashboard.constants import (
    SIDEBAR_WIDTH, NORMALIZATION_OPTIONS, NORM_RAW,
    DOWNSAMPLE_OPTIONS, DEFAULT_DOWNSAMPLE,
)
from dashboard.data_loader import list_available_data


def build_sidebar():
    available = list_available_data()
    rounds = sorted(set(r for r, d in available))
    default_round = rounds[0] if rounds else "0"

    return html.Div(
        style={"width": SIDEBAR_WIDTH, "padding": "16px", "borderRight": "1px solid #ddd",
               "flexShrink": 0, "overflowY": "auto"},
        children=[
            html.H3("IMC Prosperity 4", style={"marginTop": 0}),
            _dropdown_section("Round", "round-selector", rounds, default_round),
            _dropdown_section("Day", "day-selector", [], None),
            _dropdown_section("Product", "product-selector", [], None),
            _dropdown_section("Normalization", "normalization", NORMALIZATION_OPTIONS, NORM_RAW),
            html.Label("Downsample", style={"fontWeight": "bold", "marginTop": "12px"}),
            dcc.Slider(
                id="downsample",
                min=1, max=10, step=1,
                value=DEFAULT_DOWNSAMPLE,
                marks={v: str(v) for v in DOWNSAMPLE_OPTIONS},
            ),
        ],
    )


def _dropdown_section(label, dropdown_id, options, default):
    return html.Div(style={"marginTop": "12px"}, children=[
        html.Label(label, style={"fontWeight": "bold"}),
        dcc.Dropdown(
            id=dropdown_id,
            options=[{"label": str(o), "value": o} for o in options],
            value=default,
            clearable=False,
        ),
    ])
