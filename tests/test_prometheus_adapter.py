"""Tests del adaptador Prometheus con transporte HTTP simulado.

Ninguna prueba abre conexiones de red: ``httpx.MockTransport`` intercepta
todas las solicitudes dentro del proceso.
"""

import logging

import httpx
import pytest
from pydantic import ValidationError

from app.adapters.factory import get_infrastructure_adapter
from app.adapters.inventory import Inventory, InventoryServer
from app.adapters.prometheus import (
    PrometheusAuthError,
    PrometheusInfrastructureAdapter,
    PrometheusSourceError,
)
from app.adapters.sources import ServerStatus
from app.core.config import Settings
from tests.conftest import FIXED_NOW, make_test_settings
from tests.prom_helpers import full_values, instance_of, metric_key_of, prom_empty, prom_json

TOKEN = "token-de-prueba-no-debe-filtrarse"


def _fixed_clock():
    return FIXED_NOW


def _inventory(*instances: str) -> Inventory:
    return Inventory(
        servers=[
            InventoryServer(
                external_id=f"srv-{index}",
                name=f"Servidor {index}",
                node_exporter_instance=instance,
                network_capacity_mbps=1000.0,
            )
            for index, instance in enumerate(instances, 1)
        ]
    )


def _adapter(handler, *instances: str, token: str | None = None):
    return PrometheusInfrastructureAdapter(
        base_url="https://prometheus.test.internal:9090",
        inventory=_inventory(*instances),
        timeout_seconds=5.0,
        bearer_token=token,
        transport=httpx.MockTransport(handler),
        now_fn=_fixed_clock,
    )


def _values_handler(values_by_instance, *, broken_instances=frozenset()):
    """Handler que responde según (instance, métrica); simula fallos por host."""

    def handler(request: httpx.Request) -> httpx.Response:
        promql = request.url.params["query"]
        instance = instance_of(promql)
        if instance in broken_instances:
            raise httpx.ConnectError("conexión rechazada", request=request)
        values = values_by_instance[instance]
        value = values.get(metric_key_of(promql))
        if value is None:
            return httpx.Response(200, json=prom_empty())
        return httpx.Response(200, json=prom_json(value))

    return handler


# --- Respuestas válidas y normalización ----------------------------------------


def test_valid_responses_are_normalized():
    """Los valores de node_exporter se normalizan al snapshot del contrato."""
    handler = _values_handler(
        {
            "10.0.0.1:9100": full_values(),
            "10.0.0.2:9100": full_values(cpu_percent=12.0, memory_percent=130.0),
        }
    )
    adapter = _adapter(handler, "10.0.0.1:9100", "10.0.0.2:9100")

    metrics = {m.server_external_id: m for m in adapter.get_infrastructure_metrics()}

    assert set(metrics) == {"srv-1", "srv-2"}
    first = metrics["srv-1"]
    assert first.cpu_percent == 35.46  # redondeo a 2 decimales
    assert first.memory_percent == 61.2
    assert first.disk_percent == 72.9
    assert first.input_mbps == 120.5
    assert first.output_mbps == 850.75
    assert first.load_average_1m == 1.42
    assert first.uptime_seconds == 86_400  # normalizado a entero
    assert first.status is ServerStatus.ONLINE
    assert first.collected_at == FIXED_NOW.replace(second=0, microsecond=0)
    # Valores fuera de rango se acotan (rate() puede exceder 100%).
    assert metrics["srv-2"].memory_percent == 100.0


def test_up_zero_host_emits_no_sample():
    """Un host con up=0 no fabrica métricas en cero: simplemente se omite."""
    handler = _values_handler({"10.0.0.1:9100": full_values(up=0)})
    adapter = _adapter(handler, "10.0.0.1:9100")

    assert adapter.get_infrastructure_metrics() == []


def test_multiple_hosts_one_failure_does_not_block_others():
    """Un host caído no impide recolectar los demás."""
    handler = _values_handler(
        {"10.0.0.1:9100": full_values(), "10.0.0.2:9100": full_values()},
        broken_instances={"10.0.0.2:9100"},
    )
    adapter = _adapter(handler, "10.0.0.1:9100", "10.0.0.2:9100")

    metrics = adapter.get_infrastructure_metrics()

    assert [m.server_external_id for m in metrics] == ["srv-1"]


# --- Métricas faltantes y valores inválidos ------------------------------------


def test_missing_essential_metric_skips_host():
    """Sin CPU (métrica esencial) el host no emite muestra."""
    handler = _values_handler(
        {
            "10.0.0.1:9100": full_values(cpu_percent=None),
            "10.0.0.2:9100": full_values(),
        }
    )
    adapter = _adapter(handler, "10.0.0.1:9100", "10.0.0.2:9100")

    metrics = adapter.get_infrastructure_metrics()

    assert [m.server_external_id for m in metrics] == ["srv-2"]


def test_missing_optional_metrics_are_none():
    """Disco, load y uptime ausentes no impiden la muestra."""
    handler = _values_handler(
        {
            "10.0.0.1:9100": full_values(
                disk_percent=None,
                load_average_1m=None,
                load_average_5m=None,
                load_average_15m=None,
                uptime_seconds=None,
            )
        }
    )
    adapter = _adapter(handler, "10.0.0.1:9100")

    (metric,) = adapter.get_infrastructure_metrics()

    assert metric.disk_percent is None
    assert metric.load_average_1m is None
    assert metric.uptime_seconds is None
    assert metric.status is ServerStatus.ONLINE


def test_nan_values_treated_as_missing():
    """Un valor NaN de Prometheus cuenta como métrica ausente."""
    handler = _values_handler(
        {"10.0.0.1:9100": full_values(cpu_percent="NaN"), "10.0.0.2:9100": full_values()}
    )
    adapter = _adapter(handler, "10.0.0.1:9100", "10.0.0.2:9100")

    metrics = adapter.get_infrastructure_metrics()

    assert [m.server_external_id for m in metrics] == ["srv-2"]


def test_unparseable_value_counts_as_host_failure():
    """Un valor no numérico produce fallo del host, no de toda la pasada."""
    handler = _values_handler(
        {"10.0.0.1:9100": full_values(cpu_percent="no-es-numero"), "10.0.0.2:9100": full_values()}
    )
    adapter = _adapter(handler, "10.0.0.1:9100", "10.0.0.2:9100")

    metrics = adapter.get_infrastructure_metrics()

    assert [m.server_external_id for m in metrics] == ["srv-2"]


# --- Timeouts, caídas y autenticación ------------------------------------------


def test_timeout_on_single_host_raises_source_error():
    """Con un único host y timeout, la pasada completa falla con claridad."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("lento", request=request)

    adapter = _adapter(handler, "10.0.0.1:9100")

    with pytest.raises(PrometheusSourceError, match="ningún host respondió"):
        adapter.get_infrastructure_metrics()


def test_server_down_raises_source_error():
    """Prometheus caído (conexión rechazada en todos) marca la pasada en error."""
    handler = _values_handler({}, broken_instances={"10.0.0.1:9100", "10.0.0.2:9100"})
    adapter = _adapter(handler, "10.0.0.1:9100", "10.0.0.2:9100")

    with pytest.raises(PrometheusSourceError) as excinfo:
        adapter.get_infrastructure_metrics()
    assert "srv-1" in str(excinfo.value) and "srv-2" in str(excinfo.value)


@pytest.mark.parametrize("status_code", [401, 403])
def test_auth_errors_raise_without_leaking_token(status_code, caplog):
    """401/403 lanzan error de credenciales sin exponer el token en ningún lado."""

    def handler(request: httpx.Request) -> httpx.Response:
        # El token viaja en la cabecera (comprobación del transporte)...
        assert request.headers["Authorization"] == f"Bearer {TOKEN}"
        return httpx.Response(status_code, json={"status": "error"})

    adapter = _adapter(handler, "10.0.0.1:9100", token=TOKEN)

    with caplog.at_level(logging.DEBUG), pytest.raises(PrometheusAuthError) as excinfo:
        adapter.get_infrastructure_metrics()

    # ...pero jamás aparece en la excepción ni en los logs.
    assert TOKEN not in str(excinfo.value)
    assert TOKEN not in caplog.text


def test_no_token_in_logs_during_partial_failures(caplog):
    """Los logs de fallos por host tampoco contienen el token."""
    handler = _values_handler({"10.0.0.1:9100": full_values()}, broken_instances={"10.0.0.2:9100"})
    adapter = _adapter(handler, "10.0.0.1:9100", "10.0.0.2:9100", token=TOKEN)

    with caplog.at_level(logging.DEBUG):
        adapter.get_infrastructure_metrics()

    assert TOKEN not in caplog.text


# --- TLS y configuración -------------------------------------------------------


def test_tls_verification_enabled_by_default():
    """Sin configuración explícita, la verificación TLS queda activa."""
    adapter = _adapter(_values_handler({"10.0.0.1:9100": full_values()}), "10.0.0.1:9100")
    assert adapter.verify_tls is True


def test_production_rejects_disabled_tls():
    """APP_ENV=production con TLS desactivado no puede ni arrancar."""
    with pytest.raises(ValidationError, match="PROMETHEUS_TLS_VERIFY"):
        Settings(
            _env_file=None,
            app_env="production",
            prometheus_tls_verify=False,
        )


def test_factory_requires_url_and_inventory(tmp_path):
    """La fábrica exige URL e inventario para la fuente prometheus."""
    with pytest.raises(ValueError, match="PROMETHEUS_URL"):
        get_infrastructure_adapter(make_test_settings(infrastructure_source="prometheus"))

    with pytest.raises(ValueError, match="INFRASTRUCTURE_INVENTORY_FILE"):
        get_infrastructure_adapter(
            make_test_settings(
                infrastructure_source="prometheus",
                prometheus_url="https://prometheus.test.internal:9090",
            )
        )

    inventory_file = tmp_path / "inventory.yaml"
    inventory_file.write_text(
        "servers:\n"
        "  - external_id: srv-a\n"
        "    name: Servidor A\n"
        '    node_exporter_instance: "192.0.2.10:9100"\n',
        encoding="utf-8",
    )
    adapter = get_infrastructure_adapter(
        make_test_settings(
            infrastructure_source="prometheus",
            prometheus_url="https://prometheus.test.internal:9090",
            infrastructure_inventory_file=str(inventory_file),
        )
    )
    assert isinstance(adapter, PrometheusInfrastructureAdapter)
    assert adapter.source_name == "prometheus"
    assert [server.external_id for server in adapter.get_servers()] == ["srv-a"]
