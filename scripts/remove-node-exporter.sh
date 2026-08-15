#!/usr/bin/env bash
set -Eeuo pipefail
if [[ $EUID -ne 0 ]]; then echo "Ejecuta este script como root." >&2; exit 2; fi
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
MONITOR_IP="${MONITOR_IP:-178.104.98.19}"
systemctl disable --now node_exporter >/dev/null 2>&1 || true
rm -f /etc/systemd/system/node_exporter.service /usr/local/bin/node_exporter
systemctl daemon-reload
MONITOR_IP="$MONITOR_IP" FIREWALL_ACTION=remove "$SCRIPT_DIR/configure-node-exporter-firewall.sh" || true
echo "Node Exporter eliminado; solo se retiraron reglas gestionadas por SuperFlash."
