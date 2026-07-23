"""Tests de autenticación, exclusión mutua, historial y estado del recolector."""

import threading
import time

from sqlalchemy import func, select

from app.adapters.mock import MockMonitoringAdapter
from app.collectors.runner import (
    CollectionAlreadyRunningError,
    CollectionRunner,
    get_collection_runner,
)
from app.core.config import get_settings
from app.main import app as fastapi_app
from app.models import CollectionRun, CollectionRunStatus, CollectionTrigger
from tests.conftest import FIXED_NOW, make_test_settings


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


class _ExplodingAdapter(MockMonitoringAdapter):
    """Mock que falla a mitad de la recolección."""

    def get_servers(self):  # type: ignore[override]
        raise RuntimeError("fuente rota a propósito")


def _wait_until(predicate, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


# --- Autenticación por API key -------------------------------------------------


def test_run_without_key_is_rejected(anon_client):
    """Sin cabecera X-API-Key el endpoint de recolección responde 401."""
    assert anon_client.post("/api/v1/collection/run").status_code == 401


def test_run_with_wrong_key_is_rejected(client, session):
    """Una clave incorrecta responde 401 sin ejecutar nada."""
    response = client.post("/api/v1/collection/run", headers={"X-API-Key": "clave-mala"})
    assert response.status_code == 401
    assert session.scalar(select(func.count()).select_from(CollectionRun)) == 0


def test_api_fails_closed_without_configured_key(client):
    """Sin API_KEY configurada toda la API v1 se niega a operar (503)."""
    unconfigured = make_test_settings(api_key=None)
    fastapi_app.dependency_overrides[get_settings] = lambda: unconfigured

    assert client.post("/api/v1/collection/run").status_code == 503
    assert client.get("/api/v1/servers").status_code == 503


def test_run_with_valid_key_succeeds(client):
    """La clave correcta permite ejecutar la recolección."""
    response = client.post("/api/v1/collection/run")
    assert response.status_code == 200
    assert response.json()["servers_synced"] >= 4


# --- Exclusión mutua -----------------------------------------------------------


def test_runner_rejects_concurrent_run(session_factory):
    """Dos recolecciones simultáneas: la segunda es rechazada por el lock."""
    runner = CollectionRunner()
    adapter = _BlockingAdapter()
    session = session_factory()
    check_session = session_factory()

    worker = threading.Thread(target=lambda: (runner.run(session, adapter), session.close()))
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
    last = check_session.scalars(select(CollectionRun).order_by(CollectionRun.id.desc())).first()
    check_session.close()
    assert last is not None and last.status is CollectionRunStatus.SUCCESS


def test_endpoint_returns_409_while_running(client, session_factory):
    """El endpoint responde 409 mientras el runner del proceso está ocupado."""
    runner = get_collection_runner()
    adapter = _BlockingAdapter()
    session = session_factory()

    worker = threading.Thread(target=lambda: (runner.run(session, adapter), session.close()))
    worker.start()
    try:
        assert adapter.started.wait(timeout=5)
        assert client.post("/api/v1/collection/run").status_code == 409
    finally:
        adapter.release.set()
        worker.join(timeout=10)


# --- Historial persistido ------------------------------------------------------


def test_history_persists_successful_run(client, session):
    """Una recolección exitosa queda registrada con contadores y duración."""
    assert client.post("/api/v1/collection/run").status_code == 200

    run = session.scalars(select(CollectionRun)).one()
    assert run.status is CollectionRunStatus.SUCCESS
    assert run.triggered_by is CollectionTrigger.MANUAL
    assert run.finished_at is not None
    assert run.duration_ms is not None and run.duration_ms >= 0
    assert run.servers_synced >= 4
    assert run.channels_synced >= 20
    assert run.server_metrics_inserted >= 4
    assert run.errors == []


def test_history_persists_failed_run(session_factory, session):
    """Un fallo total queda registrado con estado error y su motivo."""
    runner = CollectionRunner()
    run_session = session_factory()
    try:
        try:
            runner.run(run_session, _ExplodingAdapter(seed=42))
            raise AssertionError("la recolección debió fallar")
        except RuntimeError:
            pass
    finally:
        run_session.close()

    run = session.scalars(select(CollectionRun)).one()
    assert run.status is CollectionRunStatus.ERROR
    assert run.finished_at is not None
    assert run.errors and "fuente rota a propósito" in run.errors[0]


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


def test_status_reads_persisted_history(client):
    """Tras una recolección, el status expone la ejecución persistida."""
    assert client.post("/api/v1/collection/run").status_code == 200

    body = client.get("/api/v1/collection/status").json()

    assert body["running"] is False
    last_run = body["last_run"]
    assert last_run["status"] == "success"
    assert last_run["triggered_by"] == "manual"
    assert last_run["duration_ms"] >= 0
    assert last_run["finished_at"] >= last_run["started_at"]
    assert last_run["server_metrics_inserted"] >= 4
    assert last_run["errors"] == []


def test_status_survives_process_restart(client, session_factory):
    """El last_run proviene de la BD: sigue visible con un runner nuevo."""
    assert client.post("/api/v1/collection/run").status_code == 200
    # Simula un reinicio del proceso: el estado en memoria desaparece.
    get_collection_runner().reset()

    body = client.get("/api/v1/collection/status").json()
    assert body["last_run"] is not None
    assert body["last_run"]["status"] == "success"


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


def test_status_detects_running_row_from_other_instance(client, session_factory):
    """Una fila running fresca de otra instancia se refleja en el status."""
    runner = get_collection_runner()
    adapter = _BlockingAdapter()
    session = session_factory()

    worker = threading.Thread(target=lambda: (runner.run(session, adapter), session.close()))
    worker.start()
    try:
        assert adapter.started.wait(timeout=5)
        # Simula que la consulta llega a OTRA instancia: el runner local
        # no sabe nada, pero la fila running persistida sí se detecta.
        runner.reset()
        body = client.get("/api/v1/collection/status").json()
        assert body["running"] is True
        assert body["current_run_started_at"] is not None
    finally:
        adapter.release.set()
        worker.join(timeout=10)
