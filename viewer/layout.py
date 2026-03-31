from __future__ import annotations

from dash import dcc, html


def serve_layout():
    card = {
        "background": "#fffaf2",
        "border": "1px solid #e2d5c2",
        "borderRadius": "14px",
        "padding": "16px",
    }
    return html.Div(
        [
            dcc.Store(id="viewer-window"),
            html.Div(
                [
                    html.H1("SeisStream Viewer", style={"marginBottom": "4px"}),
                    html.Div(id="viewer-status", style={"color": "#5b5245"}),
                ],
                style={"marginBottom": "18px"},
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.Label("Stations"),
                            dcc.Dropdown(id="station-select", multi=True),
                            html.Label("Channels", style={"marginTop": "12px", "display": "block"}),
                            dcc.Dropdown(id="channel-select", multi=True),
                            html.Button(
                                "Load Latest Window",
                                id="load-window",
                                n_clicks=0,
                                style={
                                    "marginTop": "12px",
                                    "borderRadius": "999px",
                                    "padding": "10px 16px",
                                    "border": "none",
                                    "background": "#1f4d4f",
                                    "color": "white",
                                },
                            ),
                            html.Button(
                                "Reset Window",
                                id="reset-window",
                                n_clicks=0,
                                style={
                                    "marginTop": "10px",
                                    "borderRadius": "999px",
                                    "padding": "10px 16px",
                                    "border": "1px solid #1f4d4f",
                                    "background": "transparent",
                                    "color": "#1f4d4f",
                                },
                            ),
                        ],
                        style={**card, "position": "sticky", "top": "24px"},
                    ),
                    html.Div(
                        [
                            dcc.Graph(
                                id="waveform-graph",
                                config={
                                    "displaylogo": False,
                                    "responsive": True,
                                    "scrollZoom": True,
                                },
                                style={"height": "70vh"},
                            )
                        ],
                        style={"minWidth": "0", **card},
                    ),
                ],
                style={
                    "display": "grid",
                    "gap": "18px",
                    "gridTemplateColumns": "320px minmax(0, 1fr)",
                    "alignItems": "start",
                },
            ),
            html.Div(
                [
                    html.Div([html.H3("Window"), html.Div(id="window-summary")], style=card),
                    html.Div([html.H3("Picks"), html.Div(id="pick-summary")], style=card),
                    html.Div([html.H3("Origins"), html.Div(id="origin-summary")], style=card),
                ],
                style={
                    "display": "grid",
                    "gap": "18px",
                    "gridTemplateColumns": "repeat(3, minmax(0, 1fr))",
                    "marginTop": "18px",
                },
            ),
        ],
        style={
            "padding": "24px",
            "maxWidth": "1500px",
            "margin": "0 auto",
            "fontFamily": "IBM Plex Sans, Segoe UI, sans-serif",
            "background": "linear-gradient(180deg, #f4ead9 0%, #efe6da 100%)",
            "minHeight": "100vh",
            "color": "#1f2526",
        },
    )
