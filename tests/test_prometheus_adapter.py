"""Tests del adaptador Prometheus con transporte HTTP simulado.

Ninguna prueba abre conexiones de red: ``httpx.MockTransport`` intercepta
todas las solicitudes dentro del proceso.
"""

import logging

import httpx
import pytest
from pydantic import ValidationError

from app.adapters.base import ServerSnapshot
from app.adapters.factory import get_infrastructure_adapter
from app.adapters.inventory import Inventory, InventoryServer
from app.adapters.mock_sources import MockInfrastructureAdapter
from app.adapters.prometheus import (
    DatabasePrometheusInfrastructureAdapter,
    HostProbe,
    PrometheusAuthError,
    PrometheusInfrastructureAdapter,
    PrometheusSourceError,
)
from app.adapters.sources import ServerStatus
from app.core.config import Settings
from app.models import Server, ServerRole
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
    assert first.filesystem_percent == 72.9
    assert first.swap_percent == 18.5
    assert first.input_mbps == 120.5
    assert first.output_mbps == 850.75
    assert first.io_read_mbps == 42.5
    assert first.io_write_mbps == 21.25
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


def test_database_targets_use_their_own_prometheus_configuration():
    """El provider administrado consulta targets y credenciales por servidor."""
    server = Server(
        external_id="srv-db",
        name="DB server",
        hostname="10.0.0.10",
        network_capacity_mbps=1000,
        prometheus_url="https://prometheus.db.internal",
        prometheus_token=TOKEN,
        enabled=True,
    )
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.headers["Authorization"] == f"Bearer {TOKEN}"
        key = metric_key_of(request.url.params["query"])
        return httpx.Response(200, json=prom_json(full_values()[key]))

    adapter = DatabasePrometheusInfrastructureAdapter(
        [server], transport=httpx.MockTransport(handler), now_fn=_fixed_clock
    )
    metrics = adapter.get_infrastructure_metrics()

    assert len(metrics) == 1
    assert metrics[0].server_external_id == "srv-db"
    assert requests
    assert all("10.0.0.10:9100" in request.url.params["query"] for request in requests)


@pytest.mark.parametrize("server_count", [1, 3, 5])
def test_database_provider_uses_real_metrics_and_mock_only_per_unconfigured_server(server_count):
    """La fuente real escala el primer flujo y conserva fallback por servidor."""
    servers = []
    real_ids: set[str] = set()
    fallback_ids: set[str] = set()
    for index in range(server_count):
        external_id = f"srv-production-{index}"
        configured = index % 2 == 0
        server = Server(
            external_id=external_id,
            name=external_id,
            hostname=f"10.0.0.{index + 1}",
            role=ServerRole.OTHER,
            network_capacity_mbps=1000,
            prometheus_url="https://prometheus.internal" if configured else None,
            enabled=True,
        )
        servers.append(server)
        (real_ids if configured else fallback_ids).add(external_id)

    def handler(request: httpx.Request) -> httpx.Response:
        key = metric_key_of(request.url.params["query"])
        return httpx.Response(200, json=prom_json(full_values()[key]))

    fallback = MockInfrastructureAdapter(
        seed=42,
        server_snapshots=[
            ServerSnapshot(
                external_id=server.external_id,
                name=server.name,
                hostname=server.hostname,
                role=server.role,
                network_capacity_mbps=server.network_capacity_mbps,
            )
            for server in servers
            if server.external_id in fallback_ids
        ],
    )
    adapter = DatabasePrometheusInfrastructureAdapter(
        servers,
        transport=httpx.MockTransport(handler),
        fallback=fallback if fallback_ids else None,
        now_fn=_fixed_clock,
    )

    metrics = adapter.get_infrastructure_metrics()

    assert {metric.server_external_id for metric in metrics} == real_ids | fallback_ids
    assert {
        metric.server_external_id for metric in metrics if metric.source == "prometheus"
    } == real_ids
    assert {
        metric.server_external_id for metric in metrics if metric.source == "mock"
    } == fallback_ids
    assert len(adapter.get_servers()) == server_count


def test_probe_reports_latency_without_exposing_prometheus_configuration():
    """El diagnóstico mide la consulta y conserva el secreto fuera del contrato."""
    server = Server(
        external_id="srv-probe",
        name="Probe",
        hostname="10.0.0.20",
        role=ServerRole.OTHER,
        prometheus_url="https://prometheus.internal",
        prometheus_token=TOKEN,
    )
    adapter = DatabasePrometheusInfrastructureAdapter(
        [server],
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200, json=prom_json(full_values()[metric_key_of(request.url.params["query"])])
            )
        ),
        now_fn=_fixed_clock,
    )

    probe = adapter.probe_server(server)

    assert isinstance(probe, HostProbe)
    assert probe.reachable is True
    assert probe.up_value == 1
    assert probe.latency_ms is not None
    assert TOKEN not in str(probe)


def test_probe_can_discover_inventory_and_respects_manual_interface():
    """El diagnóstico descubre inventario sin alterar la recolección normal."""
    requests: list[str] = []

    def vector_json(rows):
        return {
            "status": "success",
            "data": {
                "resultType": "vector",
                "result": [
                    {"metric": labels, "value": [1753300000.0, str(value)]}
                    for labels, value in rows
                ],
            },
        }

    def handler(request: httpx.Request) -> httpx.Response:
        query = request.url.params["query"]
        requests.append(query)
        if "node_exporter_build_info" in query:
            return httpx.Response(200, json=vector_json([({"version": "1.8.2"}, 1)]))
        if "node_uname_info" in query:
            return httpx.Response(
                200,
                json=vector_json(
                    [
                        (
                            {
                                "nodename": "real-node",
                                "machine": "x86_64",
                                "sysname": "Linux",
                                "release": "6.8.0",
                                "version": "#1",
                            },
                            1,
                        )
                    ]
                ),
            )
        if "node_cpu_info" in query:
            return httpx.Response(
                200,
                json=vector_json(
                    [
                        ({"core": "0", "model_name": "Test CPU"}, 1),
                        ({"core": "1", "model_name": "Test CPU"}, 1),
                    ]
                ),
            )
        if "node_filesystem_size_bytes" in query:
            return httpx.Response(
                200,
                json=vector_json(
                    [({"device": "/dev/sda1", "mountpoint": "/", "fstype": "ext4"}, 1_000_000)]
                ),
            )
        if "node_network_info" in query:
            return httpx.Response(
                200, json=vector_json([({"device": "ens18", "operstate": "up"}, 1)])
            )
        if "node_network_speed_bytes" in query:
            return httpx.Response(200, json=vector_json([({"device": "ens18"}, 125_000_000)]))
        if "node_memory_MemTotal_bytes" in query:
            return httpx.Response(200, json=prom_json(16_000_000_000))
        if "node_memory_SwapTotal_bytes" in query:
            return httpx.Response(200, json=prom_json(2_000_000_000))
        if "node_boot_time_seconds" in query and "time() -" not in query:
            return httpx.Response(200, json=prom_json(1753200000))
        if "timestamp(up" in query:
            return httpx.Response(200, json=prom_json(1753300000))
        return httpx.Response(200, json=prom_json(full_values()[metric_key_of(query)]))

    inventory = Inventory(
        servers=[
            InventoryServer(
                external_id="srv-discovery",
                name="Discovery",
                hostname="10.0.0.30",
                node_exporter_instance="10.0.0.30:9100",
                network_interface="ens18",
            )
        ]
    )
    adapter = PrometheusInfrastructureAdapter(
        base_url="https://prometheus.internal",
        inventory=inventory,
        transport=httpx.MockTransport(handler),
        now_fn=_fixed_clock,
    )

    (probe,) = adapter.probe(include_inventory=True)

    assert probe.reachable is True
    assert probe.node_exporter_version == "1.8.2"
    assert probe.last_scrape_at is not None
    assert probe.inventory is not None
    assert probe.inventory["hostname"] == "real-node"
    assert probe.inventory["cpu"] == {"model": "Test CPU", "cores": 2, "threads": 2}
    assert probe.inventory["interfaces"] == [
        {"name": "ens18", "operstate": "up", "speed_mbps": 1000.0}
    ]
    assert any(
        "node_network_receive_bytes_total" in query and 'device="ens18"' in query
        for query in requests
    )


def test_probe_marks_missing_manual_interface():
    """Una interfaz seleccionada sin RX/TX queda en diagnóstico degradado."""
    inventory = Inventory(
        servers=[
            InventoryServer(
                external_id="srv-missing-interface",
                name="Missing interface",
                hostname="10.0.0.31",
                node_exporter_instance="10.0.0.31:9100",
                network_interface="ens3",
            )
        ]
    )

    def handler(request: httpx.Request) -> httpx.Response:
        query = request.url.params["query"]
        if (
            "node_network_receive_bytes_total" in query
            or "node_network_transmit_bytes_total" in query
        ):
            return httpx.Response(200, json=prom_empty())
        return httpx.Response(200, json=prom_json(full_values()[metric_key_of(query)]))

    adapter = PrometheusInfrastructureAdapter(
        base_url="https://prometheus.internal",
        inventory=inventory,
        transport=httpx.MockTransport(handler),
    )

    (probe,) = adapter.probe()

    assert probe.reachable is True
    assert probe.up_value == 1
    assert probe.error == "interfaz_no_encontrada"


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
