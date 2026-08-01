"""Utilidades compartidas para simular respuestas de Prometheus en tests."""

import re
from typing import Any

# Orden importa: los nombres más específicos primero (load15 contiene load1).
_METRIC_PATTERNS: tuple[tuple[str, str], ...] = (
    ("node_load15", "load_average_15m"),
    ("node_load5", "load_average_5m"),
    ("node_load1", "load_average_1m"),
    ("node_cpu_seconds_total", "cpu_percent"),
    ("node_memory_MemAvailable_bytes", "memory_percent"),
    ("node_memory_SwapFree_bytes", "swap_percent"),
    ("node_filesystem_avail_bytes", "disk_percent"),
    ("node_network_receive_bytes_total", "input_mbps"),
    ("node_network_transmit_bytes_total", "output_mbps"),
    ("node_disk_read_bytes_total", "io_read_mbps"),
    ("node_disk_written_bytes_total", "io_write_mbps"),
    ("node_boot_time_seconds", "uptime_seconds"),
    ("up{", "up"),
)


def metric_key_of(promql: str) -> str:
    """Identifica a qué métrica normalizada corresponde una consulta."""
    for needle, key in _METRIC_PATTERNS:
        if needle in promql:
            return key
    raise AssertionError(f"consulta no reconocida en el test: {promql}")


def instance_of(promql: str) -> str:
    """Extrae la etiqueta instance de una consulta PromQL."""
    match = re.search(r'instance="([^"]+)"', promql)
    assert match, f"consulta sin instance: {promql}"
    return match.group(1)


def prom_json(value: object) -> dict[str, Any]:
    """Respuesta de /api/v1/query con un único valor escalar."""
    return {
        "status": "success",
        "data": {
            "resultType": "vector",
            "result": [{"metric": {}, "value": [1753300000.0, str(value)]}],
        },
    }


def prom_empty() -> dict[str, Any]:
    """Respuesta de /api/v1/query sin series (métrica ausente)."""
    return {"status": "success", "data": {"resultType": "vector", "result": []}}


def full_values(**overrides: object) -> dict[str, object]:
    """Juego completo de métricas simuladas de node_exporter."""
    values: dict[str, object] = {
        "up": 1,
        "cpu_percent": 35.456,
        "memory_percent": 61.2,
        "disk_percent": 72.9,
        "swap_percent": 18.5,
        "input_mbps": 120.5,
        "output_mbps": 850.75,
        "io_read_mbps": 42.5,
        "io_write_mbps": 21.25,
        "load_average_1m": 1.42,
        "load_average_5m": 1.10,
        "load_average_15m": 0.95,
        "uptime_seconds": 86_400.7,
    }
    values.update(overrides)
    return values
