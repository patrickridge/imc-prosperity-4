from dash import Input, Output, State, callback_context


SYNCED_CHARTS = ["market-chart", "spread-chart", "depth-chart", "pnl-chart", "position-chart"]


def register_sync_zoom(app):
    @app.callback(
        [Output(chart_id, "figure", allow_duplicate=True) for chart_id in SYNCED_CHARTS],
        [Input(chart_id, "relayoutData") for chart_id in SYNCED_CHARTS],
        [State(chart_id, "figure") for chart_id in SYNCED_CHARTS],
        prevent_initial_call=True,
    )
    def sync_zoom(*args):
        n = len(SYNCED_CHARTS)
        relayout_data = args[:n]
        figures = list(args[n:])

        triggered = callback_context.triggered
        if not triggered:
            return [f for f in figures]

        trigger_id = triggered[0]["prop_id"].split(".")[0]
        trigger_idx = SYNCED_CHARTS.index(trigger_id)
        source_data = relayout_data[trigger_idx]

        if not source_data:
            return [f for f in figures]

        x_range = None
        if "xaxis.range[0]" in source_data and "xaxis.range[1]" in source_data:
            x_range = [source_data["xaxis.range[0]"], source_data["xaxis.range[1]"]]
        elif "xaxis.autorange" in source_data:
            x_range = None

        updated = []
        for i, fig in enumerate(figures):
            if fig is None or not fig:
                updated.append(fig)
                continue
            if isinstance(fig, dict):
                fig = dict(fig)
                layout = fig.get("layout", {})
                if x_range:
                    layout["xaxis"] = {**layout.get("xaxis", {}), "range": x_range, "autorange": False}
                else:
                    layout["xaxis"] = {**layout.get("xaxis", {}), "autorange": True}
                fig["layout"] = layout
            updated.append(fig)

        return updated
