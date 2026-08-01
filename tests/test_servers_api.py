"""Tests de los endpoints de servidores y su histórico."""

from datetime import UTC, datetime

from app.models import Server, ServerMetric, ServerRole


def _seed_server_with_metrics(session) -> Server:
    server = Server(
        external_id="srv-hist",
        name="Histórico 01",
        hostname="hist01.example.internal",
        role=ServerRole.LIVE,
        network_capacity_mbps=1000.0,
        enabled=True,
    )
    session.add(server)
    session.flush()
    for hour in (8, 9, 10, 11):
        session.add(
            ServerMetric(
                server_id=server.id,
                collected_at=datetime(2026, 7, 23, hour, 0, tzinfo=UTC),
                cpu_percent=10.0 * hour,
                memory_percent=30.0,
                input_mbps=20.0,
                output_mbps=100.0 + hour,
                active_connections=500,
                active_streams=10,
                uptime_seconds=86_400,
                source="mock",
            )
        )
    session.commit()
    return server


def test_list_and_get_server(client, session):
    """Los servidores registrados se pueden listar y consultar."""
    server = _seed_server_with_metrics(session)

    listed = client.get("/api/v1/servers")
    assert listed.status_code == 200
    assert [item["external_id"] for item in listed.json()] == ["srv-hist"]

    detail = client.get(f"/api/v1/servers/{server.id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["name"] == "Histórico 01"
    assert body["role"] == "live"
    assert body["network_capacity_mbps"] == 1000.0
    assert "prometheus_url" not in body
    assert "prometheus_token" not in body


def test_get_server_not_found(client):
    """Un id inexistente devuelve 404."""
    assert client.get("/api/v1/servers/999").status_code == 404
    assert client.get("/api/v1/servers/999/metrics").status_code == 404


def test_server_metrics_date_range(client, session):
    """El histórico respeta el rango start/end y el orden descendente."""
    server = _seed_server_with_metrics(session)

    response = client.get(
        f"/api/v1/servers/{server.id}/metrics",
        params={"start": "2026-07-23T09:00:00Z", "end": "2026-07-23T10:30:00Z"},
    )

    assert response.status_code == 200
    hours = [
        datetime.fromisoformat(item["collected_at"]).replace(tzinfo=None).hour
        for item in response.json()
    ]
    assert hours == [10, 9], "solo las muestras dentro del rango, descendentes"


def test_server_metrics_limit(client, session):
    """El parámetro limit acota el número de muestras devueltas."""
    server = _seed_server_with_metrics(session)

    response = client.get(f"/api/v1/servers/{server.id}/metrics", params={"limit": 2})

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    # Sin rango, devuelve las más recientes primero.
    assert datetime.fromisoformat(body[0]["collected_at"]).hour == 11

    invalid = client.get(f"/api/v1/servers/{server.id}/metrics", params={"limit": 0})
    assert invalid.status_code == 422


def test_server_inventory_crud_does_not_return_prometheus_token(client):
    """El inventario admite CRUD completo y nunca devuelve el token."""
    payload = {
        "external_id": "srv-crud",
        "name": "Servidor administrado",
        "hostname": "crud.example.internal",
        "role": "live",
        "provider": "Acme Cloud",
        "datacenter": "SCL-1",
        "group": "live",
        "tags": ["production", "edge"],
        "type": "bare-metal",
        "country": "cl",
        "network_speed_mbps": 1000,
        "prometheus_url": "https://prometheus.internal",
        "prometheus_token": "super-secret-token",
        "heartbeat_interval_seconds": 120,
        "status": "online",
        "notes": "Servidor de prueba",
    }

    created = client.post("/api/v1/servers", json=payload)
    assert created.status_code == 201
    body = created.json()
    server_id = body["id"]
    assert body["country"] == "CL"
    assert body["network_speed_mbps"] == 1000.0
    assert body["prometheus_configured"] is True
    assert "prometheus_url" not in body
    assert "prometheus_token" not in body

    updated = client.patch(
        f"/api/v1/servers/{server_id}",
        json={"name": "Servidor actualizado", "status": "degraded"},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Servidor actualizado"
    assert updated.json()["status"] == "degraded"

    listed = client.get("/api/v1/servers")
    assert listed.status_code == 200
    assert any(item["id"] == server_id for item in listed.json())

    deleted = client.delete(f"/api/v1/servers/{server_id}")
    assert deleted.status_code == 204
    assert client.get(f"/api/v1/servers/{server_id}").status_code == 404


def test_server_inventory_rejects_duplicate_external_id(client):
    """El identificador externo mantiene la unicidad del inventario."""
    payload = {"external_id": "srv-duplicate", "name": "Uno"}
    assert client.post("/api/v1/servers", json=payload).status_code == 201
    duplicate = client.post("/api/v1/servers", json=payload)
    assert duplicate.status_code == 409
