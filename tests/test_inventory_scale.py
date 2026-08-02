"""Pruebas de escala realista para los listados agregados."""

from datetime import UTC, datetime, timedelta
from time import perf_counter

from sqlalchemy import event

from app.models import (
    Alert,
    AlertSeverity,
    AlertStatus,
    Channel,
    ChannelMetric,
    ChannelStatus,
    Server,
    ServerMetric,
    ServerRole,
)


def _seed_scale_inventory(session) -> None:
    servers = [
        Server(
            external_id=f"scale-srv-{index:02d}",
            name=f"Scale Server {index:02d}",
            role=ServerRole.LIVE,
            provider="Scale Provider",
            group="edge",
            country="CL",
            network_capacity_mbps=10_000,
            enabled=True,
        )
        for index in range(12)
    ]
    session.add_all(servers)
    session.flush()
    collected_at = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)
    session.add_all(
        [
            ServerMetric(
                server_id=server.id,
                collected_at=collected_at,
                cpu_percent=float(index),
                memory_percent=40.0,
                input_mbps=100.0,
                output_mbps=200.0 + index,
                active_connections=10,
                active_streams=2,
                source="mock",
            )
            for index, server in enumerate(servers)
        ]
    )
    session.add(
        Alert(
            fingerprint=f"{servers[0].id}:high_cpu",
            type="high_cpu",
            severity=AlertSeverity.WARNING,
            status=AlertStatus.ACTIVE,
            server_id=servers[0].id,
            server_name=servers[0].name,
            message="CPU alta",
        )
    )

    channels = [
        Channel(
            external_id=f"scale-channel-{index:05d}",
            name=f"Scale Channel {index:05d}",
            category="sports" if index % 2 == 0 else "news",
            current_server_id=servers[index % len(servers)].id,
            enabled=index % 10 != 0,
        )
        for index in range(5_000)
    ]
    session.add_all(channels)
    session.flush()
    session.add_all(
        [
            ChannelMetric(
                channel_id=channel.id,
                server_id=channel.current_server_id,
                collected_at=collected_at - timedelta(minutes=5),
                viewers=index,
                bitrate_mbps=4.0,
                estimated_output_mbps=5.0,
                status=ChannelStatus.ONLINE,
            )
            for index, channel in enumerate(channels)
        ]
    )
    session.commit()


def _count_sql(session, callback):
    statements: list[str] = []

    def before_cursor_execute(*args):
        statements.append(args[2])

    event.listen(session.bind, "before_cursor_execute", before_cursor_execute)
    try:
        result = callback()
    finally:
        event.remove(session.bind, "before_cursor_execute", before_cursor_execute)
    select_statements = [
        statement for statement in statements if statement.lstrip().upper().startswith("SELECT")
    ]
    return result, select_statements


def test_servers_page_aggregates_12_servers_without_n_plus_one(client, session):
    """La tabla de servidores usa una página y una consulta agregada."""
    _seed_scale_inventory(session)

    started = perf_counter()
    response, statements = _count_sql(
        session,
        lambda: client.get(
            "/api/v1/servers",
            params={
                "page": 1,
                "page_size": 50,
                "sort_by": "cpu",
                "sort_order": "desc",
                "search": "Scale",
            },
        ),
    )
    elapsed = perf_counter() - started

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 12
    assert body["page"] == 1
    assert body["page_size"] == 50
    assert body["total_pages"] == 1
    assert len(body["items"]) == 12
    assert body["items"][0]["latest_metric"]["cpu_percent"] == 11.0
    assert body["items"][0]["active_alert_count"] == 0
    assert body["items"][-1]["active_alert_count"] == 1
    assert len(statements) == 2, statements
    assert elapsed < 5.0


def test_channels_page_handles_5000_rows_with_filters_and_sorting(client, session):
    """El listado de canales no trae las 5.000 filas al navegador."""
    _seed_scale_inventory(session)

    started = perf_counter()
    response, statements = _count_sql(
        session,
        lambda: client.get(
            "/api/v1/channels",
            params={
                "page": 2,
                "page_size": 50,
                "category": "sports",
                "enabled": "true",
                "sort_by": "viewers",
                "sort_order": "desc",
            },
        ),
    )
    elapsed = perf_counter() - started

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2_000
    assert body["page"] == 2
    assert body["page_size"] == 50
    assert body["total_pages"] == 40
    assert len(body["items"]) == 50
    assert body["items"][0]["latest_metric"] is not None
    assert body["items"][0]["viewers"] > body["items"][-1]["viewers"]
    assert len(statements) == 2, statements
    assert elapsed < 5.0


def test_inventory_page_size_is_bounded(client):
    """El contrato rechaza páginas mayores al límite seguro."""
    assert client.get("/api/v1/servers", params={"page_size": 201}).status_code == 422
    assert client.get("/api/v1/channels", params={"page": 0}).status_code == 422
