"""Tests de autenticación, exclusión mutua y estado del recolector."""

import threading
import time

from app.adapters.mock import MockMonitoringAdapter
from app.collectors.runner import (
    CollectionAlreadyRunningError,
    CollectionRunner,
    get_collection_runner,
)
from app.core.config import get_settings
from app.main import app as fastapi_app
from tests.conftest import FIXED_NOW, TEST_API_KEY, make_test_settings


class _BlockingAdapter(MockMonitoringAdapter):
    """Mock cuyo inventario se bloquea hasta que el test lo libere."""

    def __init__(self) -> None:
        super().__init__(seed=42, now_fn=lambda: FIXED_NOW)
        self.release = threading.Event()
        self.started = threading.Event()

    def get_servers(self):  # type: ignore[override]
        self.started.set()
        assert self.release.wait(timeout=5), "el test nunca liberó el adaptador"
        return super().get_servers()


def _wait_until(predicate, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


# --- Autenticación por API key -------------------------------------------------


def test_run_without_key_is_rejected(client):
    """Sin cabecera X-API-Key el endpoint interno responde 401."""
    response = client.post("/api/v1/collection/run")
    assert response.status_code == 401


def test_run_with_wrong_key_is_rejected(client):
    """Una clave incorrecta responde 401 sin ejecutar nada."""
    response = client.post("/api/v1/collection/run", headers={"X-API-Key": "clave-mala"})
    assert response.status_code == 401
    assert client.get("/api/v1/servers").json() == []


def test_run_fails_closed_without_configured_key(client):
    """Sin COLLECTION_API_KEY configurada el endpoint se niega a operar (503)."""
    unconfigured = make_test_settings(collection_api_key=None)
    fastapi_app.dependency_overrides[get_settings] = lambda: unconfigured

    response = client.post("/api/v1/collection/run", headers={"X-API-Key": TEST_API_KEY})
    assert response.status_code == 503


def test_run_with_valid_key_succeeds(client):
    """La clave correcta permite ejecutar la recolección."""
    response = client.post("/api/v1/collection/run", headers={"X-API-Key": TEST_API_KEY})
    assert response.status_code == 200
    assert response.json()["servers_synced"] >= 4


# --- Exclusión mutua -----------------------------------------------------------


def test_runner_rejects_concurrent_run(session_factory):
    """Dos recolecciones simultáneas: la segunda es rechazada por el lock."""
    runner = CollectionRunner()
    adapter = _BlockingAdapter()
    session = session_factory()
    outcome: dict[str, object] = {}

    def _blocked_run():
        try:
            outcome["result"] = runner.run(session, adapter)
        finally:
            session.close()

    worker = threading.Thread(target=_blocked_run)
    worker.start()
    try:
        assert adapter.started.wait(timeout=5)
        assert runner.is_running

        other_session = session_factory()
        try:
            try:
                runner.run(other_session, MockMonitoringAdapter(seed=42))
                raise AssertionError("la segunda recolección debió ser rechazada")
            except CollectionAlreadyRunningError:
                pass
        finally:
            other_session.close()
    finally:
        adapter.release.set()
        worker.join(timeout=10)

    assert not runner.is_running
    assert runner.last_run is not None and runner.last_run.success


def test_endpoint_returns_409_while_running(client, session_factory):
    """El endpoint responde 409 mientras el runner del proceso está ocupado."""
    runner = get_collection_runner()
    adapter = _BlockingAdapter()
    session = session_factory()

    worker = threading.Thread(target=lambda: (runner.run(session, adapter), session.close()))
    worker.start()
    try:
        assert adapter.started.wait(timeout=5)
        response = client.post("/api/v1/collection/run", headers={"X-API-Key": TEST_API_KEY})
        assert response.status_code == 409
    finally:
        adapter.release.set()
        worker.join(timeout=10)


# --- Estado --------------------------------------------------------------------


def test_status_initial(client):
    """Sin ejecuciones previas: nada corriendo, sin last_run, scheduler apagado."""
    body = client.get("/api/v1/collection/status").json()

    assert body["running"] is False
    assert body["current_run_started_at"] is None
    assert body["last_run"] is None
    assert body["scheduler"]["enabled"] is False
    assert body["scheduler"]["next_run_at"] is None
    assert body["scheduler"]["interval_seconds"] == 300


def test_status_after_successful_run(client):
    """Tras una recolección, el status refleja duración y resultado."""
    assert (
        client.post("/api/v1/collection/run", headers={"X-API-Key": TEST_API_KEY}).status_code
        == 200
    )

    body = client.get("/api/v1/collection/status").json()

    assert body["running"] is False
    last_run = body["last_run"]
    assert last_run["success"] is True
    assert last_run["error"] is None
    assert last_run["duration_seconds"] >= 0
    assert last_run["finished_at"] >= last_run["started_at"]
    assert last_run["result"]["servers_synced"] >= 4


def test_status_while_running(client, session_factory):
    """Durante una recolección el status marca running y su inicio."""
    runner = get_collection_runner()
    adapter = _BlockingAdapter()
    session = session_factory()

    worker = threading.Thread(target=lambda: (runner.run(session, adapter), session.close()))
    worker.start()
    try:
        assert adapter.started.wait(timeout=5)
        body = client.get("/api/v1/collection/status").json()
        assert body["running"] is True
        assert body["current_run_started_at"] is not None
    finally:
        adapter.release.set()
        worker.join(timeout=10)

    assert _wait_until(lambda: not get_collection_runner().is_running)
