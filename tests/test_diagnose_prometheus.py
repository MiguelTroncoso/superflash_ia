"""Diagnóstico de la fuente Prometheus contra un servidor HTTP simulado.

El servidor corre en 127.0.0.1 dentro del proceso de tests: no hay
ninguna conexión externa.
"""

import json
import socket
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import pytest

import app.database.session as db_session
import app.tasks.diagnose_source as diagnose_module
from tests.conftest import make_test_settings
from tests.prom_helpers import full_values, metric_key_of, prom_empty, prom_json

TOKEN = "token-diagnostico-secreto"

INVENTORY_YAML = """
servers:
  - external_id: srv-demo
    name: Demo 01
    node_exporter_instance: "192.0.2.10:9100"
    network_capacity_mbps: 1000
"""


class _FakePrometheusHandler(BaseHTTPRequestHandler):
    """Responde /api/v1/query con métricas simuladas de node_exporter."""

    values = full_values(disk_percent=None)  # disco ausente a propósito

    def do_GET(self) -> None:  # nombre requerido por http.server
        parsed = urlparse(self.path)
        if parsed.path != "/api/v1/query":
            self.send_error(404)
            return
        promql = parse_qs(parsed.query)["query"][0]
        value = self.values.get(metric_key_of(promql))
        payload = prom_empty() if value is None else prom_json(value)
        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: object) -> None:
        """Silencia el log del servidor de pruebas."""


@pytest.fixture()
def fake_prometheus() -> Iterator[str]:
    """Levanta un Prometheus simulado en 127.0.0.1 y devuelve su URL."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), _FakePrometheusHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join(timeout=5)


@pytest.fixture()
def _no_database(monkeypatch):
    """Falla el test si el diagnóstico intenta crear el motor de BD."""

    def _boom(*args, **kwargs):
        raise AssertionError("el diagnóstico no debe tocar la base de datos")

    monkeypatch.setattr(db_session, "create_engine", _boom)
    db_session.get_engine.cache_clear()
    db_session.get_session_factory.cache_clear()


def _configure(monkeypatch, tmp_path, url: str) -> None:
    inventory = tmp_path / "inventory.yaml"
    inventory.write_text(INVENTORY_YAML, encoding="utf-8")
    settings = make_test_settings(
        prometheus_url=url,
        infrastructure_inventory_file=str(inventory),
        prometheus_bearer_token=TOKEN,
    )
    monkeypatch.setattr(diagnose_module, "get_settings", lambda: settings)


def test_diagnose_prometheus_lists_available_metrics(
    fake_prometheus, monkeypatch, tmp_path, capsys, _no_database
):
    """El diagnóstico valida conectividad y lista métrica por métrica."""
    _configure(monkeypatch, tmp_path, fake_prometheus)

    exit_code = diagnose_module.main(["--infrastructure", "prometheus"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Fuente de infraestructura: prometheus" in output
    assert "host srv-demo" in output
    assert "up = 1.0" in output
    assert "cpu_percent = 35.46" in output
    assert "disk_percent = NO DISPONIBLE" in output
    assert "No se escribió nada en la base de datos." in output
    assert "solo GET de consulta" in output


def test_diagnose_prometheus_hides_bearer_token(
    fake_prometheus, monkeypatch, tmp_path, capsys, _no_database
):
    """El token jamás aparece en la salida del diagnóstico."""
    _configure(monkeypatch, tmp_path, fake_prometheus)

    diagnose_module.main(["--infrastructure", "prometheus"])
    output = capsys.readouterr().out

    assert TOKEN not in output
    assert "bearer token: configurado (oculto)" in output


def test_diagnose_prometheus_unreachable_returns_1(monkeypatch, tmp_path, capsys, _no_database):
    """Con Prometheus caído, el diagnóstico informa y sale con código 1."""
    # Puerto cerrado garantizado: se reserva y se libera antes de usarlo.
    probe_socket = socket.socket()
    probe_socket.bind(("127.0.0.1", 0))
    closed_port = probe_socket.getsockname()[1]
    probe_socket.close()

    _configure(monkeypatch, tmp_path, f"http://127.0.0.1:{closed_port}")

    exit_code = diagnose_module.main(["--infrastructure", "prometheus"])
    output = capsys.readouterr().out

    assert exit_code == 1
    assert "INACCESIBLE" in output
    assert TOKEN not in output


def test_diagnose_prometheus_without_config_returns_2(monkeypatch, capsys, _no_database):
    """Sin PROMETHEUS_URL el diagnóstico reporta configuración inválida."""
    monkeypatch.setattr(diagnose_module, "get_settings", lambda: make_test_settings())

    exit_code = diagnose_module.main(["--infrastructure", "prometheus"])

    assert exit_code == 2
    assert "CONFIGURACIÓN INVÁLIDA" in capsys.readouterr().err
