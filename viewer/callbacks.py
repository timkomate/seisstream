from __future__ import annotations

from datetime import datetime, timedelta, timezone

import plotly.graph_objects as go
from dash import Input, Output, State, callback
from dash.exceptions import PreventUpdate
from plotly.subplots import make_subplots

from viewer import db


CHANNEL_COLORS = [
    "#1f77b4",
    "#d62728",
    "#2ca02c",
]


def register_callbacks() -> None:
    @callback(
        Output("station-select", "options"),
        Output("station-select", "value"),
        Output("channel-select", "options"),
        Output("channel-select", "value"),
        Output("viewer-window", "data"),
        Output("viewer-status", "children"),
        Input("viewer-status", "id"),
    )
    def initialize_viewer(_component_id: str):
        try:
            stations = db.station_options()
            channels = db.channel_options()
            window = db.default_window()
            if not stations or not channels or not window:
                return [], [], [], [], None, "No waveform data available in TimescaleDB."
            return (
                stations,
                [item["value"] for item in stations[:3]],
                channels,
                [channels[0]["value"]],
                window,
                f"Loaded latest DB window from {window['start_ts']} to {window['end_ts']}.",
            )
        except Exception as exc:
            return [], [], [], [], None, f"Viewer DB initialization failed: {exc}"

    @callback(
        Output("viewer-pending-window", "data"),
        Output("viewer-window-debounce", "disabled"),
        Output("viewer-window-debounce", "n_intervals"),
        Output("viewer-window-debounce", "max_intervals"),
        Input("waveform-graph", "relayoutData"),
        State("viewer-window", "data"),
        prevent_initial_call=True,
    )
    def queue_window_from_graph(
        relayout_data: dict | None,
        current_window: dict | None,
    ):
        if not relayout_data or not current_window:
            raise PreventUpdate

        if "xaxis.range[0]" in relayout_data and "xaxis.range[1]" in relayout_data:
            start_ts = normalize_plotly_ts(relayout_data["xaxis.range[0]"])
            end_ts = normalize_plotly_ts(relayout_data["xaxis.range[1]"])
            return {"start_ts": start_ts, "end_ts": end_ts}, False, 0, 1

        if "xaxis.autorange" in relayout_data:
            window = db.default_window()
            if not window:
                return None, True, 0, 0
            return window, False, 0, 1

        raise PreventUpdate

    @callback(
        Output("viewer-window", "data", allow_duplicate=True),
        Output("viewer-status", "children", allow_duplicate=True),
        Output("viewer-window-debounce", "disabled", allow_duplicate=True),
        Input("viewer-window-debounce", "n_intervals"),
        State("viewer-pending-window", "data"),
        prevent_initial_call=True,
    )
    def apply_debounced_window(_n_intervals: int, pending_window: dict | None):
        if not pending_window:
            raise PreventUpdate
        return (
            pending_window,
            f"Loaded window from {pending_window['start_ts']} to {pending_window['end_ts']}.",
            True,
        )

    @callback(
        Output("waveform-graph", "figure"),
        Input("station-select", "value"),
        Input("channel-select", "value"),
        Input("viewer-window", "data"),
    )
    def load_window(stations: list[str], channels: list[str], window: dict | None):
        if not stations or not channels or not window:
            return empty_figure("Load a DB window first.")

        start_ts = parse_ts(window["start_ts"])
        end_ts = parse_ts(window["end_ts"])
        traces = db.fetch_waveforms(stations, channels, start_ts, end_ts)

        if len(traces) == 0:
            return empty_figure("No waveform samples found for the current selection.")

        station_traces = selected_station_streams(traces, stations)

        fig = make_subplots(
            rows=len(station_traces),
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.1,
            subplot_titles=[station_label(key) for key, _station_stream in station_traces],
        )

        for row_index, (station_key, station_stream) in enumerate(station_traces, start=1):
            for trace in station_stream:
                trace_start = trace.stats.starttime.datetime.replace(tzinfo=timezone.utc)
                trace_times = [
                    trace_start + timedelta(seconds=offset)
                    for offset in trace.times(type="relative")
                ]
                fig.add_trace(
                    go.Scattergl(
                        x=trace_times,
                        y=trace.data,
                        mode="lines",
                        name=f"{station_label(station_key)}.{trace.stats.channel}",
                        line={"width": 1.0, "color": channel_color(trace.stats.channel, channels)},
                        hovertemplate=(
                            f"{trace.stats.channel}<br>"
                            "%{x|%Y-%m-%d %H:%M:%S}<br>%{y}<extra></extra>"
                        ),
                    ),
                    row=row_index,
                    col=1,
                )

        fig.update_layout(
            template="plotly_white",
            height=max(360, 220 * len(station_traces)),
            margin={"l": 50, "r": 20, "t": 50, "b": 40},
            showlegend=False,
            dragmode="pan",
        )
        fig.update_annotations(x=0, xanchor="left")
        fig.update_xaxes(
            title_text="",
            showgrid=True,
            gridcolor="#e5e5e5",
            range=[start_ts, end_ts],
        )
        fig.update_yaxes(
            title_text="",
            showgrid=True,
            gridcolor="#eeeeee",
            autorange=True,
            fixedrange=True,
        )

        return fig


def empty_figure(title: str) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        template="plotly_white",
        title=title,
        dragmode="pan",
    )
    return fig


def parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def station_label(station_key: str) -> str:
    net, sta, loc = db.parse_station_key(station_key)
    return f"{net}.{sta}.{loc}" if loc else f"{net}.{sta}"


def selected_station_streams(traces, station_keys: list[str]):
    station_traces = []
    for key in station_keys:
        net, sta, loc = db.parse_station_key(key)
        station_stream = traces.select(network=net, station=sta, location=loc)
        if station_stream:
            station_traces.append((key, station_stream))
    return station_traces


def channel_color(channel: str, selected_channels: list[str]) -> str:
    channel_index = selected_channels.index(channel) if channel in selected_channels else 0
    return CHANNEL_COLORS[channel_index % len(CHANNEL_COLORS)]


def normalize_plotly_ts(value) -> str:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc).isoformat()
