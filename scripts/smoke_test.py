"""Smoke test end-to-end contra una base de datos real.

Verifica, en orden:

1. Ciclo completo de migraciones: upgrade head → downgrade base → upgrade head.
2. Arranque de la API con uvicorn.
3. /health público con base de datos conectada.
4. Autenticación global de /api/v1 (sin clave o clave incorrecta → 401).
5. Recolección mock: inserta datos; repetida en el mismo minuto: deduplica.
6. Overview coherente y endpoints históricos.
7. Estado del recolector desde el historial persistido.
8. Alertas internas disponibles.

Uso::

    DATABASE_URL=postgresql+psycopg://... API_KEY=una-clave \
        python scripts/smoke_test.py

Solo usa la biblioteca estándar; pensado para CI (GitHub Actions con un
servicio PostgreSQL) y para ejecución local.
"""

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from typing import Any

PORT = int(os.environ.get("SMOKE_PORT", "8300"))
BASE_URL = f"http://127.0.0.1:{PORT}"
STARTUP_TIMEOUT_SECONDS = 30


def run_step(description: str, command: list[str]) -> None:
    """Ejecuta un comando y aborta el smoke test si falla."""
    print(f"--- {description}: {' '.join(command)}")
    subprocess.run(command, check=True)


def request(method: str, path: str, headers: dict[str, str] | None = None) -> tuple[int, Any]:
    """Petición HTTP simple; devuelve (status, cuerpo JSON dinámico)."""
    req = urllib.request.Request(BASE_URL + path, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            return response.status, json.loads(response.read() or b"null")
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read() or b"null")


def check(condition: bool, message: str) -> None:
    """Asegura una condición del smoke test con mensaje claro."""
    if not condition:
        raise AssertionError(f"FALLO: {message}")
    print(f"OK: {message}")


def wait_for_health() -> None:
    """Espera a que la API responda /health o aborta por timeout."""
    deadline = time.monotonic() + STARTUP_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        try:
            status, _ = request("GET", "/health")
            if status == 200:
                return
        except (urllib.error.URLError, ConnectionError):
            pass
        time.sleep(0.5)
    raise TimeoutError("la API no respondió /health a tiempo")


def main() -> int:
    api_key = os.environ.get("API_KEY") or os.environ.get("COLLECTION_API_KEY")
    if not os.environ.get("DATABASE_URL") or not api_key:
        print("Define DATABASE_URL y API_KEY antes de ejecutar el smoke test.")
        return 2
    auth = {"X-API-Key": api_key}

    # 1. Ciclo de migraciones en ambos sentidos.
    run_step("migraciones: upgrade", [sys.executable, "-m", "alembic", "upgrade", "head"])
    run_step("migraciones: downgrade", [sys.executable, "-m", "alembic", "downgrade", "base"])
    run_step("migraciones: re-upgrade", [sys.executable, "-m", "alembic", "upgrade", "head"])

    # 2. API real con uvicorn.
    server = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(PORT),
        ]
    )
    try:
        wait_for_health()

        status, health = request("GET", "/health")
        check(status == 200 and health["database"] == "ok", "/health público con base de datos ok")

        # 3. Autenticación global de /api/v1.
        status, _ = request("POST", "/api/v1/collection/run")
        check(status == 401, "recolección sin clave rechazada (401)")
        status, _ = request("POST", "/api/v1/collection/run", {"X-API-Key": "clave-incorrecta"})
        check(status == 401, "recolección con clave incorrecta rechazada (401)")
        status, _ = request("GET", "/api/v1/servers")
        check(status == 401, "GET de consulta sin clave rechazado (401)")

        # 4. Recolección real + deduplicación.
        status, first = request("POST", "/api/v1/collection/run", auth)
        check(status == 200, "recolección con clave válida aceptada")
        check(first["servers_synced"] >= 4, "se sincronizaron al menos 4 servidores")
        check(first["channels_synced"] >= 20, "se sincronizaron al menos 20 canales")
        check(first["server_metrics_inserted"] >= 4, "se insertaron métricas de servidores")
        check(first["errors"] == [], "recolección sin errores")

        status, second = request("POST", "/api/v1/collection/run", auth)
        check(status == 200, "segunda recolección aceptada")
        check(
            second["server_metrics_inserted"] == 0 and second["server_metrics_skipped"] >= 4,
            "segunda recolección en el mismo minuto deduplicada",
        )

        # 5. Endpoints de consulta.
        status, servers = request("GET", "/api/v1/servers", auth)
        check(status == 200 and len(servers) >= 4, "listado de servidores disponible")

        server_id = servers[0]["id"]
        status, metrics = request("GET", f"/api/v1/servers/{server_id}/metrics?limit=1", auth)
        check(status == 200 and len(metrics) == 1, "histórico de métricas consultable")

        status, overview = request("GET", "/api/v1/overview", auth)
        check(status == 200, "overview disponible")
        check(overview["enabled_servers"] >= 4, "overview: servidores habilitados")
        check(overview["total_output_mbps"] > 0, "overview: output total positivo")
        check(overview["top_output_server"] is not None, "overview: servidor con mayor output")
        check(len(overview["top_channels"]) == 5, "overview: top 5 canales")
        utilizations = [
            item["utilization_percent"] for item in overview["server_network_utilization"]
        ]
        check(
            all(value is not None and 0 <= value <= 100 for value in utilizations),
            "overview: utilización de red calculada para todos los servidores mock",
        )

        # 6. Estado del recolector (contrato plano, historial persistido).
        status, cstatus = request("GET", "/api/v1/collection/status", auth)
        check(status == 200, "status de recolección disponible")
        check(cstatus["running"] is False, "status: sin recolección en curso")
        check(cstatus["status"] == "success", "status: última ejecución exitosa")
        check(cstatus["triggered_by"] == "manual", "status: disparo manual registrado")
        check(cstatus["duration_ms"] >= 0, "status: duración registrada")
        check(cstatus["heartbeat_at"] is not None, "status: heartbeat persistido")
        # El último run reflejado es la segunda recolección (deduplicada):
        # no inserta nada y omite servidores + canales.
        check(cstatus["inserted"] == 0, "status: segunda pasada sin inserciones")
        check(cstatus["skipped"] >= 24, "status: métricas omitidas agregadas")
        check(cstatus["next_run_at"] is None, "status: sin scheduler, sin próximo ciclo")

        # 7. Alertas internas.
        status, alerts = request("GET", "/api/v1/alerts", auth)
        check(status == 200, "alertas disponibles")
        check("generated_at" in alerts, "alertas: marca de tiempo presente")
        check(isinstance(alerts["alerts"], list), "alertas: lista evaluada")

        print("\nSMOKE TEST COMPLETO: todas las verificaciones pasaron.")
        return 0
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()


if __name__ == "__main__":
    sys.exit(main())
