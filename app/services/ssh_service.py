"""Catálogo cerrado de operaciones SSH para el onboarding.

Este módulo no acepta comandos provenientes del navegador. Todas las órdenes
remotas están declaradas en ``_OPERATION_COMMANDS`` y los scripts que pueden
subirse están en ``_ALLOWED_SCRIPTS``.
"""

from __future__ import annotations

import base64
import hashlib
import ipaddress
import json
import logging
import re
import shlex
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

import paramiko

from app.core.config import Settings

logger = logging.getLogger(__name__)


class SSHOperation(StrEnum):
    CHECK_SUDO = "check_sudo"
    DETECT_INVENTORY = "detect_inventory"
    CHECK_REQUIREMENTS = "check_requirements"
    CHECK_EXPORTER = "check_exporter"
    CHECK_EXPORTER_VERSION = "check_exporter_version"
    SERVICE_STATUS = "service_status"
    FIREWALL_STATUS = "firewall_status"


_OPERATION_COMMANDS: dict[SSHOperation, str] = {
    SSHOperation.CHECK_SUDO: "id -u",
    SSHOperation.DETECT_INVENTORY: (
        "set -eu; "
        "printf 'hostname=%s\\n' \"$(hostname)\"; "
        "printf 'os=%s\\n' \"$(. /etc/os-release 2>/dev/null; printf '%s %s' "
        '"${PRETTY_NAME:-unknown}" "${VERSION_ID:-}")"; '
        "printf 'os_version=%s\\n' \"$(. /etc/os-release 2>/dev/null; "
        'printf \'%s\' "${VERSION_ID:-unknown}")"; '
        "printf 'arch=%s\\n' \"$(uname -m)\"; "
        "printf 'kernel=%s\\n' \"$(uname -r)\"; "
        "printf 'ip_addresses=%s\\n' \"$(hostname -I 2>/dev/null | tr ' ' ',' | sed 's/,$//')\"; "
        "printf 'cpu_model=%s\\n' \"$(LC_ALL=C lscpu 2>/dev/null | "
        'awk -F: \'/Model name/{gsub(/^ +| +$/,"",$2); print $2; exit}\')"; '
        "printf 'sockets=%s\\n' \"$(lscpu 2>/dev/null | awk -F: '/Socket\\(s\\)/{gsub(/^ +| +$/,\"\",$2); print $2; exit}')\"; "  # noqa: E501
        "printf 'cores=%s\\n' \"$(nproc --all 2>/dev/null || printf unknown)\"; "
        "printf 'threads=%s\\n' \"$(lscpu 2>/dev/null | awk -F: '/CPU\\(s\\)/{gsub(/^ +| +$/,\"\",$2); print $2; exit}')\"; "  # noqa: E501
        "printf 'memory_bytes=%s\\n' \"$(awk '/MemTotal/{print $2 * 1024; exit}' /proc/meminfo 2>/dev/null || printf 0)\"; "  # noqa: E501
        "printf 'swap_bytes=%s\\n' \"$(awk '/SwapTotal/{print $2 * 1024; exit}' /proc/meminfo 2>/dev/null || printf 0)\"; "  # noqa: E501
        "printf 'interfaces=%s\\n' \"$(ip -br addr 2>/dev/null | awk '{print $1\"|\"$3}' | tr '\\n' ';')\"; "  # noqa: E501
        "printf 'interface_speeds=%s\\n' \"$(for path in /sys/class/net/*/speed; do "
        '[ -r "$path" ] || continue; iface="${path%/speed}"; iface="${iface##*/}"; '
        'speed=$(cat "$path" 2>/dev/null || printf 0); printf \'%s|%s;\' "$iface" "$speed"; '
        'done)"; '
        "printf 'disks=%s\\n' \"$(lsblk -b -dn -o NAME,SIZE,TYPE,MODEL 2>/dev/null | tr '\\n' ';')\"; "  # noqa: E501
        "printf 'virtualization=%s\\n' \"$(systemd-detect-virt 2>/dev/null || printf none)\"; "
        "printf 'uptime_seconds=%s\\n' \"$(awk '{print int($1)}' /proc/uptime 2>/dev/null || printf 0)\"; "  # noqa: E501
        "printf 'last_reboot=%s\\n' \"$(who -b 2>/dev/null | sed 's/^ *//' || true)\"; "
        "printf 'primary_interface=%s\\n' \"$(ip route show default 2>/dev/null | awk 'NR==1{print $5; exit}')\""  # noqa: E501
    ),
    SSHOperation.CHECK_REQUIREMENTS: (
        "set +e; "
        "for tool in systemctl curl tar sha256sum ss ip; do "
        'if command -v "$tool" >/dev/null 2>&1; then printf \'%s=ok\\n\' "$tool"; '
        "else printf '%s=missing\\n' \"$tool\"; fi; done; "
        "if [ -d /run/systemd/system ]; then printf 'systemd=ok\\n'; "
        "else printf 'systemd=missing\\n'; fi; "
        "if ss -ltn 2>/dev/null | grep -Eq '[:.]9100[[:space:]]'; then "
        "printf 'port_9100=occupied\\n'; else printf 'port_9100=free\\n'; fi"
    ),
    SSHOperation.CHECK_EXPORTER: (
        "curl --fail --silent --show-error --max-time 5 "
        "http://127.0.0.1:9100/metrics | grep -q '^# HELP'"
    ),
    SSHOperation.CHECK_EXPORTER_VERSION: (
        "(/usr/local/bin/node_exporter --version 2>/dev/null || "
        "node_exporter --version 2>/dev/null || true) | head -n 1"
    ),
    SSHOperation.SERVICE_STATUS: (
        "set +e; printf 'active=%s\\n' \"$(systemctl is-active node_exporter 2>/dev/null || true)\"; "  # noqa: E501
        "printf 'enabled=%s\\n' \"$(systemctl is-enabled node_exporter 2>/dev/null || true)\""
    ),
    SSHOperation.FIREWALL_STATUS: (
        "set +e; if command -v ufw >/dev/null 2>&1; then ufw status verbose; fi; "
        "if command -v nft >/dev/null 2>&1; then nft list table inet superflash_node_exporter 2>/dev/null; fi; "  # noqa: E501
        "if command -v iptables >/dev/null 2>&1; then iptables -S INPUT 2>/dev/null | "
        "grep -E '9100|superflash-node-exporter' || true; fi"
    ),
}

_ALLOWED_SCRIPTS = frozenset(
    {
        "install-node-exporter.sh",
        "update-node-exporter.sh",
        "remove-node-exporter.sh",
        "repair-node-exporter.sh",
        "configure-node-exporter-firewall.sh",
        "install-superflash-agent.sh",
        "update-superflash-agent.sh",
        "remove-superflash-agent.sh",
    }
)


@dataclass(frozen=True)
class SSHCredentials:
    host: str
    port: int
    username: str
    password: str | None = None
    private_key: str | None = None
    expected_host_key_fingerprint: str | None = None


@dataclass(frozen=True)
class SSHCommandResult:
    operation: str
    exit_code: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.exit_code == 0


@dataclass
class RemoteInventory:
    hostname: str = "unknown"
    os: str = "unknown"
    os_version: str = "unknown"
    arch: str = "unknown"
    kernel: str = "unknown"
    ip_addresses: list[str] = field(default_factory=list)
    public_ip: str | None = None
    cpu_model: str | None = None
    sockets: int | None = None
    cores: int | None = None
    threads: int | None = None
    memory_bytes: int | None = None
    swap_bytes: int | None = None
    interfaces: list[dict[str, str | int | None]] = field(default_factory=list)
    disks: list[dict[str, str | int | None]] = field(default_factory=list)
    primary_interface: str | None = None
    virtualization: str | None = None
    uptime_seconds: int | None = None
    last_reboot: str | None = None

    def payload(self) -> dict[str, object]:
        return {
            "hostname": self.hostname,
            "os": self.os,
            "os_version": self.os_version,
            "arch": self.arch,
            "kernel": self.kernel,
            "ip_addresses": self.ip_addresses,
            "public_ip": self.public_ip,
            "cpu": {
                "model": self.cpu_model,
                "sockets": self.sockets,
                "cores": self.cores,
                "threads": self.threads,
            },
            "memory_bytes": self.memory_bytes,
            "swap_bytes": self.swap_bytes,
            "interfaces": self.interfaces,
            "disks": self.disks,
            "primary_interface": self.primary_interface,
            "virtualization": self.virtualization,
            "uptime_seconds": self.uptime_seconds,
            "last_reboot": self.last_reboot,
        }

    def fingerprint(self) -> str:
        fingerprint_payload = self.payload()
        fingerprint_payload.pop("uptime_seconds", None)
        fingerprint_payload.pop("last_reboot", None)
        raw = json.dumps(fingerprint_payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class SSHServiceError(RuntimeError):
    """Error seguro con código estable, sin detalles de credenciales/host key."""

    def __init__(self, code: str, message: str, *, fingerprint: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.fingerprint = fingerprint


def parse_inventory_output(output: str) -> RemoteInventory:
    """Parsea únicamente el formato de key/value producido por el catálogo."""
    values: dict[str, str] = {}
    for line in output.splitlines():
        key, separator, value = line.partition("=")
        if separator:
            values[key.strip()] = value.strip()[:2000]

    def integer(name: str) -> int | None:
        try:
            value = int(values.get(name, ""))
        except ValueError:
            return None
        return value if value >= 0 else None

    addresses = [value for value in values.get("ip_addresses", "").split(",") if value]
    public_ip = next(
        (value for value in addresses if _is_public_ip(value)),
        None,
    )
    interfaces = _parse_interfaces(values.get("interfaces", ""), values.get("interface_speeds", ""))
    disks = _parse_disks(values.get("disks", ""))
    return RemoteInventory(
        hostname=values.get("hostname", "unknown") or "unknown",
        os=values.get("os", "unknown") or "unknown",
        os_version=values.get("os_version", "unknown") or "unknown",
        arch=values.get("arch", "unknown") or "unknown",
        kernel=values.get("kernel", "unknown") or "unknown",
        ip_addresses=addresses,
        public_ip=public_ip,
        cpu_model=values.get("cpu_model") or None,
        sockets=integer("sockets"),
        cores=integer("cores"),
        threads=integer("threads"),
        memory_bytes=integer("memory_bytes"),
        swap_bytes=integer("swap_bytes"),
        interfaces=interfaces,
        disks=disks,
        primary_interface=values.get("primary_interface") or None,
        virtualization=values.get("virtualization") or None,
        uptime_seconds=integer("uptime_seconds"),
        last_reboot=values.get("last_reboot") or None,
    )


def _is_public_ip(value: str) -> bool:
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return False
    return address.is_global


def _parse_interfaces(raw_interfaces: str, raw_speeds: str) -> list[dict[str, str | int | None]]:
    speeds: dict[str, int | None] = {}
    for item in raw_speeds.split(";"):
        name, separator, raw_speed = item.partition("|")
        if not separator or not name:
            continue
        try:
            speed = int(raw_speed)
        except ValueError:
            speed = None
        speeds[name] = speed if speed is not None and speed >= 0 else None
    result: list[dict[str, str | int | None]] = []
    for item in raw_interfaces.split(";"):
        name, separator, addresses = item.partition("|")
        if not separator or not name:
            continue
        result.append({"name": name, "addresses": addresses, "speed_mbps": speeds.get(name)})
    return result


def _parse_disks(raw_disks: str) -> list[dict[str, str | int | None]]:
    result: list[dict[str, str | int | None]] = []
    for item in raw_disks.split(";"):
        parts = item.split(None, 3)
        if len(parts) < 3:
            continue
        size: int | None
        try:
            size = int(parts[1])
        except ValueError:
            size = None
        result.append(
            {
                "name": parts[0],
                "size_bytes": size,
                "type": parts[2],
                "model": parts[3] if len(parts) == 4 and parts[3] else None,
            }
        )
    return result


class SSHSession:
    """Sesión autenticada con ejecución limitada al catálogo."""

    def __init__(
        self,
        client: Any,
        settings: Settings,
        job_token: str,
        username: str,
        host_key_fingerprint: str | None = None,
    ) -> None:
        self._client = client
        self._settings = settings
        self._job_token = job_token
        self._username = username
        self.host_key_fingerprint = host_key_fingerprint

    def run(
        self,
        operation: SSHOperation,
        *,
        as_root: bool = False,
        sudo_password: str | None = None,
    ) -> SSHCommandResult:
        command = _OPERATION_COMMANDS[operation]
        if as_root and self._username != "root":
            command = _sudo_command(command)
        try:
            stdin, stdout, stderr = self._client.exec_command(
                command, timeout=self._settings.ssh_command_timeout_seconds
            )
            if as_root and sudo_password:
                stdin.write(f"{sudo_password}\n")
                stdin.flush()
            exit_code = int(stdout.channel.recv_exit_status())
            return SSHCommandResult(
                operation=operation.value,
                exit_code=exit_code,
                stdout=_truncate(stdout.read().decode("utf-8", "replace")),
                stderr=_truncate(stderr.read().decode("utf-8", "replace")),
            )
        except (OSError, EOFError, TimeoutError) as error:
            raise SSHServiceError(
                "command_failed", "No se pudo completar la comprobación remota"
            ) from error

    def run_script(
        self,
        script_name: str,
        *,
        environment: dict[str, str] | None = None,
        as_root: bool = True,
        sudo_password: str | None = None,
    ) -> SSHCommandResult:
        if script_name not in _ALLOWED_SCRIPTS:
            raise SSHServiceError("operation_not_allowed", "Script remoto no permitido")
        script_path = Path(__file__).resolve().parents[2] / "scripts" / script_name
        if not script_path.is_file():
            raise SSHServiceError("script_missing", "Script de provisioning no disponible")
        remote_path = f"/tmp/superflash-onboarding-{self._job_token}-{script_name}"
        try:
            sftp = self._client.open_sftp()
            with sftp.file(remote_path, "w") as remote_file:
                remote_file.write(script_path.read_text(encoding="utf-8"))
            sftp.chmod(remote_path, 0o700)
            sftp.close()
            env = " ".join(
                f"{key}={shlex.quote(value)}"
                for key, value in (environment or {}).items()
                if key
                in {
                    "MONITOR_IP",
                    "NODE_EXPORTER_VERSION",
                    "NODE_EXPORTER_PRIMARY_BASE_URL",
                    "NODE_EXPORTER_MIRROR_BASE_URL",
                    "NODE_EXPORTER_ALLOWED_SHA256",
                    "SKIP_FIREWALL",
                    "FIREWALL_ACTION",
                }
            )
            command = f"{env} bash {shlex.quote(remote_path)}".strip()
            if as_root and self._username != "root":
                command = _sudo_command(command)
            stdin, stdout, stderr = self._client.exec_command(
                command, timeout=self._settings.ssh_command_timeout_seconds * 4
            )
            if as_root and sudo_password:
                stdin.write(f"{sudo_password}\n")
                stdin.flush()
            exit_code = int(stdout.channel.recv_exit_status())
            return SSHCommandResult(
                operation=f"script:{script_name}",
                exit_code=exit_code,
                stdout=_truncate(stdout.read().decode("utf-8", "replace")),
                stderr=_truncate(stderr.read().decode("utf-8", "replace")),
            )
        except (OSError, EOFError, TimeoutError) as error:
            raise SSHServiceError(
                "script_failed", "No se pudo completar la instalación remota"
            ) from error
        finally:
            try:
                sftp = self._client.open_sftp()
                sftp.remove(remote_path)
                sftp.close()
            except (OSError, EOFError):
                logger.debug("no se pudo limpiar el script temporal del onboarding")

    def close(self) -> None:
        self._client.close()


def _sudo_command(command: str) -> str:
    return f"sudo -S -p '' -- sh -c {shlex.quote(command)}"


def _truncate(value: str, limit: int = 8_000) -> str:
    return value[:limit]


class FingerprintHostKeyPolicy(paramiko.MissingHostKeyPolicy):
    """Acepta una host key nueva únicamente con confirmación explícita."""

    def __init__(self, expected_fingerprint: str | None) -> None:
        self.expected_fingerprint = expected_fingerprint
        self.fingerprint: str | None = None

    def missing_host_key(self, client: Any, hostname: str, key: Any) -> None:
        fingerprint = ssh_key_fingerprint(key)
        self.fingerprint = fingerprint
        if not self.expected_fingerprint:
            raise SSHServiceError(
                "host_key_new",
                "Se requiere confirmar la huella de la host key SSH.",
                fingerprint=fingerprint,
            )
        if not _fingerprints_equal(self.expected_fingerprint, fingerprint):
            raise SSHServiceError(
                "host_key_changed",
                "La host key SSH no coincide con la huella confirmada.",
                fingerprint=fingerprint,
            )
        client.get_host_keys().add(hostname, key.get_name(), key)


def ssh_key_fingerprint(key: Any) -> str:
    """Calcula una huella OpenSSH SHA256 sin registrar material de la clave."""
    digest = hashlib.sha256(key.asbytes()).digest()
    return f"SHA256:{base64.b64encode(digest).decode('ascii').rstrip('=')}"


def private_key_fingerprint(private_key: str) -> str:
    """Calcula solo la huella de una clave privada mantenida en memoria."""
    return ssh_key_fingerprint(_parse_private_key(private_key))


def _fingerprints_equal(left: str, right: str) -> bool:
    return left.strip().removeprefix("SHA256:") == right.strip().removeprefix("SHA256:")


def exporter_version_from_output(output: str) -> str | None:
    match = re.search(r"node_exporter(?:,)? version (v?[0-9]+(?:\.[0-9]+){1,3})", output)
    return match.group(1) if match else None


def detect_firewall(output: str, monitor_ip: str) -> str:
    """Clasifica únicamente reglas visibles, sin exponer su contenido al cliente."""
    normalized = output.lower()
    if not output.strip():
        return "unknown"
    has_managed_allow = monitor_ip in output and "9100" in output
    has_managed_deny = "superflash-node-exporter" in normalized and (
        "deny" in normalized or "drop" in normalized
    )
    if has_managed_allow and has_managed_deny:
        return "restricted"
    if has_managed_allow:
        return "partial"
    if "9100" in output:
        return "exposed"
    return "not_configured"


class SSHConnectionService:
    """Conecta con host-key validation, timeout y retries acotados."""

    def __init__(
        self,
        settings: Settings,
        client_factory: Callable[[], Any] | None = None,
    ) -> None:
        self._settings = settings
        self._client_factory = client_factory or paramiko.SSHClient

    def connect(self, credentials: SSHCredentials, job_token: str) -> SSHSession:
        last_error: Exception | None = None
        for attempt in range(self._settings.ssh_retry_count + 1):
            client = self._client_factory()
            try:
                policy = self._configure_host_keys(
                    client, credentials.expected_host_key_fingerprint
                )
                kwargs: dict[str, Any] = {
                    "hostname": credentials.host,
                    "port": credentials.port,
                    "username": credentials.username,
                    "timeout": self._settings.ssh_connect_timeout_seconds,
                    "auth_timeout": self._settings.ssh_connect_timeout_seconds,
                    "banner_timeout": self._settings.ssh_connect_timeout_seconds,
                    "allow_agent": False,
                    "look_for_keys": False,
                }
                if credentials.private_key:
                    kwargs["pkey"] = _parse_private_key(credentials.private_key)
                else:
                    kwargs["password"] = credentials.password
                client.connect(**kwargs)
                remote_fingerprint = policy.fingerprint or credentials.expected_host_key_fingerprint
                if remote_fingerprint is None:
                    try:
                        transport = client.get_transport()
                        if transport is None:
                            raise AttributeError("SSH transport unavailable")
                        remote_key = transport.get_remote_server_key()
                        remote_fingerprint = ssh_key_fingerprint(remote_key)
                    except (AttributeError, TypeError, paramiko.SSHException):
                        remote_fingerprint = None
                return SSHSession(
                    client,
                    self._settings,
                    job_token,
                    credentials.username,
                    remote_fingerprint,
                )
            except SSHServiceError:
                client.close()
                raise
            except paramiko.AuthenticationException as error:
                client.close()
                raise SSHServiceError(
                    "authentication_failed", "La autenticación SSH fue rechazada"
                ) from error
            except paramiko.BadHostKeyException as error:
                client.close()
                raise SSHServiceError(
                    "host_key_changed", "La host key SSH no coincide con la registrada"
                ) from error
            except paramiko.ssh_exception.SSHException as error:
                last_error = error
                client.close()
            except (OSError, TimeoutError) as error:
                last_error = error
                client.close()
            if attempt < self._settings.ssh_retry_count:
                continue
        raise SSHServiceError(
            "connection_failed", "No se pudo conectar por SSH al servidor"
        ) from last_error

    def _configure_host_keys(
        self, client: Any, expected_fingerprint: str | None
    ) -> FingerprintHostKeyPolicy:
        client.load_system_host_keys()
        known_hosts = Path(self._settings.ssh_known_hosts_file)
        if known_hosts.is_file():
            client.load_host_keys(str(known_hosts))
        policy = FingerprintHostKeyPolicy(expected_fingerprint)
        client.set_missing_host_key_policy(policy)
        return policy


def _parse_private_key(private_key: str) -> Any:
    from io import StringIO

    errors: list[Exception] = []
    for key_type in (
        paramiko.RSAKey,
        paramiko.Ed25519Key,
        paramiko.ECDSAKey,
    ):
        try:
            return key_type.from_private_key(StringIO(private_key))
        except (paramiko.SSHException, ValueError) as error:
            errors.append(error)
    raise SSHServiceError("invalid_private_key", "La clave privada SSH no es válida") from errors[
        -1
    ]
