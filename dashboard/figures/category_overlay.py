import plotly.graph_objects as go


CATEGORY_PRODUCTS = {
    "GALAXY_SOUNDS": ["DARK_MATTER", "BLACK_HOLES", "PLANETARY_RINGS", "SOLAR_WINDS", "SOLAR_FLAMES"],
    "SLEEP_POD":     ["SUEDE", "LAMB_WOOL", "POLYESTER", "NYLON", "COTTON"],
    "MICROCHIP":     ["CIRCLE", "OVAL", "SQUARE", "RECTANGLE", "TRIANGLE"],
    "PEBBLES":       ["XS", "S", "M", "L", "XL"],
    "ROBOT":         ["VACUUMING", "MOPPING", "DISHES", "LAUNDRY", "IRONING"],
    "UV_VISOR":      ["YELLOW", "AMBER", "ORANGE", "RED", "MAGENTA"],
    "TRANSLATOR":    ["SPACE_GRAY", "ASTRO_BLACK", "ECLIPSE_CHARCOAL", "GRAPHITE_MIST", "VOID_BLUE"],
    "PANEL":         ["1X2", "2X2", "1X4", "2X4", "4X4"],
    "OXYGEN_SHAKE":  ["MORNING_BREATH", "EVENING_BREATH", "MINT", "CHOCOLATE", "GARLIC"],
    "SNACKPACK":     ["CHOCOLATE", "VANILLA", "PISTACHIO", "STRAWBERRY", "RASPBERRY"],
}

LINE_COLORS = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"]


def category_options():
    return [{"label": cat, "value": cat} for cat in CATEGORY_PRODUCTS]


def products_in_category(category):
    if not category:
        return []
    return [f"{category}_{v}" for v in CATEGORY_PRODUCTS[category]]


def build_category_overlay(prices_df, category, normalize_to_first):
    fig = go.Figure()
    if prices_df.empty or not category:
        return fig

    products = products_in_category(category)
    sub = prices_df[prices_df["product"].isin(products)]

    for color, suffix in zip(LINE_COLORS, CATEGORY_PRODUCTS[category]):
        product = f"{category}_{suffix}"
        g = sub[sub["product"] == product].sort_values("timestamp")
        if g.empty:
            continue
        y = g["mid_price"]
        if normalize_to_first:
            y = (y / y.iloc[0] - 1) * 100  # percent change from first observation
        fig.add_trace(go.Scattergl(
            x=g["timestamp"], y=y,
            mode="lines",
            name=suffix,
            line=dict(color=color, width=1.2),
        ))

    y_title = "% change from start" if normalize_to_first else "Mid price"
    fig.update_layout(
        height=400,
        margin=dict(l=50, r=20, t=30, b=30),
        xaxis_title="Timestamp",
        yaxis_title=y_title,
        legend=dict(orientation="h", y=1.02, x=0),
        hovermode="x unified",
        title=dict(text=f"{category} — all 5 variants", x=0.01, font=dict(size=14)),
    )
    if normalize_to_first:
        fig.add_hline(y=0, line_color="#aaa", line_width=0.5)
    return fig
