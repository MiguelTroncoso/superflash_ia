"""Tests del inventario local de infraestructura (YAML/JSON)."""

import json

import pytest

from app.adapters.inventory import InventoryError, load_inventory
from app.models.server import ServerRole

VALID_YAML = """
servers:
  - external_id: srv-a
    name: Servidor A
    hostname: a.example.internal
    role: live
    network_capacity_mbps: 10000
    node_exporter_instance: "192.0.2.10:9100"
  - external_id: srv-b
    name: Servidor B
    node_exporter_instance: "192.0.2.11:9100"
    enabled: false
"""


def test_load_yaml_inventory(tmp_path):
    """Un inventario YAML válido se carga con defaults correctos."""
    path = tmp_path / "inventory.yaml"
    path.write_text(VALID_YAML, encoding="utf-8")

    inventory = load_inventory(path)

    assert [server.external_id for server in inventory.servers] == ["srv-a", "srv-b"]
    first, second = inventory.servers
    assert first.role is ServerRole.LIVE
    assert first.network_capacity_mbps == 10000
    assert second.role is ServerRole.OTHER  # default
    assert second.enabled is False
    snapshot = first.to_snapshot()
    assert snapshot.external_id == "srv-a" and snapshot.enabled is True


def test_load_json_inventory(tmp_path):
    """El mismo esquema funciona en JSON."""
    path = tmp_path / "inventory.json"
    path.write_text(
        json.dumps(
            {
                "servers": [
                    {
                        "external_id": "srv-json",
                        "name": "Desde JSON",
                        "node_exporter_instance": "192.0.2.20:9100",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    inventory = load_inventory(path)
    assert inventory.servers[0].external_id == "srv-json"


def test_shipped_example_inventory_is_valid():
    """El ejemplo versionado del repositorio siempre debe parsear."""
    inventory = load_inventory("config/inventory.example.yaml")
    assert len(inventory.servers) >= 3
    assert all(server.node_exporter_instance for server in inventory.servers)


def test_missing_file_raises(tmp_path):
    """Un inventario inexistente produce un error claro."""
    with pytest.raises(InventoryError, match="no existe"):
        load_inventory(tmp_path / "no-esta.yaml")


def test_unsupported_extension_raises(tmp_path):
    """Extensiones distintas de YAML/JSON se rechazan."""
    path = tmp_path / "inventory.toml"
    path.write_text("x = 1", encoding="utf-8")
    with pytest.raises(InventoryError, match="Extensión"):
        load_inventory(path)


def test_duplicate_external_id_rejected(tmp_path):
    """external_id duplicado invalida el inventario."""
    path = tmp_path / "inventory.yaml"
    path.write_text(
        """
servers:
  - {external_id: srv-a, name: A, node_exporter_instance: "192.0.2.10:9100"}
  - {external_id: srv-a, name: B, node_exporter_instance: "192.0.2.11:9100"}
""",
        encoding="utf-8",
    )
    with pytest.raises(InventoryError, match="duplicado"):
        load_inventory(path)


def test_empty_inventory_rejected(tmp_path):
    """Un inventario sin servidores no es válido."""
    path = tmp_path / "inventory.yaml"
    path.write_text("servers: []", encoding="utf-8")
    with pytest.raises(InventoryError, match="Inventario inválido"):
        load_inventory(path)


def test_instance_with_promql_metacharacters_rejected(tmp_path):
    """Comillas u otros caracteres peligrosos en instance se rechazan."""
    path = tmp_path / "inventory.yaml"
    path.write_text(
        """
servers:
  - external_id: srv-a
    name: A
    node_exporter_instance: 'malo",job="x'
""",
        encoding="utf-8",
    )
    with pytest.raises(InventoryError, match="Inventario inválido"):
        load_inventory(path)
