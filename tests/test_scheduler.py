"""Tests del programador periódico de recolecciones."""

import asyncio

from sqlalchemy import func, select

from app.adapters.mock import MockMonitoringAdapter
from app.collectors.runner import CollectionRunner
from app.models import ServerMetric
from app.tasks.scheduler import CollectionScheduler


def _make_scheduler(session_factory, runner, interval=0.05):
    return CollectionScheduler(
        interval_seconds=interval,
        session_factory=session_factory,
        adapter_factory=lambda: MockMonitoringAdapter(seed=42),
        runner=runner,
    )


def test_scheduler_collects_periodically(session_factory, session):
    """Con el scheduler activo se persisten métricas sin intervención manual."""
    runner = CollectionRunner()
    scheduler = _make_scheduler(session_factory, runner)

    async def scenario():
        scheduler.start()
        assert scheduler.is_active
        for _ in range(200):
            if runner.last_run is not None:
                break
            await asyncio.sleep(0.02)
        await scheduler.stop()

    asyncio.run(scenario())

    assert not scheduler.is_active
    assert scheduler.next_run_at is None
    assert runner.last_run is not None
    assert runner.last_run.success
    stored = session.scalar(select(func.count()).select_from(ServerMetric))
    assert stored >= 4


def test_scheduler_start_is_idempotent(session_factory):
    """Llamar start dos veces no crea bucles duplicados."""
    runner = CollectionRunner()
    scheduler = _make_scheduler(session_factory, runner, interval=60)

    async def scenario():
        scheduler.start()
        first_task = scheduler._task
        scheduler.start()
        assert scheduler._task is first_task
        assert scheduler.is_active
        await scheduler.stop()

    asyncio.run(scenario())
    assert not scheduler.is_active


def test_scheduler_survives_collection_failure(session_factory):
    """Un fallo en la recolección no tumba el bucle periódico."""

    class _ExplodingFactory:
        calls = 0

        def __call__(self):
            _ExplodingFactory.calls += 1
            raise RuntimeError("adaptador roto a propósito")

    runner = CollectionRunner()
    scheduler = CollectionScheduler(
        interval_seconds=0.03,
        session_factory=session_factory,
        adapter_factory=_ExplodingFactory(),
        runner=runner,
    )

    async def scenario():
        scheduler.start()
        for _ in range(200):
            if _ExplodingFactory.calls >= 2:
                break
            await asyncio.sleep(0.02)
        assert scheduler.is_active, "el bucle debe seguir vivo tras el fallo"
        await scheduler.stop()

    asyncio.run(scenario())
    assert _ExplodingFactory.calls >= 2
