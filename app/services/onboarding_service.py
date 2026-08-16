"""Orquestación segura, reanudable y auditable del onboarding SSH."""

from __future__ import annotations

import logging
import re
import secrets
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
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
from app.schemas.onboarding import (
    MaintenanceAction,
    OnboardingDiscoveryRequest,
    OnboardingStartRequest,
    OnboardingStatus,
    OnboardingTestSSHRequest,
)
from app.services.ssh_service import (
    RemoteInventory,
    SSHConnectionService,
    SSHCredentials,
    SSHOperation,
    SSHServiceError,
    SSHSession,
    detect_firewall,
    exporter_version_from_output,
    parse_inventory_output,
    private_key_fingerprint,
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
    "wrong_password": "La contraseña SSH no fue aceptada.",
    "ssh_user_not_found": "El usuario SSH no existe en el servidor.",
    "root_login_disabled": "El acceso SSH directo de root está deshabilitado.",
    "password_authentication_disabled": (
        "La autenticación por contraseña está deshabilitada; usa una clave privada."
    ),
    "public_key_required": "El servidor requiere autenticación por clave pública.",
    "permission_denied": "El acceso SSH fue denegado.",
    "ssh_timeout": "La conexión SSH agotó el tiempo de espera.",
    "host_unreachable": "El servidor no es alcanzable por SSH.",
    "firewall_blocked": "La conexión SSH fue rechazada por el servidor o firewall.",
    "fingerprint_mismatch": "La huella SSH no coincide; el onboarding fue bloqueado.",
    "host_key_invalid": "La host key SSH no coincide con la registrada.",
    "host_key_new": "Se requiere confirmar la huella de la host key SSH.",
    "host_key_changed": "La host key SSH cambió y fue bloqueada.",
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
    "invalid_private_key": "La clave privada SSH no es válida.",
    "maintenance_failed": "La acción administrada no pudo validarse.",
    "temporary_directory_unavailable": (
        "El usuario no tiene acceso de escritura al directorio temporal."
    ),
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
                "server_profile": payload.server_profile,
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
                "ssh_host_key_fingerprint": payload.host_key_fingerprint,
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
            server.ssh_host_key_fingerprint = (
                ssh.host_key_fingerprint or server.ssh_host_key_fingerprint
            )
            management_key_path = self._settings.ssh_management_private_key_file
            if management_key_path and Path(management_key_path).is_file():
                key_text = Path(management_key_path).read_text(encoding="utf-8")
                management_fingerprint = private_key_fingerprint(key_text)
                server.ssh_management_configured = True
                if server.ssh_management_key_fingerprint != management_fingerprint:
                    server.ssh_management_key_rotated_at = (
                        datetime.now(UTC) if server.ssh_management_key_fingerprint else None
                    )
                    server.ssh_management_key_fingerprint = management_fingerprint
                if server.ssh_management_key_created_at is None:
                    server.ssh_management_key_created_at = datetime.fromtimestamp(
                        Path(management_key_path).stat().st_mtime, tz=UTC
                    )
            server.node_exporter_status = "running"
            version_output = ssh.run(SSHOperation.CHECK_EXPORTER_VERSION)
            server.node_exporter_version = exporter_version_from_output(version_output.stdout)
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

    def test_ssh(self, payload: OnboardingTestSSHRequest) -> dict[str, object]:
        """Run the onboarding preflight without installing or mutating anything."""
        credentials = SSHCredentials(
            host=payload.host,
            port=payload.port,
            username=payload.username,
            password=payload.password,
            private_key=payload.private_key,
            expected_host_key_fingerprint=(
                payload.host_key_fingerprint if payload.confirm_host_key else None
            ),
        )
        result: dict[str, object] = {
            "reachable": False,
            "authentication_ok": False,
            "privilege_ok": False,
            "temp_write_ok": False,
            "host_key_fingerprint": payload.host_key_fingerprint,
            "host_key_status": "unknown",
            "hostname": None,
            "os": None,
            "os_version": None,
            "architecture": None,
            "interfaces": [],
            "discovered_inventory": None,
            "error_code": None,
            "error_message": None,
            "probable_cause": None,
        }
        ssh: SSHSession | None = None
        try:
            ssh = self._connection_factory(self._settings).connect(
                credentials, secrets.token_hex(8)
            )
            result["reachable"] = True
            result["authentication_ok"] = True
            result["host_key_fingerprint"] = ssh.host_key_fingerprint
            result["host_key_status"] = ssh.host_key_status

            privilege = ssh.run(SSHOperation.CHECK_SUDO)
            if privilege.ok and privilege.stdout.strip() == "0":
                result["privilege_ok"] = True
            else:
                privilege = ssh.run(
                    SSHOperation.CHECK_SUDO,
                    as_root=True,
                    sudo_password=payload.password,
                )
                result["privilege_ok"] = privilege.ok and privilege.stdout.strip() == "0"

            temp_write = ssh.run(SSHOperation.CHECK_TEMP_WRITE)
            result["temp_write_ok"] = temp_write.ok
            if not temp_write.ok:
                result["error_code"] = "temporary_directory_unavailable"
                result["error_message"] = SAFE_ERRORS["temporary_directory_unavailable"]
                result["probable_cause"] = "El usuario autenticado no puede escribir en /tmp."

            raw_inventory = ssh.run(SSHOperation.DETECT_INVENTORY)
            inventory = parse_inventory_output(raw_inventory.stdout) if raw_inventory.ok else None
            if inventory is None or inventory.hostname == "unknown":
                result["error_code"] = "inventory_failed"
                result["error_message"] = SAFE_ERRORS["inventory_failed"]
                result["probable_cause"] = "El catálogo de inventario no pudo ejecutarse."
            else:
                inventory_payload = inventory.payload()
                result["discovered_inventory"] = inventory_payload
                result["hostname"] = inventory.hostname
                result["os"] = inventory.os
                result["os_version"] = inventory.os_version
                result["architecture"] = inventory.arch
                result["interfaces"] = inventory.interfaces
            if not result["privilege_ok"] and result["error_code"] is None:
                result["error_code"] = "permission_denied"
                result["error_message"] = SAFE_ERRORS["permission_denied"]
                result["probable_cause"] = "El usuario no tiene root ni sudo utilizable."
            return result
        except SSHServiceError as error:
            safe_code = "fingerprint_mismatch" if error.code == "host_key_changed" else error.code
            result["error_code"] = safe_code
            result["error_message"] = SAFE_ERRORS.get(safe_code, SAFE_ERRORS["internal_error"])
            result["probable_cause"] = error.probable_cause
            result["host_key_fingerprint"] = error.fingerprint or result["host_key_fingerprint"]
            if error.code == "host_key_new":
                result["reachable"] = True
                result["host_key_status"] = "new"
            elif error.code in {"host_key_changed", "fingerprint_mismatch"}:
                result["reachable"] = True
                result["host_key_status"] = "changed"
            elif error.code in {
                "wrong_password",
                "permission_denied",
                "password_authentication_disabled",
                "public_key_required",
            }:
                result["reachable"] = True
            return result
        finally:
            if ssh is not None:
                ssh.close()

    def discover(self, payload: OnboardingDiscoveryRequest) -> dict[str, object]:
        """Descubre un host sin crear registros ni ejecutar cambios remotos."""
        credentials = SSHCredentials(
            host=payload.host,
            port=payload.port,
            username=payload.username,
            password=payload.password,
            private_key=payload.private_key,
            expected_host_key_fingerprint=(
                payload.host_key_fingerprint if payload.confirm_host_key else None
            ),
        )
        result: dict[str, object] = {
            "reachable": False,
            "authentication_ok": False,
            "privilege_ok": False,
            "discovered_inventory": None,
            "host_key_fingerprint": payload.host_key_fingerprint,
            "host_key_status": "unknown",
            "detected_firewall": "unknown",
            "detected_interface": None,
            "link_speed_mbps": None,
            "exporter_status": "unknown",
            "exporter_version": None,
            "port_9100_status": "unknown",
            "systemd_available": False,
            "warnings": [],
            "blocking_errors": [],
            "error_code": None,
            "error_message": None,
            "probable_cause": None,
        }
        warnings = result["warnings"]
        blocking_errors = result["blocking_errors"]
        assert isinstance(warnings, list)
        assert isinstance(blocking_errors, list)
        ssh: SSHSession | None = None
        try:
            ssh = self._connection_factory(self._settings).connect(
                credentials, secrets.token_hex(8)
            )
            result["reachable"] = True
            result["authentication_ok"] = True
            result["host_key_status"] = ssh.host_key_status
            result["host_key_fingerprint"] = ssh.host_key_fingerprint

            requirements = ssh.run(SSHOperation.CHECK_REQUIREMENTS)
            result["systemd_available"] = "systemd=ok" in requirements.stdout
            if "port_9100=occupied" in requirements.stdout:
                result["port_9100_status"] = "occupied"
            elif "port_9100=free" in requirements.stdout:
                result["port_9100_status"] = "free"
            else:
                result["port_9100_status"] = "unknown"
            required_tools = ("systemctl", "curl", "tar", "sha256sum", "ss", "ip")
            missing_tools = [
                tool for tool in required_tools if f"{tool}=missing" in requirements.stdout
            ]
            if not requirements.ok or missing_tools or not result["systemd_available"]:
                blocking_errors.append("REQUIREMENTS_MISSING")
            if result["port_9100_status"] == "occupied":
                exporter_probe = ssh.run(SSHOperation.CHECK_EXPORTER)
                if not exporter_probe.ok:
                    blocking_errors.append("PORT_9100_OCCUPIED")

            privilege = ssh.run(SSHOperation.CHECK_SUDO)
            if privilege.ok and privilege.stdout.strip() == "0":
                result["privilege_ok"] = True
            else:
                privilege = ssh.run(
                    SSHOperation.CHECK_SUDO,
                    as_root=True,
                    sudo_password=payload.password,
                )
                result["privilege_ok"] = privilege.ok and privilege.stdout.strip() == "0"
            if not result["privilege_ok"]:
                blocking_errors.append("PRIVILEGE_REQUIRED")

            raw_inventory = ssh.run(SSHOperation.DETECT_INVENTORY)
            inventory = parse_inventory_output(raw_inventory.stdout) if raw_inventory.ok else None
            if inventory is None or inventory.hostname == "unknown" or not inventory.interfaces:
                blocking_errors.append("INVENTORY_UNAVAILABLE")
            else:
                result["discovered_inventory"] = inventory.payload()
                result["detected_interface"] = inventory.primary_interface
                result["link_speed_mbps"] = _interface_speed(inventory, inventory.primary_interface)

            exporter = ssh.run(SSHOperation.CHECK_EXPORTER)
            version_output = ssh.run(SSHOperation.CHECK_EXPORTER_VERSION)
            result["exporter_status"] = "healthy" if exporter.ok else "not_healthy"
            result["exporter_version"] = exporter_version_from_output(version_output.stdout)
            if not exporter.ok:
                warnings.append("NODE_EXPORTER_NOT_HEALTHY")

            firewall = ssh.run(
                SSHOperation.FIREWALL_STATUS,
                as_root=True,
                sudo_password=payload.password,
            )
            firewall_status = detect_firewall(firewall.stdout, self._settings.onboarding_monitor_ip)
            result["detected_firewall"] = firewall_status
            if firewall_status in {"unknown", "not_configured", "exposed", "partial"}:
                warnings.append("FIREWALL_REVIEW_REQUIRED")
            if inventory is not None and not inventory.primary_interface:
                warnings.append("PRIMARY_INTERFACE_NOT_DETECTED")
            return result
        except SSHServiceError as error:
            safe_code = "fingerprint_mismatch" if error.code == "host_key_changed" else error.code
            result["error_code"] = safe_code
            result["error_message"] = SAFE_ERRORS.get(safe_code, SAFE_ERRORS["internal_error"])
            result["probable_cause"] = error.probable_cause
            if error.code in {"host_key_new", "host_key_changed"}:
                result["reachable"] = True
                result["host_key_status"] = "new" if error.code == "host_key_new" else "changed"
                result["host_key_fingerprint"] = error.fingerprint
                blocking_errors.append(
                    "HOST_KEY_CONFIRMATION_REQUIRED"
                    if error.code == "host_key_new"
                    else "HOST_KEY_CHANGED"
                )
            elif error.code in {
                "authentication_failed",
                "wrong_password",
                "password_authentication_disabled",
                "public_key_required",
                "permission_denied",
            }:
                result["reachable"] = True
                result["host_key_status"] = "already_trusted"
                blocking_errors.append(error.code.upper())
            elif error.code == "invalid_private_key":
                blocking_errors.append("INVALID_PRIVATE_KEY")
            else:
                blocking_errors.append(error.code.upper())
            return result
        finally:
            if ssh is not None:
                ssh.close()

    def health(self, onboarding_id: int) -> dict[str, object]:
        """Devuelve salud consolidada sin volver a pedir una contraseña."""
        session = get_session_factory()()
        try:
            onboarding = OnboardingRepository(session).get(onboarding_id)
            if onboarding is None:
                raise ValueError("Onboarding no encontrado")
            server = ServerRepository(session).get(onboarding.server_id)
            if server is None:
                raise ValueError("Servidor no encontrado")
            snapshot = session.scalar(
                select(ServerInventorySnapshot)
                .where(ServerInventorySnapshot.server_id == server.id)
                .order_by(desc(ServerInventorySnapshot.captured_at))
                .limit(1)
            )
            latest_metric = session.scalar(
                select(ServerMetric)
                .where(ServerMetric.server_id == server.id)
                .order_by(desc(ServerMetric.collected_at))
                .limit(1)
            )
            now = datetime.now(UTC)
            last_scrape = latest_metric.collected_at if latest_metric else None
            if last_scrape is not None and last_scrape.tzinfo is None:
                last_scrape = last_scrape.replace(tzinfo=UTC)
            age = int((now - last_scrape).total_seconds()) if last_scrape else None
            freshness = (
                "fresh"
                if age is not None and age <= server.heartbeat_interval_seconds * 2
                else "stale"
            )
            metrics_available = latest_metric is not None
            prometheus_target_status = self._prometheus_target_status(server)
            prometheus = (
                "configured"
                if prometheus_target_status == "UP"
                else prometheus_target_status.lower()
            )
            ssh = "configured" if server.ssh_host_key_fingerprint else "unknown"
            node_exporter = server.node_exporter_status or "unknown"
            completed = onboarding.status == OnboardingStatus.COMPLETED.value
            provisioning = onboarding.status in {
                item.value
                for item in OnboardingStatus
                if item
                not in {
                    OnboardingStatus.COMPLETED,
                    OnboardingStatus.FAILED,
                    OnboardingStatus.CANCELLED,
                    OnboardingStatus.ROLLBACK_REQUIRED,
                }
            }
            if completed:
                overall = "healthy" if metrics_available and freshness == "fresh" else "degraded"
            elif provisioning:
                overall = "provisioning"
            elif onboarding.status == OnboardingStatus.FAILED.value:
                overall = "failed"
            else:
                overall = "unknown"
            return {
                "onboarding_status": onboarding.status,
                "ssh": ssh,
                "privilege": "configured" if completed else "unknown",
                "node_exporter": node_exporter,
                "exporter_version": server.node_exporter_version,
                "firewall": "configured" if completed else "unknown",
                "prometheus": prometheus,
                "prometheus_target_status": prometheus_target_status,
                "inventory": "available" if snapshot is not None else "missing",
                "network_interface": server.network_interface,
                "metrics_available": metrics_available,
                "last_scrape": last_scrape,
                "scrape_age_seconds": age,
                "freshness": freshness,
                "latency_ms": None,
                "overall_status": overall,
            }
        finally:
            session.close()

    def maintenance(
        self,
        server_id: int,
        action: MaintenanceAction,
        credentials: SSHCredentials,
        actor: str,
        target_version: str | None = None,
    ) -> dict[str, object]:
        """Ejecuta solo acciones del catálogo sobre componentes administrados."""
        session = get_session_factory()()
        ssh: SSHSession | None = None
        result: dict[str, object] = {
            "action": action.value,
            "status": "failed",
            "message": SAFE_ERRORS["maintenance_failed"],
            "exporter_status": "unknown",
            "exporter_version": None,
        }
        try:
            server = ServerRepository(session).get(server_id)
            if server is None or not server.hostname:
                result["message"] = "Servidor sin endpoint SSH configurado."
                return result
            expected = server.ssh_host_key_fingerprint
            ssh = self._connection_factory(self._settings).connect(
                SSHCredentials(
                    host=server.hostname,
                    port=server.ssh_port,
                    username=server.ssh_username or credentials.username,
                    password=credentials.password,
                    private_key=credentials.private_key,
                    expected_host_key_fingerprint=expected,
                ),
                secrets.token_hex(8),
            )
            if action is MaintenanceAction.DIAGNOSE:
                exporter = ssh.run(SSHOperation.CHECK_EXPORTER)
                firewall = ssh.run(
                    SSHOperation.FIREWALL_STATUS,
                    as_root=True,
                    sudo_password=credentials.password,
                )
                result["exporter_status"] = "healthy" if exporter.ok else "not_healthy"
                result["status"] = "ok"
                result["message"] = "Diagnóstico completado sin ejecutar cambios."
                result["exporter_version"] = exporter_version_from_output(
                    ssh.run(SSHOperation.CHECK_EXPORTER_VERSION).stdout
                )
                result["message"] = (
                    result["message"]
                    if detect_firewall(firewall.stdout, self._settings.onboarding_monitor_ip)
                    in {"restricted", "partial"}
                    else "Diagnóstico completado; revisar la configuración del firewall."
                )
            else:
                version = target_version or self._settings.node_exporter_version
                if action is MaintenanceAction.UPDATE and not version:
                    raise SSHServiceError(
                        "target_version_not_configured",
                        "La versión objetivo no está configurada.",
                    )
                common_env = {
                    "MONITOR_IP": self._settings.onboarding_monitor_ip,
                    "NODE_EXPORTER_VERSION": version or "",
                    "NODE_EXPORTER_PRIMARY_BASE_URL": self._settings.node_exporter_primary_base_url,
                    "NODE_EXPORTER_MIRROR_BASE_URL": (
                        self._settings.node_exporter_mirror_base_url or ""
                    ),
                    "NODE_EXPORTER_ALLOWED_SHA256": (
                        self._settings.node_exporter_allowed_sha256 or ""
                    ),
                    "SKIP_FIREWALL": "1",
                }
                script_name = {
                    MaintenanceAction.REPAIR: "repair-node-exporter.sh",
                    MaintenanceAction.UPDATE: "update-node-exporter.sh",
                    MaintenanceAction.REINSTALL: "install-node-exporter.sh",
                }[action]
                operation = ssh.run_script(
                    script_name, environment=common_env, sudo_password=credentials.password
                )
                if not operation.ok:
                    raise SSHServiceError("maintenance_failed", SAFE_ERRORS["maintenance_failed"])
                firewall = ssh.run_script(
                    "configure-node-exporter-firewall.sh",
                    environment={"MONITOR_IP": self._settings.onboarding_monitor_ip},
                    sudo_password=credentials.password,
                )
                if not firewall.ok:
                    raise SSHServiceError("firewall_failed", SAFE_ERRORS["firewall_failed"])
                exporter = ssh.run(SSHOperation.CHECK_EXPORTER)
                if not exporter.ok:
                    raise SSHServiceError("exporter_unhealthy", SAFE_ERRORS["exporter_unhealthy"])
                result["exporter_status"] = "healthy"
                result["exporter_version"] = exporter_version_from_output(
                    ssh.run(SSHOperation.CHECK_EXPORTER_VERSION).stdout
                )
                result["status"] = "ok"
                result["message"] = "Acción administrada completada y validada."
                server.node_exporter_status = "running"
                exporter_version = result["exporter_version"]
                server.node_exporter_version = (
                    exporter_version if isinstance(exporter_version, str) else None
                )
                server.ssh_host_key_fingerprint = (
                    ssh.host_key_fingerprint or server.ssh_host_key_fingerprint
                )
            onboarding = OnboardingRepository(session).latest_for_server(server_id)
            if onboarding is not None:
                OnboardingRepository(session).add_audit(
                    OnboardingAuditEvent(
                        onboarding_id=onboarding.id,
                        server_id=server.id,
                        actor=actor,
                        event=f"maintenance_{action.value}",
                        step="maintenance",
                        success=True,
                        detail_sanitized=str(result["message"]),
                        created_at=datetime.now(UTC),
                    )
                )
            session.commit()
            return result
        except SSHServiceError as error:
            result["message"] = SAFE_ERRORS.get(error.code, SAFE_ERRORS["maintenance_failed"])
            return result
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
            firewall_status = detect_firewall(firewall.stdout, self._settings.onboarding_monitor_ip)
            result["firewall"] = {
                "restricted": "PASS",
                "partial": "PARTIAL",
                "exposed": "FAIL",
                "not_configured": "FAIL",
                "unknown": "FAIL",
            }.get(firewall_status, "FAIL")
            inventory = parse_inventory_output(ssh.run(SSHOperation.DETECT_INVENTORY).stdout)
            result["network"] = (
                "PASS" if _network_is_valid(server.network_interface, inventory) else "FAIL"
            )
            if result["node_exporter"] != "PASS":
                errors.append("Node Exporter no responde")
            if result["firewall"] != "PASS":
                errors.append(
                    "Puerto 9100 expuesto o firewall administrado no confirmado"
                    if firewall_status == "exposed"
                    else "No se pudo confirmar el acceso restringido del firewall"
                )
            if result["network"] != "PASS":
                errors.append("La interfaz de red configurada no está disponible")
            prometheus_target_status = self._prometheus_target_status(server)
            result["prometheus_target_status"] = prometheus_target_status
            if prometheus_target_status == "UP":
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
                errors.append(
                    SAFE_ERRORS["prometheus_not_configured"]
                    if prometheus_target_status == "CONNECTION_FAILED" and not server.prometheus_url
                    else SAFE_ERRORS["prometheus_unavailable"]
                )
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
        return self._prometheus_target_status(server) == "UP"

    def _prometheus_target_status(self, server: Server) -> str:
        """Returns the public target state without exposing URL or token details."""
        if not server.prometheus_url or not server.hostname:
            return "CONNECTION_FAILED"
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
        try:
            probes = adapter.probe()
        except Exception:
            logger.warning("falló el diagnóstico del target Prometheus")
            return "CONNECTION_FAILED"
        if not probes or not probes[0].reachable:
            return "CONNECTION_FAILED"
        if probes[0].up_value is None:
            return "PENDING_SCRAPE"
        return "UP" if probes[0].up_value > 0 else "CONNECTION_FAILED"

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


def _interface_speed(inventory: RemoteInventory, interface: str | None) -> int | None:
    if interface is None:
        return None
    for item in inventory.interfaces:
        if item.get("name") == interface:
            value = item.get("speed_mbps")
            return value if isinstance(value, int) else None
    return None
