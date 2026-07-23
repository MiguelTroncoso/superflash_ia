"""Inventario local de servidores para fuentes de infraestructura reales.

El inventario es un archivo YAML o JSON **local y no versionado** (ver
``.gitignore``): describe qué servidores monitorear y cómo se llaman sus
instancias en la fuente (p. ej. la etiqueta ``instance`` de Prometheus).
El repositorio solo incluye un ejemplo sin datos reales:
``config/inventory.example.yaml``.
"""

import json
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, ValidationError, field_validator

from app.adapters.base import ServerSnapshot
from app.models.server import ServerRole


class InventoryError(ValueError):
    """El inventario no existe o es inválido."""


class InventoryServer(BaseModel):
    """Un servidor monitoreado según el inventario local."""

    external_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    hostname: str | None = None
    role: ServerRole = ServerRole.OTHER
    network_capacity_mbps: float | None = Field(default=None, ge=0)
    # Valor de la etiqueta "instance" en Prometheus (host:puerto). El
    # patrón impide caracteres con significado en PromQL (comillas, llaves).
    node_exporter_instance: str = Field(pattern=r"^[A-Za-z0-9._\-\[\]:]+$", max_length=253)
    enabled: bool = True

    def to_snapshot(self) -> ServerSnapshot:
        """Convierte la entrada de inventario al snapshot de servidor."""
        return ServerSnapshot(
            external_id=self.external_id,
            name=self.name,
            hostname=self.hostname,
            role=self.role,
            network_capacity_mbps=self.network_capacity_mbps,
            enabled=self.enabled,
        )


class Inventory(BaseModel):
    """Colección validada de servidores a monitorear."""

    servers: list[InventoryServer] = Field(min_length=1)

    @field_validator("servers")
    @classmethod
    def _unique_identifiers(cls, servers: list[InventoryServer]) -> list[InventoryServer]:
        """Rechaza external_id o instancias duplicadas."""
        seen_ids: set[str] = set()
        seen_instances: set[str] = set()
        for server in servers:
            if server.external_id in seen_ids:
                raise ValueError(f"external_id duplicado en el inventario: {server.external_id}")
            if server.node_exporter_instance in seen_instances:
                raise ValueError(
                    f"instancia duplicada en el inventario: {server.node_exporter_instance}"
                )
            seen_ids.add(server.external_id)
            seen_instances.add(server.node_exporter_instance)
        return servers


def load_inventory(path: str | Path) -> Inventory:
    """Carga y valida un inventario YAML o JSON.

    Raises:
        InventoryError: Si el archivo no existe, no se puede parsear o
            no cumple el esquema.
    """
    file_path = Path(path)
    if not file_path.is_file():
        raise InventoryError(f"El inventario no existe: {file_path}")

    try:
        raw_text = file_path.read_text(encoding="utf-8")
        if file_path.suffix.lower() == ".json":
            data = json.loads(raw_text)
        elif file_path.suffix.lower() in (".yaml", ".yml"):
            data = yaml.safe_load(raw_text)
        else:
            raise InventoryError(
                f"Extensión de inventario no soportada: {file_path.suffix!r} (usa .yaml o .json)"
            )
    except (OSError, json.JSONDecodeError, yaml.YAMLError) as error:
        raise InventoryError(f"No se pudo leer el inventario {file_path}: {error}") from error

    try:
        return Inventory.model_validate(data)
    except ValidationError as error:
        raise InventoryError(f"Inventario inválido ({file_path}): {error}") from error
