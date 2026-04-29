import plotly.graph_objects as go


# Maps a product to the strategy that owns it in r5_combined.
PRODUCT_STRATEGY = {}

PEBBLES = ["PEBBLES_XS", "PEBBLES_S", "PEBBLES_M", "PEBBLES_L", "PEBBLES_XL"]
SNACKPACK = [f"SNACKPACK_{x}" for x in ["CHOCOLATE", "VANILLA", "PISTACHIO", "STRAWBERRY", "RASPBERRY"]]
GALAXY_OXYGEN = [
    "GALAXY_SOUNDS_BLACK_HOLES", "GALAXY_SOUNDS_DARK_MATTER",
    "GALAXY_SOUNDS_SOLAR_FLAMES", "GALAXY_SOUNDS_PLANETARY_RINGS",
    "GALAXY_SOUNDS_SOLAR_WINDS",
    "OXYGEN_SHAKE_GARLIC", "OXYGEN_SHAKE_CHOCOLATE", "OXYGEN_SHAKE_EVENING_BREATH",
]
PANEL_SPREAD = ["PANEL_1X4", "PANEL_2X2"]
ROBOT_DISHES = ["ROBOT_DISHES"]
MICROCHIP = ["MICROCHIP_CIRCLE", "MICROCHIP_OVAL", "MICROCHIP_SQUARE",
             "MICROCHIP_RECTANGLE", "MICROCHIP_TRIANGLE"]

for p in PEBBLES:        PRODUCT_STRATEGY[p] = "pebbles"
for p in SNACKPACK:      PRODUCT_STRATEGY[p] = "snackpack"
for p in GALAXY_OXYGEN:  PRODUCT_STRATEGY[p] = "galaxy_oxygen"
for p in PANEL_SPREAD:   PRODUCT_STRATEGY[p] = "panel_spread"
for p in ROBOT_DISHES:   PRODUCT_STRATEGY[p] = "robot_dishes"
for p in MICROCHIP:      PRODUCT_STRATEGY[p] = "microchip"


STRATEGY_COLORS = {
    "pebbles":       "#1f77b4",
    "galaxy_oxygen": "#ff7f0e",
    "snackpack":     "#2ca02c",
    "robot_dishes":  "#d62728",
    "panel_spread":  "#9467bd",
    "microchip":     "#8c564b",
    "fallback_mm":   "#7f7f7f",
}


def strategy_for(product):
    return PRODUCT_STRATEGY.get(product, "fallback_mm")


def build_strategy_breakdown(activities_df):
    fig = go.Figure()
    if activities_df is None or activities_df.empty:
        fig.add_annotation(
            text="No backtest log selected",
            xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False,
        )
        fig.update_layout(height=300)
        return fig

    last_per_product = activities_df.sort_values("timestamp").groupby("product").last()
    last_per_product = last_per_product.reset_index()
    last_per_product["strategy"] = last_per_product["product"].apply(strategy_for)

    by_strategy = (last_per_product
                   .groupby("strategy")["profit_and_loss"]
                   .sum()
                   .sort_values(ascending=True))

    colors = [STRATEGY_COLORS.get(s, "#666") for s in by_strategy.index]

    fig.add_trace(go.Bar(
        x=by_strategy.values,
        y=by_strategy.index,
        orientation="h",
        marker=dict(color=colors),
        text=[f"{v:+,.0f}" for v in by_strategy.values],
        textposition="outside",
        hovertemplate="%{y}: %{x:+,.0f}<extra></extra>",
    ))

    total = by_strategy.sum()
    fig.update_layout(
        height=300,
        margin=dict(l=120, r=80, t=30, b=30),
        title=dict(text=f"Final PnL by sub-strategy — total {total:+,.0f}",
                   x=0.01, font=dict(size=14)),
        xaxis_title="PnL",
        yaxis_title="",
        showlegend=False,
        bargap=0.3,
    )
    return fig
