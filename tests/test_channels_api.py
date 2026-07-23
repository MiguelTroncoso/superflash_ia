"""Tests de los endpoints de canales y su histórico."""

from datetime import UTC, datetime

from app.models import Channel, ChannelMetric, ChannelStatus, Server, ServerRole


def _seed_channels(session) -> tuple[Server, Channel, Channel]:
    server = Server(
        external_id="srv-a",
        name="Servidor A",
        role=ServerRole.LIVE,
        network_capacity_mbps=1000.0,
        enabled=True,
    )
    session.add(server)
    session.flush()

    sports = Channel(
        external_id="ch-sports",
        name="Deportes HD",
        category="deportes",
        current_server_id=server.id,
        enabled=True,
    )
    movies = Channel(
        external_id="ch-movies",
        name="Cine Noche",
        category="cine",
        current_server_id=None,
        enabled=False,
    )
    session.add_all([sports, movies])
    session.flush()

    for hour in (9, 10):
        session.add(
            ChannelMetric(
                channel_id=sports.id,
                server_id=server.id,
                collected_at=datetime(2026, 7, 23, hour, 0, tzinfo=UTC),
                viewers=100 * hour,
                bitrate_mbps=4.0,
                estimated_output_mbps=400.0 * hour,
                status=ChannelStatus.ONLINE,
            )
        )
    session.commit()
    return server, sports, movies


def test_list_channels_filters(client, session):
    """Los filtros server_id, category y enabled acotan el listado."""
    server, _sports, _movies = _seed_channels(session)

    everything = client.get("/api/v1/channels").json()
    assert len(everything) == 2

    by_server = client.get("/api/v1/channels", params={"server_id": server.id}).json()
    assert [item["external_id"] for item in by_server] == ["ch-sports"]

    by_category = client.get("/api/v1/channels", params={"category": "cine"}).json()
    assert [item["external_id"] for item in by_category] == ["ch-movies"]

    enabled_only = client.get("/api/v1/channels", params={"enabled": "true"}).json()
    assert [item["external_id"] for item in enabled_only] == ["ch-sports"]


def test_channel_metrics_history(client, session):
    """El histórico del canal se consulta con rango y orden descendente."""
    _, sports, _ = _seed_channels(session)

    response = client.get(f"/api/v1/channels/{sports.id}/metrics")
    assert response.status_code == 200
    body = response.json()
    assert [item["viewers"] for item in body] == [1000, 900]

    ranged = client.get(
        f"/api/v1/channels/{sports.id}/metrics",
        params={"start": "2026-07-23T09:30:00Z"},
    )
    assert [item["viewers"] for item in ranged.json()] == [1000]


def test_channel_metrics_not_found(client):
    """Un canal inexistente devuelve 404."""
    assert client.get("/api/v1/channels/999/metrics").status_code == 404
