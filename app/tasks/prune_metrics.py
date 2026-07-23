"""Limpieza manual del histórico según la política de retención.

Uso::

    python -m app.tasks.prune_metrics [--dry-run]

Requiere ``METRICS_RETENTION_DAYS`` configurado en el entorno: sin esa
variable el comando se niega a borrar nada y termina con código 2. La
limpieza solo afecta a la base de datos propia de la plataforma
(métricas de servidores y canales, y ejecuciones de recolección más
antiguas que el corte); jamás toca infraestructura externa.
"""

import argparse
import sys

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.database.session import get_session_factory
from app.services.retention_service import prune_history


def main(argv: list[str] | None = None) -> int:
    """Ejecuta la limpieza (o su simulación) y devuelve el código de salida."""
    parser = argparse.ArgumentParser(
        description="Elimina el histórico anterior a METRICS_RETENTION_DAYS días."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Solo muestra cuántas filas se borrarían, sin borrar nada.",
    )
    args = parser.parse_args(argv)

    settings = get_settings()
    setup_logging(settings.log_level)

    if settings.metrics_retention_days is None:
        print(
            "RETENCIÓN DESHABILITADA: define METRICS_RETENTION_DAYS para habilitar "
            "la limpieza. No se borró nada.",
            file=sys.stderr,
        )
        return 2

    session = get_session_factory()()
    try:
        result = prune_history(
            session, retention_days=settings.metrics_retention_days, dry_run=args.dry_run
        )
    finally:
        session.close()

    action = "se borrarían" if result.dry_run else "borradas"
    print(f"corte: {result.cutoff.isoformat()} (retención {settings.metrics_retention_days} días)")
    print(f"métricas de servidores {action}: {result.server_metrics_deleted}")
    print(f"métricas de canales {action}: {result.channel_metrics_deleted}")
    print(f"ejecuciones de recolección {action}: {result.collection_runs_deleted}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
