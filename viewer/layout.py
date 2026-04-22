from __future__ import annotations

from dash import dcc, html


def serve_layout():
    return html.Div(
        [
            dcc.Store(id="viewer-window"),
            dcc.Store(id="viewer-pending-window"),
            dcc.Interval(
                id="viewer-window-debounce",
                interval=250,
                n_intervals=0,
                disabled=True,
                max_intervals=1,
            ),
            html.Div(
                [
                    html.H1("SeisStream Viewer", style={"margin": "0 0 4px"}),
                    html.Div(id="viewer-status", style={"color": "#555"}),
                ],
                style={"marginBottom": "16px"},
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
                                style={"minWidth": "240px", "flex": "2 1 320px"},
                            ),
                            html.Div(
                                [
                                    html.Label("Channels", style={"fontWeight": "600", "display": "block", "marginBottom": "6px"}),
                                    dcc.Dropdown(id="channel-select", multi=True),
                                ],
                                style={"minWidth": "180px", "flex": "1 1 220px"},
                            ),
                        ],
                        style={
                            "display": "flex",
                            "gap": "12px",
                            "alignItems": "end",
                            "flexWrap": "wrap",
                            "marginBottom": "16px",
                        },
                    ),
                    dcc.Graph(
                        id="waveform-graph",
                        config={
                            "displaylogo": False,
                            "responsive": True,
                            "scrollZoom": True,
                        },
                        style={"height": "72vh"},
                    ),
                ],
                style={"display": "block"},
            ),
        ],
        style={
            "padding": "20px",
            "maxWidth": "1400px",
            "margin": "0 auto",
            "fontFamily": "system-ui, sans-serif",
            "color": "#222",
        },
    )
