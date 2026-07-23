"""Tests de la paginación por cursor en los históricos."""

from datetime import UTC, datetime, timedelta

from app.models import Channel, ChannelMetric, ChannelStatus, Server, ServerMetric, ServerRole

BASE = datetime(2026, 7, 23, 0, 0, tzinfo=UTC)


def _seed_server_history(session, samples=7) -> Server:
    server = Server(
        external_id="srv-pag",
        name="Paginado",
        role=ServerRole.LIVE,
        network_capacity_mbps=1000.0,
        enabled=True,
    )
    session.add(server)
    session.flush()
    for index in range(samples):
        session.add(
            ServerMetric(
                server_id=server.id,
                collected_at=BASE + timedelta(minutes=5 * index),
                cpu_percent=float(index),
                memory_percent=50.0,
                input_mbps=10.0,
                output_mbps=100.0,
                active_connections=10,
                active_streams=2,
                source="mock",
            )
        )
    session.commit()
    return server


def test_cursor_pages_cover_history_without_gaps(client, session):
    """Paginar con cursores recorre todo el histórico sin huecos ni repetidos."""
    server = _seed_server_history(session, samples=7)

    collected: list[float] = []
    cursor: str | None = None
    pages = 0
    while True:
        params = {"limit": 3}
        if cursor is not None:
            params["cursor"] = cursor
        response = client.get(f"/api/v1/servers/{server.id}/metrics", params=params)
        assert response.status_code == 200
        body = response.json()
        collected.extend(item["cpu_percent"] for item in body)
        pages += 1
        cursor = response.headers.get("X-Next-Cursor")
        if cursor is None:
            break

    assert pages == 3  # 3 + 3 + 1
    assert collected == [6.0, 5.0, 4.0, 3.0, 2.0, 1.0, 0.0], "orden descendente completo"


def test_last_page_has_no_next_cursor(client, session):
    """Si el histórico cabe en una página, no se emite X-Next-Cursor."""
    server = _seed_server_history(session, samples=2)

    response = client.get(f"/api/v1/servers/{server.id}/metrics", params={"limit": 10})

    assert response.status_code == 200
    assert len(response.json()) == 2
    assert "X-Next-Cursor" not in response.headers


def test_limit_only_requests_remain_compatible(client, session):
    """Los clientes que solo usan limit siguen recibiendo la lista de siempre."""
    server = _seed_server_history(session, samples=5)

    response = client.get(f"/api/v1/servers/{server.id}/metrics", params={"limit": 2})

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list) and len(body) == 2
    assert body[0]["cpu_percent"] == 4.0  # la más reciente primero


def test_invalid_cursor_is_rejected(client, session):
    """Un cursor malformado devuelve 400 sin tocar el histórico."""
    server = _seed_server_history(session, samples=2)

    response = client.get(
        f"/api/v1/servers/{server.id}/metrics", params={"cursor": "no-es-un-cursor"}
    )

    assert response.status_code == 400


def test_channel_metrics_cursor_pagination(client, session):
    """La paginación por cursor también funciona en el histórico de canales."""
    channel = Channel(external_id="ch-pag", name="Canal Paginado", enabled=True)
    session.add(channel)
    session.flush()
    for index in range(5):
        session.add(
            ChannelMetric(
                channel_id=channel.id,
                collected_at=BASE + timedelta(minutes=5 * index),
                viewers=index * 100,
                status=ChannelStatus.ONLINE,
            )
        )
    session.commit()

    first = client.get(f"/api/v1/channels/{channel.id}/metrics", params={"limit": 3})
    assert first.status_code == 200
    assert [item["viewers"] for item in first.json()] == [400, 300, 200]
    cursor = first.headers["X-Next-Cursor"]

    second = client.get(
        f"/api/v1/channels/{channel.id}/metrics", params={"limit": 3, "cursor": cursor}
    )
    assert second.status_code == 200
    assert [item["viewers"] for item in second.json()] == [100, 0]
    assert "X-Next-Cursor" not in second.headers
