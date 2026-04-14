from dash import html, dash_table


def build_trade_table():
    return html.Div([
        html.H4("Trades", style={"marginBottom": "4px"}),
        dash_table.DataTable(
            id="trade-table",
            columns=[
                {"name": "Timestamp", "id": "timestamp"},
                {"name": "Symbol", "id": "symbol"},
                {"name": "Price", "id": "price"},
                {"name": "Quantity", "id": "quantity"},
                {"name": "Side", "id": "side"},
                {"name": "Buyer", "id": "buyer"},
                {"name": "Seller", "id": "seller"},
            ],
            page_size=30,
            sort_action="native",
            filter_action="native",
            style_table={"overflowX": "auto"},
            style_cell={"textAlign": "left", "padding": "4px", "fontSize": "13px"},
            style_header={"fontWeight": "bold"},
        ),
    ])
