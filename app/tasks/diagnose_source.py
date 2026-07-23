"""Diagnóstico de fuentes de monitoreo, sin tocar la base de datos.

Uso::

    python -m app.tasks.diagnose_source [--source infrastructure|streaming|all]
                                        [--infrastructure mock|prometheus]

Valida la configuración, instancia las fuentes configuradas y muestra
qué datos podría obtener cada una. Con ``--infrastructure prometheus``
comprueba conectividad contra la URL configurada, lista qué métricas
están disponibles por host y valida las consultas PromQL.

Garantías:

- NO escribe métricas ni inventario en la base de datos (nunca abre una
  conexión ni crea el motor de SQLAlchemy).
- Con fuentes ``mock`` no realiza ninguna conexión de red; con
  ``prometheus`` solo hace GET de consulta al destino configurado.
- Los tokens y secretos NUNCA se muestran (solo si están configurados).

Códigos de salida: 0 = correcto; 1 = fuente inaccesible; 2 = configuración inválida.
"""

import argparse
import sys
from typing import Literal

from pydantic import BaseModel

from app.adapters.factory import get_infrastructure_adapter, get_streaming_adapter
from app.adapters.inventory import InventoryError
from app.adapters.prometheus import PrometheusInfrastructureAdapter
from app.core.config import Settings, get_settings

_SourceChoice = Literal["infrastructure", "streaming", "all"]


def _print_header(settings: Settings, source: _SourceChoice) -> None:
    token_state = "configurado (oculto)" if settings.prometheus_bearer_token else "no configurado"
    print("=== Diagnóstico de fuentes de monitoreo ===")
    print(f"entorno: {settings.app_env} | version: {settings.app_version}")
    print(
        f"configuración: MONITORING_ADAPTER={settings.monitoring_adapter} | "
        f"INFRASTRUCTURE_SOURCE={settings.infrastructure_source} | "
        f"STREAMING_SOURCE={settings.streaming_source} | MOCK_SEED={settings.mock_seed}"
    )
    if settings.infrastructure_source == "prometheus":
        print(
            f"prometheus: url={settings.prometheus_url} | "
            f"timeout={settings.prometheus_timeout_seconds}s | "
            f"tls_verify={settings.prometheus_tls_verify} | bearer token: {token_state}"
        )
        print(f"inventario: {settings.infrastructure_inventory_file}")
    print(f"diagnóstico solicitado: {source}")
    print()


def _fields_of(model: BaseModel) -> str:
    """Lista los campos disponibles de un snapshot con su valor de ejemplo."""
    lines = []
    for name, value in model.model_dump().items():
        lines.append(f"    {name} = {value}")
    return "\n".join(lines)


def _diagnose_prometheus(adapter: PrometheusInfrastructureAdapter) -> bool:
    """Diagnóstico específico de Prometheus; devuelve True si todo respondió."""
    print(f"--- Fuente de infraestructura: {adapter.source_name}")
    servers = adapter.get_servers()
    print(f"  servidores en el inventario: {len(servers)}")

    probes = adapter.probe()
    all_ok = True
    for probe in probes:
        print(f"  host {probe.external_id} (instance={probe.instance}):")
        if not probe.reachable:
            all_ok = False
            print(f"    INACCESIBLE: {probe.error}")
            continue
        up_text = "sin datos" if probe.up_value is None else str(probe.up_value)
        print(f"    up = {up_text}")
        for metric, value in probe.metrics.items():
            shown = "NO DISPONIBLE" if value is None else round(value, 2)
            print(f"    {metric} = {shown}")
        if probe.up_value is None:
            all_ok = False
    print()
    return all_ok


def _diagnose_infrastructure(settings: Settings) -> bool:
    """Diagnóstico de la fuente de infraestructura configurada."""
    adapter = get_infrastructure_adapter(settings)
    if isinstance(adapter, PrometheusInfrastructureAdapter):
        return _diagnose_prometheus(adapter)

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
    return True


def _diagnose_streaming(settings: Settings) -> bool:
    """Diagnóstico de la fuente de streaming configurada."""
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
    return True


def main(argv: list[str] | None = None) -> int:
    """Ejecuta el diagnóstico y devuelve el código de salida."""
    parser = argparse.ArgumentParser(
        description="Valida la configuración y muestra qué datos entregaría cada fuente."
    )
    parser.add_argument(
        "--source",
        choices=("infrastructure", "streaming", "all"),
        default=None,
        help="Secciones a diagnosticar (por defecto: all).",
    )
    parser.add_argument(
        "--infrastructure",
        choices=("mock", "prometheus"),
        default=None,
        help="Fuerza qué fuente de infraestructura diagnosticar.",
    )
    args = parser.parse_args(argv)

    settings = get_settings()
    if args.infrastructure is not None:
        settings = settings.model_copy(update={"infrastructure_source": args.infrastructure})
    source: _SourceChoice = args.source or (
        "infrastructure" if args.infrastructure is not None else "all"
    )
    _print_header(settings, source)

    all_ok = True
    try:
        if source in ("infrastructure", "all"):
            all_ok = _diagnose_infrastructure(settings) and all_ok
        if source in ("streaming", "all"):
            all_ok = _diagnose_streaming(settings) and all_ok
    except (ValueError, InventoryError) as error:
        print(f"CONFIGURACIÓN INVÁLIDA: {error}", file=sys.stderr)
        return 2

    print("Diagnóstico completado." if all_ok else "Diagnóstico con hosts inaccesibles.")
    print("No se escribió nada en la base de datos.")
    if settings.infrastructure_source == "prometheus" and source != "streaming":
        print("Conexiones realizadas: solo GET de consulta al Prometheus configurado.")
    else:
        print("No se realizó ninguna conexión externa (fuentes mock).")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
