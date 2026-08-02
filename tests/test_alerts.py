"""Tests de las alertas internas de solo lectura."""

from datetime import UTC, datetime, timedelta

from app.models import Server, ServerMetric, ServerRole

NOW = datetime.now(UTC)


def _add_server(session, external_id, name, capacity=1000.0):
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


def _add_metric(
    session,
    server,
    collected_at=None,
    cpu=20.0,
    memory=30.0,
    disk=None,
    output=100.0,
):
    session.add(
        ServerMetric(
            server_id=server.id,
            collected_at=collected_at or NOW,
            cpu_percent=cpu,
            memory_percent=memory,
            disk_percent=disk,
            input_mbps=10.0,
            output_mbps=output,
            active_connections=10,
            active_streams=2,
            source="mock",
        )
    )


def _alerts_by_type(client):
    response = client.get("/api/v1/alerts")
    assert response.status_code == 200
    body = response.json()
    assert "generated_at" in body
    grouped: dict[str, list[dict]] = {}
    for alert in body["alerts"]:
        grouped.setdefault(alert["type"], []).append(alert)
    return grouped


def test_healthy_infrastructure_has_no_alerts(client, session):
    """Con métricas recientes y sanas no hay ninguna alerta."""
    server = _add_server(session, "srv-ok", "Sano")
    _add_metric(session, server, cpu=20.0, memory=30.0, disk=40.0, output=100.0)
    session.commit()

    assert _alerts_by_type(client) == {}


def test_threshold_alerts_for_cpu_memory_disk_network(client, session):
    """CPU, RAM, disco y red por encima del umbral generan sus alertas."""
    server = _add_server(session, "srv-hot", "Caliente", capacity=1000.0)
    # Umbrales por defecto: cpu 90, memoria 90, disco 90, red 85%.
    _add_metric(session, server, cpu=95.0, memory=97.5, disk=91.0, output=900.0)
    session.commit()

    alerts = _alerts_by_type(client)

    assert alerts["high_cpu"][0]["value"] == 95.0
    assert alerts["high_cpu"][0]["threshold"] == 90.0
    assert alerts["high_memory"][0]["value"] == 97.5
    assert alerts["high_disk"][0]["value"] == 91.0
    assert alerts["high_network_utilization"][0]["value"] == 90.0  # 900/1000*100
    assert alerts["high_network_utilization"][0]["server_name"] == "Caliente"


def test_alerts_are_persisted_and_can_be_acknowledged(client, session):
    """Las alertas conservan identidad y estado acknowledged entre lecturas."""
    server = _add_server(session, "srv-persisted", "Persistente", capacity=1000.0)
    _add_metric(session, server, cpu=96.0, memory=30.0, disk=40.0, output=100.0)
    session.commit()

    first = client.get("/api/v1/alerts").json()["alerts"]
    cpu_alert = next(item for item in first if item["type"] == "high_cpu")
    acknowledged = client.patch(
        f"/api/v1/alerts/{cpu_alert['id']}", json={"status": "acknowledged"}
    )
    assert acknowledged.status_code == 200
    assert acknowledged.json()["status"] == "acknowledged"

    second = client.get("/api/v1/alerts").json()["alerts"]
    same_alert = next(item for item in second if item["type"] == "high_cpu")
    assert same_alert["id"] == cpu_alert["id"]
    assert same_alert["status"] == "acknowledged"


def test_stale_server_alert(client, session):
    """Un servidor sin muestra reciente genera alerta de obsolescencia."""
    stale = _add_server(session, "srv-stale", "Obsoleto")
    _add_metric(session, stale, collected_at=NOW - timedelta(hours=2))
    never = _add_server(session, "srv-never", "Sin muestras")
    session.commit()

    alerts = _alerts_by_type(client)

    stale_alerts = {alert["server_name"]: alert for alert in alerts["stale_server"]}
    assert "Obsoleto" in stale_alerts
    assert stale_alerts["Obsoleto"]["value"] >= 115  # minutos
    assert stale_alerts["Obsoleto"]["threshold"] == 15.0
    assert "Sin muestras" in stale_alerts
    assert stale_alerts["Sin muestras"]["value"] is None
    assert never.id == stale_alerts["Sin muestras"]["server_id"]


def test_missing_data_never_alerts(client, session):
    """Disco desconocido o capacidad de red 0 no generan falsas alertas."""
    server = _add_server(session, "srv-nodata", "Sin datos", capacity=0.0)
    _add_metric(session, server, cpu=50.0, memory=50.0, disk=None, output=99999.0)
    session.commit()

    alerts = _alerts_by_type(client)

    assert "high_disk" not in alerts
    assert "high_network_utilization" not in alerts


def test_alerts_endpoint_requires_api_key(anon_client):
    """El endpoint de alertas exige la clave como el resto de /api/v1."""
    assert anon_client.get("/api/v1/alerts").status_code == 401
