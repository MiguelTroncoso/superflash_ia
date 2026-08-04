"""Pruebas estáticas de los bootstrap scripts de commissioning."""

from pathlib import Path

ROOT = Path(__file__).parents[1]
SCRIPT_NAMES = (
    "configure-node-exporter-firewall.sh",
    "install-node-exporter.sh",
    "update-node-exporter.sh",
    "remove-node-exporter.sh",
    "install-superflash-agent.sh",
    "update-superflash-agent.sh",
    "remove-superflash-agent.sh",
)


def test_commissioning_scripts_exist_and_are_executable() -> None:
    for name in SCRIPT_NAMES:
        script = ROOT / "scripts" / name
        assert script.is_file()
        assert script.stat().st_mode & 0o111
        assert script.read_text(encoding="utf-8").startswith("#!/usr/bin/env bash")


def test_node_exporter_installer_is_pinned_to_monitor_source_and_validates_release() -> None:
    content = (ROOT / "scripts/install-node-exporter.sh").read_text(encoding="utf-8")

    assert 'MONITOR_IP="${MONITOR_IP:-178.104.98.19}"' in content
    assert "releases/latest" in content
    assert "sha256sum -c" in content
    assert "ROLLBACK_NEEDED" in content
    assert "systemctl enable --now node_exporter" in content


def test_firewall_script_does_not_remove_existing_rules() -> None:
    content = (ROOT / "scripts/configure-node-exporter-firewall.sh").read_text(encoding="utf-8")

    assert "ufw" in content and "nft" in content and "iptables" in content
    assert "178.104.98.19" in content
    assert "rm -rf" not in content
    assert "iptables -C" in content


def test_agent_has_no_remote_connection_or_listener() -> None:
    content = (ROOT / "scripts/install-superflash-agent.sh").read_text(encoding="utf-8")

    assert "status.json" in content
    assert "PrivateNetwork=true" not in content
    assert "curl " not in content
    assert "nc " not in content
    assert "listen" not in content.lower()
