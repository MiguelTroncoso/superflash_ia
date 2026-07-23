"""Tests del endpoint de resumen global."""

from datetime import UTC, datetime, timedelta

from app.models import (
    Channel,
    ChannelMetric,
    ChannelStatus,
    Server,
    ServerMetric,
    ServerRole,
)

NOW = datetime(2026, 7, 23, 12, 0, tzinfo=UTC)


def _add_server(session, external_id, name, capacity, enabled=True):
    server = Server(
        external_id=external_id,
        name=name,
        role=ServerRole.LIVE,
        network_capacity_mbps=capacity,
        enabled=enabled,
    )
    session.add(server)
    session.flush()
    return server


def _add_server_metric(session, server, collected_at, cpu, memory, output, connections):
    session.add(
        ServerMetric(
            server_id=server.id,
            collected_at=collected_at,
            cpu_percent=cpu,
            memory_percent=memory,
            input_mbps=50.0,
            output_mbps=output,
            active_connections=connections,
            active_streams=5,
            source="mock",
        )
    )


def _seed_overview_data(session):
    alpha = _add_server(session, "srv-alpha", "Alpha", 1000.0)
    beta = _add_server(session, "srv-beta", "Beta", 2000.0)
    zero_cap = _add_server(session, "srv-zero", "Zero", 0.0)

    # Muestras antiguas que NO deben usarse en el resumen.
    _add_server_metric(session, alpha, NOW - timedelta(hours=1), 90.0, 90.0, 999.0, 9999)
    # Muestras recientes (las que cuentan).
    _add_server_metric(session, alpha, NOW, 40.0, 60.0, 500.0, 1000)
    _add_server_metric(session, beta, NOW, 20.0, 40.0, 800.0, 2000)
    _add_server_metric(session, zero_cap, NOW, 10.0, 30.0, 100.0, 300)

    for index, (name, viewers) in enumerate(
        [
            ("Canal A", 500),
            ("Canal B", 900),
            ("Canal C", 100),
            ("Canal D", 700),
            ("Canal E", 300),
            ("Canal F", 50),
        ],
        start=1,
    ):
        channel = Channel(
            external_id=f"ch-{index}",
            name=name,
            category="test",
            current_server_id=alpha.id,
            enabled=True,
        )
        session.add(channel)
        session.flush()
        # Muestra antigua con audiencia inflada: no debe contar.
        session.add(
            ChannelMetric(
                channel_id=channel.id,
                server_id=alpha.id,
                collected_at=NOW - timedelta(hours=1),
                viewers=viewers * 10,
                status=ChannelStatus.ONLINE,
            )
        )
        session.add(
            ChannelMetric(
                channel_id=channel.id,
                server_id=alpha.id,
                collected_at=NOW,
                viewers=viewers,
                status=ChannelStatus.ONLINE,
            )
        )
    session.commit()


def test_overview_aggregates_latest_samples(client, session):
    """El resumen agrega solo la muestra más reciente de cada servidor."""
    _seed_overview_data(session)

    response = client.get("/api/v1/overview")
    assert response.status_code == 200
    body = response.json()

    assert body["enabled_servers"] == 3
    assert body["total_active_connections"] == 1000 + 2000 + 300
    assert body["total_output_mbps"] == 500.0 + 800.0 + 100.0
    assert body["total_input_mbps"] == 150.0
    assert body["avg_cpu_percent"] == round((40.0 + 20.0 + 10.0) / 3, 2)
    assert body["avg_memory_percent"] == round((60.0 + 40.0 + 30.0) / 3, 2)
    assert body["top_output_server"]["name"] == "Beta"
    assert body["top_output_server"]["output_mbps"] == 800.0


def test_overview_network_utilization(client, session):
    """La utilización es output/capacidad*100; capacidad 0 devuelve null."""
    _seed_overview_data(session)

    body = client.get("/api/v1/overview").json()
    utilization = {
        item["name"]: item["utilization_percent"] for item in body["server_network_utilization"]
    }

    assert utilization["Alpha"] == 50.0  # 500 / 1000 * 100
    assert utilization["Beta"] == 40.0  # 800 / 2000 * 100
    assert utilization["Zero"] is None  # capacidad 0: no calculable


def test_overview_top_channels(client, session):
    """Los cinco canales con más espectadores según la última muestra."""
    _seed_overview_data(session)

    body = client.get("/api/v1/overview").json()
    top = body["top_channels"]

    assert len(top) == 5
    assert [item["name"] for item in top] == ["Canal B", "Canal D", "Canal A", "Canal E", "Canal C"]
    assert [item["viewers"] for item in top] == [900, 700, 500, 300, 100]


def test_overview_empty_database(client):
    """Sin datos, el resumen devuelve valores neutros y listas vacías."""
    body = client.get("/api/v1/overview").json()

    assert body["enabled_servers"] == 0
    assert body["total_active_connections"] == 0
    assert body["total_output_mbps"] == 0
    assert body["avg_cpu_percent"] is None
    assert body["top_output_server"] is None
    assert body["server_network_utilization"] == []
    assert body["top_channels"] == []
