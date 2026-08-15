"""Orquestación segura, reanudable y auditable del onboarding SSH."""

from __future__ import annotations

import logging
import re
import secrets
from collections.abc import Callable
from datetime import UTC, datetime
from time import monotonic

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.adapters.inventory import Inventory, InventoryServer
from app.adapters.prometheus import PrometheusInfrastructureAdapter
from app.core.config import Settings
from app.database.session import get_session_factory
from app.models.onboarding import OnboardingAuditEvent, ServerInventorySnapshot, ServerOnboarding
from app.models.server import Server, ServerMetric, ServerOperationalStatus, ServerRole
from app.repositories.onboarding_repository import OnboardingRepository
from app.repositories.server_repository import ServerRepository
from app.schemas.onboarding import OnboardingStartRequest, OnboardingStatus
from app.services.ssh_service import (
    RemoteInventory,
    SSHConnectionService,
    SSHCredentials,
    SSHOperation,
    SSHServiceError,
    SSHSession,
    parse_inventory_output,
)

logger = logging.getLogger(__name__)

TERMINAL_STATUSES = {
    OnboardingStatus.COMPLETED.value,
    OnboardingStatus.FAILED.value,
    OnboardingStatus.CANCELLED.value,
    OnboardingStatus.ROLLBACK_REQUIRED.value,
}

STEP_PROGRESS: dict[str, tuple[str, int]] = {
    "connecting": ("connecting", 5),
    "authenticating": ("authenticating", 12),
    "discovering": ("discovering", 25),
    "installing_exporter": ("installing_exporter", 45),
    "configuring_firewall": ("configuring_firewall", 60),
    "verifying_exporter": ("verifying_exporter", 70),
    "registering_inventory": ("registering_inventory", 82),
    "configuring_monitoring": ("configuring_monitoring", 90),
    "validating": ("validating", 97),
}

SAFE_ERRORS: dict[str, str] = {
    "authentication_failed": "La autenticación SSH fue rechazada.",
    "host_key_invalid": "La host key SSH no coincide con la registrada.",
    "connection_failed": "No se pudo conectar por SSH al servidor.",
    "command_failed": "Falló una comprobación remota controlada.",
    "requirements_missing": "El servidor no cumple los requisitos de provisioning.",
    "port_9100_occupied": "El puerto 9100 está ocupado por un servicio no verificado.",
    "installer_failed": "La instalación de Node Exporter no fue validada.",
    "firewall_failed": "No se pudo configurar el firewall del Node Exporter.",
    "exporter_unhealthy": "Node Exporter no respondió con métricas válidas.",
    "inventory_failed": "No se pudo registrar el inventario técnico.",
    "network_interface_missing": "La interfaz de red configurada no existe.",
    "prometheus_not_configured": "Prometheus no está configurado para este servidor.",
    "prometheus_unavailable": "Prometheus no pudo validar el target del servidor.",
    "cancelled": "Onboarding cancelado por el operador.",
    "rollback_failed": "Rollback incompleto; revisar el diagnóstico del servidor.",
    "internal_error": "Onboarding detenido por un error interno seguro.",
}


class OnboardingService:
    """Servicio de dominio; nunca recibe comandos desde el navegador."""

    def __init__(
        self,
        settings: Settings,
        *,
        connection_factory: Callable[[Settings], SSHConnectionService] | None = None,
    ) -> None:
        self._settings = settings
        self._connection_factory = connection_factory or SSHConnectionService

    @staticmethod
    def create_server_and_onboarding(
        session: Session,
        payload: OnboardingStartRequest,
        actor: str,
        settings: Settings,
    ) -> ServerOnboarding:
        repositories = ServerRepository(session)
        external_id = payload.external_id or _external_id(payload.name)
        if repositories.get_by_external_id(external_id) is not None:
            raise ValueError("external_id ya existe")
        try:
            role = ServerRole(payload.role)
        except ValueError:
            role = ServerRole.OTHER
        now = datetime.now(UTC)
        server = repositories.create(
            {
                "external_id": external_id,
                "name": payload.name,
                "hostname": payload.ip,
                "role": role,
                "provider": payload.provider,
                "datacenter": payload.datacenter,
                "country": payload.country.upper() if payload.country else None,
                "server_type": payload.server_type,
                "network_interface": payload.network_interface,
                "network_capacity_mbps": payload.physical_capacity_mbps,
                "operational_network_limit_mbps": payload.operational_target_mbps,
                "recommended_network_limit_mbps": payload.recommended_max_mbps,
                "minimum_network_reserve_mbps": payload.minimum_reserve_mbps,
                "monthly_cost": payload.monthly_cost,
                "currency": payload.currency.upper() if payload.currency else None,
                "next_payment_date": payload.next_payment_date,
                "auto_renew": payload.auto_renew,
                "contract_status": "pending_onboarding",
                "ssh_port": payload.ssh_port,
                "ssh_username": payload.ssh_username,
                "prometheus_url": payload.prometheus_url or settings.prometheus_url,
                "prometheus_active": True,
                "status": ServerOperationalStatus.UNKNOWN,
                "enabled": False,
                "notes": payload.notes,
            }
        )
        onboarding = ServerOnboarding(
            server_id=server.id,
            status=OnboardingStatus.PENDING.value,
            current_step="pending",
            progress_percent=0,
            created_by=actor,
            auth_method=payload.auth_method.value,
            ssh_port=payload.ssh_port,
            ssh_username=payload.ssh_username,
            created_at=now,
            updated_at=now,
        )
        OnboardingRepository(session).create(onboarding)
        OnboardingRepository(session).add_audit(
            OnboardingAuditEvent(
                onboarding_id=onboarding.id,
                server_id=server.id,
                actor=actor,
                event="created",
                step="pending",
                success=True,
                detail_sanitized="Onboarding creado; credenciales efímeras no persistidas.",
                created_at=now,
            )
        )
        session.commit()
        return onboarding

    def run(
        self,
        onboarding_id: int,
        credentials: SSHCredentials,
        actor: str,
    ) -> None:
        """Ejecuta el flujo en background usando una sesión propia."""
        session = get_session_factory()()
        ssh: SSHSession | None = None
        installed = False
        try:
            repository = OnboardingRepository(session)
            onboarding = repository.get(onboarding_id)
            if onboarding is None:
                return
            server = ServerRepository(session).get(onboarding.server_id)
            if server is None:
                self._fail(session, onboarding, "internal_error", actor, rollback=False)
                return

            self._transition(session, onboarding, "connecting", actor, True)
            ssh = self._connection_factory(self._settings).connect(
                credentials, secrets.token_hex(8)
            )
            self._transition(session, onboarding, "authenticating", actor, True)
            self._check_cancel(session, onboarding)
            inventory = self._discover_and_precheck(
                session, onboarding, server, ssh, credentials, actor
            )
            self._transition(session, onboarding, "discovering", actor, True)

            exporter_check = ssh.run(SSHOperation.CHECK_EXPORTER)
            self._transition(session, onboarding, "installing_exporter", actor, exporter_check.ok)
            if not exporter_check.ok:
                install = ssh.run_script(
                    "install-node-exporter.sh",
                    environment={
                        "MONITOR_IP": self._settings.onboarding_monitor_ip,
                        "NODE_EXPORTER_VERSION": self._settings.node_exporter_version or "",
                        "SKIP_FIREWALL": "1",
                    },
                    sudo_password=credentials.password,
                )
                if not install.ok:
                    raise SSHServiceError("installer_failed", SAFE_ERRORS["installer_failed"])
                installed = True
            elif self._settings.node_exporter_version:
                version = ssh.run(SSHOperation.CHECK_EXPORTER_VERSION)
                if self._settings.node_exporter_version not in version.stdout:
                    update = ssh.run_script(
                        "update-node-exporter.sh",
                        environment={
                            "MONITOR_IP": self._settings.onboarding_monitor_ip,
                            "NODE_EXPORTER_VERSION": self._settings.node_exporter_version,
                            "SKIP_FIREWALL": "1",
                        },
                        sudo_password=credentials.password,
                    )
                    if not update.ok:
                        raise SSHServiceError("installer_failed", SAFE_ERRORS["installer_failed"])

            self._check_cancel(session, onboarding)
            firewall = ssh.run_script(
                "configure-node-exporter-firewall.sh",
                environment={"MONITOR_IP": self._settings.onboarding_monitor_ip},
                sudo_password=credentials.password,
            )
            self._transition(session, onboarding, "configuring_firewall", actor, firewall.ok)
            if not firewall.ok:
                raise SSHServiceError("firewall_failed", SAFE_ERRORS["firewall_failed"])

            verify = ssh.run(SSHOperation.CHECK_EXPORTER)
            self._transition(session, onboarding, "verifying_exporter", actor, verify.ok)
            if not verify.ok:
                raise SSHServiceError("exporter_unhealthy", SAFE_ERRORS["exporter_unhealthy"])

            self._check_cancel(session, onboarding)
            self._register_inventory(session, server, inventory, onboarding, actor)
            self._transition(session, onboarding, "registering_inventory", actor, True)

            if not server.prometheus_url:
                raise SSHServiceError(
                    "prometheus_not_configured", SAFE_ERRORS["prometheus_not_configured"]
                )
            self._transition(session, onboarding, "configuring_monitoring", actor, True)
            if not self._probe_prometheus(server):
                raise SSHServiceError(
                    "prometheus_unavailable", SAFE_ERRORS["prometheus_unavailable"]
                )

            self._transition(session, onboarding, "validating", actor, True)
            server.enabled = True
            server.status = ServerOperationalStatus.ONLINE
            server.contract_status = "active"
            server.last_heartbeat_at = datetime.now(UTC)
            onboarding.status = OnboardingStatus.COMPLETED.value
            onboarding.current_step = "completed"
            onboarding.progress_percent = 100
            onboarding.completed_at = datetime.now(UTC)
            onboarding.updated_at = datetime.now(UTC)
            onboarding.last_successful_step = "validating"
            repository.add_audit(
                OnboardingAuditEvent(
                    onboarding_id=onboarding.id,
                    server_id=server.id,
                    actor=actor,
                    event="completed",
                    step="validating",
                    success=True,
                    detail_sanitized=(
                        "SSH, Node Exporter, firewall, inventory y Prometheus validados."
                    ),
                    created_at=datetime.now(UTC),
                )
            )
            session.commit()
        except SSHServiceError as error:
            self._fail(
                session,
                onboarding if "onboarding" in locals() else None,
                error.code,
                actor,
                rollback=installed,
            )
        except Exception:
            logger.error("onboarding detenido por error interno seguro")
            self._fail(
                session,
                onboarding if "onboarding" in locals() else None,
                "internal_error",
                actor,
                rollback=installed,
            )
        finally:
            if ssh is not None:
                ssh.close()
            session.close()

    def rollback(self, onboarding_id: int, credentials: SSHCredentials, actor: str) -> None:
        session = get_session_factory()()
        ssh: SSHSession | None = None
        try:
            onboarding = OnboardingRepository(session).get(onboarding_id)
            if onboarding is None:
                return
            server = ServerRepository(session).get(onboarding.server_id)
            if server is None:
                return
            ssh = self._connection_factory(self._settings).connect(
                credentials, secrets.token_hex(8)
            )
            exporter = ssh.run_script("remove-node-exporter.sh", sudo_password=credentials.password)
            firewall = ssh.run_script(
                "configure-node-exporter-firewall.sh",
                environment={
                    "MONITOR_IP": self._settings.onboarding_monitor_ip,
                    "FIREWALL_ACTION": "remove",
                },
                sudo_password=credentials.password,
            )
            ok = exporter.ok and firewall.ok
            onboarding.status = (
                OnboardingStatus.FAILED.value if ok else OnboardingStatus.ROLLBACK_REQUIRED.value
            )
            onboarding.current_step = "rollback"
            onboarding.updated_at = datetime.now(UTC)
            server.enabled = False
            server.status = ServerOperationalStatus.UNKNOWN
            OnboardingRepository(session).add_audit(
                OnboardingAuditEvent(
                    onboarding_id=onboarding.id,
                    server_id=server.id,
                    actor=actor,
                    event="rollback",
                    step="rollback",
                    success=ok,
                    detail_sanitized=(
                        "Componentes de SuperFlash retirados; reglas gestionadas revisadas."
                        if ok
                        else SAFE_ERRORS["rollback_failed"]
                    ),
                    created_at=datetime.now(UTC),
                )
            )
            session.commit()
        except SSHServiceError:
            if "onboarding" in locals() and onboarding is not None:
                onboarding.status = OnboardingStatus.ROLLBACK_REQUIRED.value
                onboarding.updated_at = datetime.now(UTC)
                session.commit()
        finally:
            if ssh is not None:
                ssh.close()
            session.close()

    def diagnose(
        self, onboarding_id: int, credentials: SSHCredentials, actor: str
    ) -> dict[str, object]:
        """Ejecuta comprobaciones de solo lectura y devuelve un diagnóstico seguro."""
        session = get_session_factory()()
        ssh: SSHSession | None = None
        started = monotonic()
        result: dict[str, object] = {
            "status": "fail",
            "node_exporter": "FAIL",
            "prometheus": "FAIL",
            "firewall": "FAIL",
            "network": "FAIL",
            "latency_ms": None,
            "last_sample": None,
            "errors": [],
        }
        errors = result["errors"]
        assert isinstance(errors, list)
        try:
            onboarding = OnboardingRepository(session).get(onboarding_id)
            if onboarding is None:
                errors.append("Onboarding no encontrado")
                return result
            server = ServerRepository(session).get(onboarding.server_id)
            if server is None:
                errors.append("Servidor no encontrado")
                return result
            ssh = self._connection_factory(self._settings).connect(
                credentials, secrets.token_hex(8)
            )
            exporter = ssh.run(SSHOperation.CHECK_EXPORTER)
            result["node_exporter"] = "PASS" if exporter.ok else "FAIL"
            firewall = ssh.run(
                SSHOperation.FIREWALL_STATUS,
                as_root=True,
                sudo_password=credentials.password,
            )
            firewall_has_monitor = self._settings.onboarding_monitor_ip in firewall.stdout
            result["firewall"] = "PASS" if firewall.ok and firewall_has_monitor else "PARTIAL"
            inventory = parse_inventory_output(ssh.run(SSHOperation.DETECT_INVENTORY).stdout)
            result["network"] = (
                "PASS" if _network_is_valid(server.network_interface, inventory) else "FAIL"
            )
            if result["node_exporter"] != "PASS":
                errors.append("Node Exporter no responde")
            if result["firewall"] != "PASS":
                errors.append("No se pudo confirmar el acceso restringido del firewall")
            if result["network"] != "PASS":
                errors.append("La interfaz de red configurada no está disponible")
            if server.prometheus_url and self._probe_prometheus(server):
                result["prometheus"] = "PASS"
                latest_metric = session.scalar(
                    select(ServerMetric)
                    .where(ServerMetric.server_id == server.id)
                    .order_by(desc(ServerMetric.collected_at))
                    .limit(1)
                )
                result["last_sample"] = (
                    latest_metric.collected_at.isoformat() if latest_metric else None
                )
            else:
                errors.append(SAFE_ERRORS["prometheus_unavailable"])
            result["latency_ms"] = round((monotonic() - started) * 1000, 2)
            checks = [result[key] for key in ("node_exporter", "prometheus", "firewall", "network")]
            result["status"] = "PASS" if all(value == "PASS" for value in checks) else "PARTIAL"
            OnboardingRepository(session).add_audit(
                OnboardingAuditEvent(
                    onboarding_id=onboarding.id,
                    server_id=server.id,
                    actor=actor,
                    event="diagnosis",
                    step="diagnose",
                    success=result["status"] == "PASS",
                    detail_sanitized=f"Diagnóstico {result['status']} sin secretos.",
                    created_at=datetime.now(UTC),
                )
            )
            session.commit()
            return result
        except SSHServiceError as error:
            errors.append(SAFE_ERRORS.get(error.code, SAFE_ERRORS["internal_error"]))
            return result
        except Exception:
            logger.error("diagnóstico detenido por error interno seguro")
            errors.append(SAFE_ERRORS["internal_error"])
            return result
        finally:
            if ssh is not None:
                ssh.close()
            session.close()

    def _discover_and_precheck(
        self,
        session: Session,
        onboarding: ServerOnboarding,
        server: Server,
        ssh: SSHSession,
        credentials: SSHCredentials,
        actor: str,
    ) -> RemoteInventory:
        requirements = ssh.run(SSHOperation.CHECK_REQUIREMENTS)
        required_tools = ("systemctl", "curl", "tar", "sha256sum", "ss", "ip")
        missing_tools = [
            f"{tool}=missing" for tool in required_tools if f"{tool}=missing" in requirements.stdout
        ]
        if not requirements.ok or "systemctl=ok" not in requirements.stdout or missing_tools:
            raise SSHServiceError("requirements_missing", SAFE_ERRORS["requirements_missing"])
        if "port_9100=occupied" in requirements.stdout:
            exporter = ssh.run(SSHOperation.CHECK_EXPORTER)
            if not exporter.ok:
                raise SSHServiceError("port_9100_occupied", SAFE_ERRORS["port_9100_occupied"])
        sudo = ssh.run(SSHOperation.CHECK_SUDO)
        if sudo.stdout.strip() != "0":
            sudo = ssh.run(
                SSHOperation.CHECK_SUDO, as_root=True, sudo_password=credentials.password
            )
            if not sudo.ok or sudo.stdout.strip() != "0":
                raise SSHServiceError("requirements_missing", SAFE_ERRORS["requirements_missing"])
        raw = ssh.run(SSHOperation.DETECT_INVENTORY)
        if not raw.ok:
            raise SSHServiceError("inventory_failed", SAFE_ERRORS["inventory_failed"])
        inventory = parse_inventory_output(raw.stdout)
        if inventory.arch not in {"x86_64", "aarch64", "armv7l", "armv7"}:
            raise SSHServiceError("requirements_missing", SAFE_ERRORS["requirements_missing"])
        if (
            inventory.arch == "unknown"
            or inventory.hostname == "unknown"
            or not inventory.interfaces
        ):
            raise SSHServiceError("inventory_failed", SAFE_ERRORS["inventory_failed"])
        if server.network_interface and server.network_interface not in {
            str(item.get("name")) for item in inventory.interfaces
        }:
            raise SSHServiceError(
                "network_interface_missing", SAFE_ERRORS["network_interface_missing"]
            )
        return inventory

    def _register_inventory(
        self,
        session: Session,
        server: Server,
        inventory: RemoteInventory,
        onboarding: ServerOnboarding,
        actor: str,
    ) -> ServerInventorySnapshot:
        if server.network_interface:
            names = {str(item.get("name")) for item in inventory.interfaces}
            if server.network_interface not in names:
                raise SSHServiceError(
                    "network_interface_missing", SAFE_ERRORS["network_interface_missing"]
                )
        elif inventory.primary_interface:
            server.network_interface = inventory.primary_interface
        snapshot = OnboardingRepository(session).add_inventory_snapshot_if_changed(
            server_id=server.id,
            captured_at=datetime.now(UTC),
            fingerprint=inventory.fingerprint(),
            inventory=inventory.payload(),
        )
        OnboardingRepository(session).add_audit(
            OnboardingAuditEvent(
                onboarding_id=onboarding.id,
                server_id=server.id,
                actor=actor,
                event="inventory_snapshot",
                step="registering_inventory",
                success=True,
                detail_sanitized="Inventario técnico capturado sin credenciales.",
                created_at=datetime.now(UTC),
            )
        )
        return snapshot

    def _probe_prometheus(self, server: Server) -> bool:
        if not server.prometheus_url or not server.hostname:
            return False
        inventory = Inventory(
            servers=[
                InventoryServer(
                    external_id=server.external_id,
                    name=server.name,
                    hostname=server.hostname,
                    role=server.role,
                    network_capacity_mbps=server.network_capacity_mbps,
                    node_exporter_instance=_node_exporter_instance(server.hostname),
                    network_interface=server.network_interface,
                )
            ]
        )
        adapter = PrometheusInfrastructureAdapter(
            base_url=server.prometheus_url,
            inventory=inventory,
            timeout_seconds=self._settings.prometheus_timeout_seconds,
            bearer_token=self._settings.prometheus_bearer_token,
            verify_tls=self._settings.prometheus_tls_verify,
        )
        probe = adapter.probe()[0]
        return probe.reachable and probe.up_value is not None and probe.up_value > 0

    def _transition(
        self,
        session: Session,
        onboarding: ServerOnboarding,
        step: str,
        actor: str,
        success: bool,
    ) -> None:
        status, progress = STEP_PROGRESS[step]
        if onboarding.started_at is None:
            onboarding.started_at = datetime.now(UTC)
        onboarding.current_step = step
        onboarding.status = status
        onboarding.progress_percent = progress
        onboarding.updated_at = datetime.now(UTC)
        if success:
            onboarding.last_successful_step = step
        OnboardingRepository(session).add_audit(
            OnboardingAuditEvent(
                onboarding_id=onboarding.id,
                server_id=onboarding.server_id,
                actor=actor,
                event="step_completed" if success else "step_failed",
                step=step,
                success=success,
                detail_sanitized="Paso completado." if success else "Paso fallido.",
                created_at=datetime.now(UTC),
            )
        )
        session.commit()

    def _check_cancel(self, session: Session, onboarding: ServerOnboarding) -> None:
        session.refresh(onboarding)
        if onboarding.cancel_requested:
            raise SSHServiceError("cancelled", SAFE_ERRORS["cancelled"])

    def _fail(
        self,
        session: Session,
        onboarding: ServerOnboarding | None,
        code: str,
        actor: str,
        *,
        rollback: bool,
    ) -> None:
        if onboarding is None:
            return
        now = datetime.now(UTC)
        onboarding.status = (
            OnboardingStatus.ROLLBACK_REQUIRED.value if rollback else OnboardingStatus.FAILED.value
        )
        onboarding.failed_at = now
        onboarding.updated_at = now
        onboarding.last_error_code = code
        onboarding.last_error_message_sanitized = SAFE_ERRORS.get(
            code, SAFE_ERRORS["internal_error"]
        )
        OnboardingRepository(session).add_audit(
            OnboardingAuditEvent(
                onboarding_id=onboarding.id,
                server_id=onboarding.server_id,
                actor=actor,
                event="failed",
                step=onboarding.current_step,
                success=False,
                detail_sanitized=onboarding.last_error_message_sanitized,
                created_at=now,
            )
        )
        session.commit()


def _external_id(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:70] or "server"
    return f"{slug}-{secrets.token_hex(4)}"


def _node_exporter_instance(hostname: str) -> str:
    return hostname if re.search(r":\d+$", hostname) else f"{hostname}:9100"


def _network_is_valid(interface: str | None, inventory: RemoteInventory) -> bool:
    if interface:
        return interface in {str(item.get("name")) for item in inventory.interfaces}
    return bool(inventory.primary_interface or inventory.interfaces)
