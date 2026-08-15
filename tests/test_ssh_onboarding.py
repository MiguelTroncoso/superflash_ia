import base64
import hashlib
from pathlib import Path

import paramiko
import pytest

from app.models.onboarding import ServerOnboarding
from app.schemas.onboarding import OnboardingStartRequest
from app.services.onboarding_service import OnboardingService
from app.services.ssh_service import (
    FingerprintHostKeyPolicy,
    RemoteInventory,
    SSHOperation,
    SSHServiceError,
    detect_firewall,
    exporter_version_from_output,
    parse_inventory_output,
)


def test_inventory_parser_detects_public_ip_and_primary_interface() -> None:
    output = """hostname=live-1
os=Ubuntu 22.04 22.04
os_version=22.04
arch=x86_64
ip_addresses=10.0.0.4,107.150.53.26
interfaces=lo|127.0.0.1;eno1|107.150.53.26/24;
interface_speeds=eno1|1000;
primary_interface=eno1
memory_bytes=8589934592
"""

    inventory = parse_inventory_output(output)

    assert inventory.public_ip == "107.150.53.26"
    assert inventory.primary_interface == "eno1"
    assert inventory.interfaces[-1]["speed_mbps"] == 1000
    assert inventory.memory_bytes == 8589934592
    assert inventory.os_version == "22.04"


def test_inventory_fingerprint_ignores_dynamic_uptime_fields() -> None:
    first = RemoteInventory(hostname="live-1", arch="x86_64", uptime_seconds=10)
    second = RemoteInventory(hostname="live-1", arch="x86_64", uptime_seconds=20)

    assert first.fingerprint() == second.fingerprint()


def test_ssh_operation_catalog_is_closed() -> None:
    assert set(SSHOperation) == {
        SSHOperation.CHECK_SUDO,
        SSHOperation.DETECT_INVENTORY,
        SSHOperation.CHECK_REQUIREMENTS,
        SSHOperation.CHECK_EXPORTER,
        SSHOperation.CHECK_EXPORTER_VERSION,
        SSHOperation.SERVICE_STATUS,
        SSHOperation.FIREWALL_STATUS,
    }


def test_firewall_and_exporter_outputs_are_reduced_to_safe_statuses() -> None:
    assert exporter_version_from_output("node_exporter, version 1.8.2 (branch: HEAD)") == "1.8.2"
    assert (
        detect_firewall(
            "9100 ALLOW IN 178.104.98.19\n9100 DENY IN Anywhere # superflash-node-exporter",
            "178.104.98.19",
        )
        == "restricted"
    )
    assert detect_firewall("tcp dport 9100 accept", "178.104.98.19") == "exposed"


def test_host_key_policy_requires_confirmation_and_accepts_exact_fingerprint() -> None:
    key = paramiko.RSAKey.generate(1024)
    digest = base64.b64encode(hashlib.sha256(key.asbytes()).digest()).decode().rstrip("=")
    fingerprint = f"SHA256:{digest}"
    client = type("Client", (), {"get_host_keys": lambda self: paramiko.HostKeys()})()

    try:
        FingerprintHostKeyPolicy(None).missing_host_key(client, "server", key)
    except SSHServiceError as error:
        assert error.code == "host_key_new"
        assert error.fingerprint == fingerprint
    else:
        raise AssertionError("a new host key must require explicit confirmation")

    with pytest.raises(SSHServiceError, match="huella") as changed:
        FingerprintHostKeyPolicy("SHA256:other").missing_host_key(client, "server", key)
    assert changed.value.code == "host_key_changed"

    policy = FingerprintHostKeyPolicy(fingerprint)
    policy.missing_host_key(client, "server", key)
    assert policy.fingerprint == fingerprint


def test_onboarding_contract_never_models_secrets_for_persistence() -> None:
    payload = OnboardingStartRequest(
        name="Live 1",
        ip="107.150.53.26",
        ssh_username="root",
        auth_method="private_key",
        private_key="synthetic-private-key-fixture",
        host_key_fingerprint="SHA256:test-fingerprint",
    )

    assert "password" not in {column.name for column in ServerOnboarding.__table__.columns}
    assert "private_key" not in {column.name for column in ServerOnboarding.__table__.columns}
    assert payload.private_key is not None


def test_provisioning_scripts_are_local_allowlisted_and_do_not_flush_firewall() -> None:
    scripts = Path("scripts")
    text = "\n".join(path.read_text(encoding="utf-8") for path in scripts.glob("*.sh"))

    assert "iptables -F" not in text
    assert "nft flush ruleset" not in text
    assert "178.104.98.19" in (scripts / "configure-node-exporter-firewall.sh").read_text()
    assert all(path.stat().st_mode & 0o111 for path in scripts.glob("*.sh"))


def test_onboarding_response_does_not_return_ephemeral_ssh_secret(client, monkeypatch) -> None:
    monkeypatch.setattr(OnboardingService, "run", lambda *args, **kwargs: None)
    secret = "synthetic-private-key-fixture"

    response = client.post(
        "/api/v1/onboarding",
        json={
            "name": "Live 1",
            "ip": "203.0.113.10",
            "ssh_username": "root",
            "auth_method": "private_key",
            "private_key": secret,
            "host_key_fingerprint": "SHA256:test-fingerprint",
        },
    )

    assert response.status_code == 202
    assert secret not in response.text
    assert "private_key" not in response.json()


def test_discovery_response_is_sanitized_and_does_not_persist_credentials(
    client, monkeypatch
) -> None:
    secret = "temporary-password-not-returned"
    monkeypatch.setattr(
        OnboardingService,
        "discover",
        lambda *_args, **_kwargs: {
            "reachable": True,
            "authentication_ok": True,
            "privilege_ok": True,
            "discovered_inventory": {"hostname": "edge-1", "interfaces": []},
            "host_key_fingerprint": "SHA256:approved",
            "host_key_status": "confirmed",
            "detected_firewall": "restricted",
            "detected_interface": "ens18",
            "link_speed_mbps": 1000,
            "exporter_status": "healthy",
            "exporter_version": "1.8.2",
            "port_9100_status": "occupied",
            "systemd_available": True,
            "warnings": [],
            "blocking_errors": [],
        },
    )

    response = client.post(
        "/api/v1/onboarding/discover",
        json={
            "host": "203.0.113.10",
            "port": 22,
            "username": "root",
            "auth_method": "password",
            "password": secret,
        },
    )

    assert response.status_code == 200
    assert secret not in response.text
    assert "stderr" not in response.json()
