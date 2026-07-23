"""Diagnóstico de fuentes de monitoreo, sin tocar la base de datos.

Uso::

    python -m app.tasks.diagnose_source [--source infrastructure|streaming|all]

Valida la configuración, instancia las fuentes configuradas y muestra
qué datos podría obtener cada una (inventario y una muestra de métricas
en memoria). Garantías:

- NO escribe métricas ni inventario en la base de datos (nunca abre una
  conexión ni crea el motor de SQLAlchemy).
- Con las fuentes ``mock`` NO realiza ninguna conexión externa.

Códigos de salida: 0 = diagnóstico correcto; 2 = configuración inválida.
"""

import argparse
import sys
from typing import Literal

from pydantic import BaseModel

from app.adapters.factory import get_infrastructure_adapter, get_streaming_adapter
from app.core.config import Settings, get_settings

_SourceChoice = Literal["infrastructure", "streaming", "all"]


def _print_header(settings: Settings, source: _SourceChoice) -> None:
    print("=== Diagnóstico de fuentes de monitoreo ===")
    print(f"entorno: {settings.app_env} | version: {settings.app_version}")
    print(
        f"configuración: MONITORING_ADAPTER={settings.monitoring_adapter} | "
        f"INFRASTRUCTURE_SOURCE={settings.infrastructure_source} | "
        f"STREAMING_SOURCE={settings.streaming_source} | MOCK_SEED={settings.mock_seed}"
    )
    print(f"diagnóstico solicitado: {source}")
    print()


def _fields_of(model: BaseModel) -> str:
    """Lista los campos disponibles de un snapshot con su valor de ejemplo."""
    lines = []
    for name, value in model.model_dump().items():
        lines.append(f"    {name} = {value}")
    return "\n".join(lines)


def _diagnose_infrastructure(settings: Settings) -> None:
    adapter = get_infrastructure_adapter(settings)
    servers = adapter.get_servers()
    metrics = adapter.get_infrastructure_metrics()
    print(f"--- Fuente de infraestructura: {adapter.source_name}")
    print(f"  servidores visibles: {len(servers)}")
    for server in servers:
        print(
            f"    {server.external_id} rol={server.role.value} "
            f"capacidad={server.network_capacity_mbps} Mbps"
        )
    print(f"  muestras de métricas disponibles: {len(metrics)}")
    if metrics:
        print("  campos de una muestra (ejemplo):")
        print(_fields_of(metrics[0]))
    print()


def _diagnose_streaming(settings: Settings) -> None:
    adapter = get_streaming_adapter(settings)
    channels = adapter.get_channels()
    metrics = adapter.get_streaming_metrics()
    print(f"--- Fuente de streaming: {adapter.source_name}")
    print(f"  canales visibles: {len(channels)}")
    print(f"  muestras de métricas disponibles: {len(metrics)}")
    if metrics:
        top = max(metrics, key=lambda metric: metric.viewers)
        print(f"  canal con más espectadores en la muestra: {top.channel_external_id}")
        print("  campos de una muestra (ejemplo):")
        print(_fields_of(metrics[0]))
    print()


def main(argv: list[str] | None = None) -> int:
    """Ejecuta el diagnóstico y devuelve el código de salida."""
    parser = argparse.ArgumentParser(
        description="Valida la configuración y muestra qué datos entregaría cada fuente."
    )
    parser.add_argument(
        "--source",
        choices=("infrastructure", "streaming", "all"),
        default="all",
        help="Fuente a diagnosticar (por defecto: all).",
    )
    args = parser.parse_args(argv)
    source: _SourceChoice = args.source

    settings = get_settings()
    _print_header(settings, source)

    try:
        if source in ("infrastructure", "all"):
            _diagnose_infrastructure(settings)
        if source in ("streaming", "all"):
            _diagnose_streaming(settings)
    except ValueError as error:
        print(f"CONFIGURACIÓN INVÁLIDA: {error}", file=sys.stderr)
        return 2

    print("Diagnóstico completado.")
    print("No se escribió nada en la base de datos.")
    print("No se realizó ninguna conexión externa (fuentes mock).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
