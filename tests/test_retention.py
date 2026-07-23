"""Tests de la política de retención y su comando manual."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

import app.tasks.prune_metrics as prune_metrics_task
from app.models import (
    Channel,
    ChannelMetric,
    ChannelStatus,
    CollectionRun,
    CollectionRunStatus,
    CollectionTrigger,
    Server,
    ServerMetric,
    ServerRole,
)
from app.services.retention_service import prune_history
from tests.conftest import make_test_settings

NOW = datetime.now(UTC)


def _seed_history(session):
    server = Server(
        external_id="srv-ret",
        name="Retención",
        role=ServerRole.LIVE,
        network_capacity_mbps=1000.0,
        enabled=True,
    )
    channel = Channel(external_id="ch-ret", name="Canal Retención", enabled=True)
    session.add_all([server, channel])
    session.flush()
    for age_days in (100, 50, 1):
        collected = NOW - timedelta(days=age_days)
        session.add(
            ServerMetric(
                server_id=server.id,
                collected_at=collected,
                cpu_percent=10.0,
                memory_percent=20.0,
                input_mbps=1.0,
                output_mbps=2.0,
                active_connections=1,
                active_streams=1,
                source="mock",
            )
        )
        session.add(
            ChannelMetric(
                channel_id=channel.id,
                collected_at=collected,
                viewers=10,
                status=ChannelStatus.ONLINE,
            )
        )
        session.add(
            CollectionRun(
                started_at=collected,
                finished_at=collected,
                duration_ms=10,
                source="mock",
                status=CollectionRunStatus.SUCCESS,
                triggered_by=CollectionTrigger.MANUAL,
                errors=[],
            )
        )
    session.commit()


def _counts(session):
    return (
        session.scalar(select(func.count()).select_from(ServerMetric)),
        session.scalar(select(func.count()).select_from(ChannelMetric)),
        session.scalar(select(func.count()).select_from(CollectionRun)),
    )


def test_prune_deletes_only_older_than_cutoff(session):
    """Con retención de 30 días se borran solo las muestras antiguas."""
    _seed_history(session)

    result = prune_history(session, retention_days=30)

    assert result.server_metrics_deleted == 2
    assert result.channel_metrics_deleted == 2
    assert result.collection_runs_deleted == 2
    assert _counts(session) == (1, 1, 1), "las muestras recientes permanecen"


def test_prune_dry_run_deletes_nothing(session):
    """El modo dry-run cuenta lo que borraría sin tocar nada."""
    _seed_history(session)

    result = prune_history(session, retention_days=30, dry_run=True)

    assert result.dry_run is True
    assert result.server_metrics_deleted == 2
    assert _counts(session) == (3, 3, 3), "dry-run no borra"


def test_prune_command_refuses_without_configuration(monkeypatch, session, capsys):
    """Sin METRICS_RETENTION_DAYS el comando no borra nada y sale con 2."""
    _seed_history(session)
    monkeypatch.setattr(
        prune_metrics_task, "get_settings", lambda: make_test_settings(metrics_retention_days=None)
    )

    exit_code = prune_metrics_task.main([])

    assert exit_code == 2
    assert "RETENCIÓN DESHABILITADA" in capsys.readouterr().err
    assert _counts(session) == (3, 3, 3), "nada borrado sin configuración explícita"


def test_prune_command_with_configuration(monkeypatch, session, session_factory, capsys):
    """Configurado, el comando borra el histórico antiguo y reporta contadores."""
    _seed_history(session)
    monkeypatch.setattr(
        prune_metrics_task, "get_settings", lambda: make_test_settings(metrics_retention_days=30)
    )
    monkeypatch.setattr(prune_metrics_task, "get_session_factory", lambda: session_factory)

    exit_code = prune_metrics_task.main([])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "métricas de servidores borradas: 2" in output
    session.expire_all()
    assert _counts(session) == (1, 1, 1)
