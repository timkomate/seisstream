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
                            html.Div(
                                [
                                    html.Label("Stations", style={"fontWeight": "600", "display": "block", "marginBottom": "6px"}),
                                    dcc.Dropdown(id="station-select", multi=True),
                                ],
                                style={"minWidth": "260px", "flex": "2 1 360px"},
                            ),
                            html.Div(
                                [
                                    html.Label("Channels", style={"fontWeight": "600", "display": "block", "marginBottom": "6px"}),
                                    dcc.Dropdown(id="channel-select", multi=True),
                                ],
                                style={"minWidth": "220px", "flex": "1 1 240px"},
                            ),
                            html.Div(
                                [],
                                style={"display": "none"},
                            ),
                        ],
                        style={
                            **card,
                            "display": "flex",
                            "gap": "16px",
                            "alignItems": "end",
                            "flexWrap": "wrap",
                            "marginBottom": "18px",
                        },
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
                                style={"height": "72vh"},
                            )
                        ],
                        style={**card, "width": "100%"},
                    ),
                ],
                style={"display": "block"},
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
