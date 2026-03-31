from __future__ import annotations

import dash

from viewer.callbacks import register_callbacks
from viewer.layout import serve_layout


app = dash.Dash(__name__, title="SeisStream Viewer")
app.layout = serve_layout
register_callbacks()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8050, debug=False)
