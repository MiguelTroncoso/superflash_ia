"""Tests de autenticación, exclusión mutua, historial y estado del recolector."""

import threading
import time
from datetime import UTC, datetime, timedelta

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
    """Sin ejecuciones previas: contrato plano con valores neutros."""
    body = client.get("/api/v1/collection/status").json()

    assert body["running"] is False
    assert body["run_id"] is None
    assert body["source"] is None
    assert body["triggered_by"] is None
    assert body["started_at"] is None
    assert body["heartbeat_at"] is None
    assert body["finished_at"] is None
    assert body["duration_ms"] is None
    assert body["status"] is None
    assert body["inserted"] == 0
    assert body["skipped"] == 0
    assert body["errors"] == []
    assert body["next_run_at"] is None


def test_status_reads_persisted_history(client):
    """Tras una recolección, el status expone la ejecución persistida."""
    assert client.post("/api/v1/collection/run").status_code == 200

    body = client.get("/api/v1/collection/status").json()

    assert body["running"] is False
    assert body["run_id"] is not None
    assert body["source"] == "mock"
    assert body["status"] == "success"
    assert body["triggered_by"] == "manual"
    assert body["duration_ms"] >= 0
    assert body["finished_at"] >= body["started_at"]
    assert body["heartbeat_at"] is not None
    assert body["inserted"] >= 24  # 5 servidores + 24 canales como mínimo
    assert body["skipped"] == 0
    assert body["errors"] == []


def test_status_survives_process_restart(client, session_factory):
    """El estado proviene de la BD: sigue visible con un runner nuevo."""
    assert client.post("/api/v1/collection/run").status_code == 200
    # Simula un reinicio del proceso: el estado en memoria desaparece.
    get_collection_runner().reset()

    body = client.get("/api/v1/collection/status").json()
    assert body["status"] == "success"
    assert body["run_id"] is not None


def test_status_while_running(client, session_factory):
    """Durante una recolección el status describe la ejecución en curso."""
    runner = get_collection_runner()
    adapter = _BlockingAdapter()
    session = session_factory()

    worker = threading.Thread(target=lambda: (runner.run(session, adapter), session.close()))
    worker.start()
    try:
        assert adapter.started.wait(timeout=5)
        body = client.get("/api/v1/collection/status").json()
        assert body["running"] is True
        assert body["status"] == "running"
        assert body["started_at"] is not None
        assert body["heartbeat_at"] is not None
        assert body["finished_at"] is None
    finally:
        adapter.release.set()
        worker.join(timeout=10)

    assert _wait_until(lambda: not get_collection_runner().is_running)


def test_status_detects_running_row_from_other_instance(client, session_factory):
    """Una fila running con heartbeat vigente se refleja en el status."""
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
        assert body["status"] == "running"
    finally:
        adapter.release.set()
        worker.join(timeout=10)


# --- Heartbeat y ejecuciones abandonadas ---------------------------------------


def _seed_stale_running_row(session, heartbeat_age_seconds):
    """Inserta una fila running con heartbeat de otra época (proceso caído)."""
    stale_at = datetime.now(UTC) - timedelta(seconds=heartbeat_age_seconds)
    run = CollectionRun(
        started_at=stale_at,
        heartbeat_at=stale_at,
        source="mock",
        status=CollectionRunStatus.RUNNING,
        triggered_by=CollectionTrigger.MANUAL,
        errors=[],
    )
    session.add(run)
    session.commit()
    return run


def test_heartbeat_is_persisted_during_run(client, session):
    """Una ejecución terminada deja heartbeat al menos tan nuevo como su inicio."""
    assert client.post("/api/v1/collection/run").status_code == 200

    run = session.scalars(select(CollectionRun)).one()
    assert run.heartbeat_at is not None
    assert run.heartbeat_at >= run.started_at
    assert run.heartbeat_at == run.finished_at


def test_status_ignores_abandoned_running_row(client, session):
    """Una fila running con heartbeat vencido NO se reporta como en curso."""
    # Heartbeat de hace una hora: supera el timeout por defecto (600 s).
    _seed_stale_running_row(session, heartbeat_age_seconds=3600)

    body = client.get("/api/v1/collection/status").json()

    assert body["running"] is False
    assert body["status"] is None, "sin ejecuciones terminadas no hay nada que mostrar"


def test_status_respects_fresh_heartbeat(client, session):
    """Una fila running con heartbeat reciente sí cuenta como en curso."""
    _seed_stale_running_row(session, heartbeat_age_seconds=5)

    body = client.get("/api/v1/collection/status").json()

    assert body["running"] is True
    assert body["status"] == "running"


def test_new_run_marks_abandoned_rows_as_error(client, session):
    """Al iniciar una recolección, las filas huérfanas pasan a error."""
    stale = _seed_stale_running_row(session, heartbeat_age_seconds=3600)

    assert client.post("/api/v1/collection/run").status_code == 200

    session.expire_all()
    abandoned = session.get(CollectionRun, stale.id)
    assert abandoned is not None
    assert abandoned.status is CollectionRunStatus.ERROR
    assert "abandonada" in abandoned.errors[0]
    # Libera la transacción de lectura antes de reutilizar la conexión
    # SQLite compartida en el cliente HTTP.
    session.rollback()
    # Y la nueva ejecución quedó registrada como exitosa.
    body = client.get("/api/v1/collection/status").json()
    assert body["status"] == "success"
