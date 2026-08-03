"""Tests de los endpoints de canales y su histórico."""

from datetime import UTC, datetime

from app.models import (
    Channel,
    ChannelEvent,
    ChannelMetric,
    ChannelStatus,
    ChannelType,
    Server,
    ServerRole,
    TechnicalStream,
)


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
    assert everything["total"] == 2
    assert len(everything["items"]) == 2

    by_server = client.get("/api/v1/channels", params={"server_id": server.id}).json()
    assert [item["external_id"] for item in by_server["items"]] == ["ch-sports"]

    by_category = client.get("/api/v1/channels", params={"category": "cine"}).json()
    assert [item["external_id"] for item in by_category["items"]] == ["ch-movies"]

    enabled_only = client.get("/api/v1/channels", params={"enabled": "true"}).json()
    assert [item["external_id"] for item in enabled_only["items"]] == ["ch-sports"]

    sports = next(item for item in everything["items"] if item["external_id"] == "ch-sports")
    assert sports["latest_metric"]["viewers"] == 1000
    assert sports["current_server_name"] == "Servidor A"


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


def test_dynamic_channel_fields_and_filters_are_exposed(client, session):
    """La lista devuelve ciclo de vida, evento, stream y filtros de fuente."""
    event = ChannelEvent(
        source_id="xtream:provider-a",
        external_id="event-1",
        name="Final deportiva",
    )
    stream = TechnicalStream(
        source_id="xtream:provider-a",
        external_id="stream-1",
        name="Feed principal",
    )
    channel = Channel(
        source_id="xtream:provider-a",
        external_id="channel-1",
        name="Final temporal",
        category="sports",
        category_id="sports-1",
        channel_type=ChannelType.EVENT,
        active=False,
        enabled=False,
        event=event,
        technical_stream=stream,
    )
    session.add(channel)
    session.commit()

    response = client.get(
        "/api/v1/channels",
        params={
            "source_id": "xtream:provider-a",
            "channel_type": "event",
            "active": "false",
            "category_id": "sports-1",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    item = body["items"][0]
    assert item["channel_type"] == "event"
    assert item["active"] is False
    assert item["event_name"] == "Final deportiva"
    assert item["technical_stream_name"] == "Feed principal"
