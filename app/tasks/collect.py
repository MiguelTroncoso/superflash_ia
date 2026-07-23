"""Ejecución manual de la recolección desde la línea de comandos.

Uso::

    python -m app.tasks.collect [--seed 42]

Imprime el resumen de la recolección en JSON y termina con código
distinto de cero si la recolección registró errores.
"""

import argparse
import logging
import sys

from app.adapters.factory import get_adapter
from app.adapters.mock import MockMonitoringAdapter
from app.collectors.runner import CollectionAlreadyRunningError, get_collection_runner
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.database.session import get_session_factory
from app.models.collection_run import CollectionTrigger

logger = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    """Ejecuta una recolección manual y devuelve el código de salida."""
    parser = argparse.ArgumentParser(description="Ejecuta una recolección de métricas (mock).")
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Semilla del adaptador mock (por defecto, MOCK_SEED de la configuración).",
    )
    args = parser.parse_args(argv)

    settings = get_settings()
    setup_logging(settings.log_level)

    adapter = (
        MockMonitoringAdapter(seed=args.seed) if args.seed is not None else get_adapter(settings)
    )

    session = get_session_factory()()
    try:
        result = get_collection_runner().run(
            session, adapter, triggered_by=CollectionTrigger.MANUAL
        )
    except CollectionAlreadyRunningError:
        logger.error("ya hay una recolección en curso; no se inició otra")
        return 1
    finally:
        session.close()

    print(result.model_dump_json(indent=2))
    if result.errors:
        logger.warning("recoleccion con %d errores", len(result.errors))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
