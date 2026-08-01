"""Tests de balance y recomendaciones de infraestructura."""

from datetime import UTC, datetime

from app.models import Server, ServerMetric, ServerRole


def _server(session, external_id: str, name: str, capacity: float = 1000.0) -> Server:
    server = Server(
        external_id=external_id,
        name=name,
        role=ServerRole.LIVE,
        network_capacity_mbps=capacity,
        enabled=True,
    )
    session.add(server)
    session.flush()
    return server


def _metric(
    session,
    server: Server,
    *,
    cpu: float,
    memory: float,
    disk: float,
    output: float,
) -> None:
    session.add(
        ServerMetric(
            server_id=server.id,
            collected_at=datetime.now(UTC),
            cpu_percent=cpu,
            memory_percent=memory,
            disk_percent=disk,
            input_mbps=10,
            output_mbps=output,
            active_connections=10,
            active_streams=2,
            source="mock",
        )
    )


def test_balance_exposes_capacity_and_extreme_servers(client, session):
    """El balance calcula promedios, capacidad y extremos de red."""
    busy = _server(session, "srv-busy", "Busy", capacity=1000)
    quiet = _server(session, "srv-quiet", "Quiet", capacity=1000)
    _metric(session, busy, cpu=80, memory=60, disk=70, output=800)
    _metric(session, quiet, cpu=20, memory=40, disk=30, output=100)
    session.commit()

    response = client.get("/api/v1/balance")

    assert response.status_code == 200
    body = response.json()
    assert body["server_count"] == 2
    assert body["sampled_server_count"] == 2
    assert body["average_cpu_percent"] == 50.0
    assert body["capacity_total_mbps"] == 2000.0
    assert body["capacity_used_mbps"] == 900.0
    assert body["capacity_free_mbps"] == 1100.0
    assert body["most_loaded"]["name"] == "Busy"
    assert body["least_utilized"]["name"] == "Quiet"


def test_recommendations_apply_rules_without_writes(client, session):
    """Las reglas cubren saturación, falta de datos e infrautilización."""
    hot = _server(session, "srv-hot-rules", "Hot rules")
    quiet = _server(session, "srv-quiet-rules", "Quiet rules")
    _server(session, "srv-no-data", "No data")
    _metric(session, hot, cpu=96, memory=95, disk=94, output=950)
    _metric(session, quiet, cpu=10, memory=20, disk=20, output=20)
    session.commit()

    response = client.get("/api/v1/recommendations")

    assert response.status_code == 200
    recommendations = response.json()["recommendations"]
    hot_types = {item["type"] for item in recommendations if item["server_name"] == "Hot rules"}
    assert {"high_cpu", "high_memory", "high_disk", "high_network"} <= hot_types
    assert any(item["type"] == "no_data" for item in recommendations)
    assert any(item["type"] == "underutilized" for item in recommendations)
    assert all(
        item["server_name"] != "No data" or item["type"] == "no_data" for item in recommendations
    )
