"""Framework compatibility only; no product UI or browser rendering claim."""
import json

import pytest

pytestmark = pytest.mark.smoke


def test_community_grid_serializes_without_live_provider(monkeypatch):
    import socket
    def forbidden(*args, **kwargs):
        raise AssertionError("outbound network forbidden")
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    from dash import Dash, html
    import dash_ag_grid as dag
    from plotly.utils import PlotlyJSONEncoder

    grid = dag.AgGrid(id="foundation-grid", columnDefs=[{"field": "question"}],
                      rowData=[{"question": "Synthetic fixture"}], enableEnterpriseModules=False)
    app = Dash(__name__)
    app.layout = html.Div([grid])
    payload = json.loads(json.dumps(grid.to_plotly_json(), cls=PlotlyJSONEncoder))
    assert payload["namespace"] == "dash_ag_grid"
    assert payload["props"]["enableEnterpriseModules"] is False
    response = app.server.test_client().get("/_dash-layout")
    assert response.status_code == 200
    assert b"foundation-grid" in response.data
    assert b"dummy" not in response.data
