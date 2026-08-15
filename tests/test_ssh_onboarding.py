from pathlib import Path

from app.models.onboarding import ServerOnboarding
from app.schemas.onboarding import OnboardingStartRequest
from app.services.onboarding_service import OnboardingService
from app.services.ssh_service import RemoteInventory, SSHOperation, parse_inventory_output


def test_inventory_parser_detects_public_ip_and_primary_interface() -> None:
    output = """hostname=live-1
os=Ubuntu 22.04 22.04
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


def test_onboarding_contract_never_models_secrets_for_persistence() -> None:
    payload = OnboardingStartRequest(
        name="Live 1",
        ip="107.150.53.26",
        ssh_username="root",
        auth_method="private_key",
        private_key="-----BEGIN PRIVATE KEY-----secret-----END PRIVATE KEY-----",
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
    secret = "-----BEGIN PRIVATE KEY-----never-return-----END PRIVATE KEY-----"

    response = client.post(
        "/api/v1/onboarding",
        json={
            "name": "Live 1",
            "ip": "203.0.113.10",
            "ssh_username": "root",
            "auth_method": "private_key",
            "private_key": secret,
        },
    )

    assert response.status_code == 202
    assert secret not in response.text
    assert "private_key" not in response.json()
