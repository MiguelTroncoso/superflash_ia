#!/usr/bin/env bash
set -Eeuo pipefail
if [[ $EUID -ne 0 ]]; then echo "Ejecuta este script como root." >&2; exit 2; fi
[[ -x /usr/local/bin/node_exporter ]] || { echo "Node Exporter no está instalado." >&2; exit 1; }
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
MONITOR_IP="${MONITOR_IP:-178.104.98.19}"
NODE_EXPORTER_VERSION="${NODE_EXPORTER_VERSION:-}"
SKIP_FIREWALL=1 MONITOR_IP="$MONITOR_IP" NODE_EXPORTER_VERSION="$NODE_EXPORTER_VERSION" \
  "$SCRIPT_DIR/install-node-exporter.sh"
echo "Node Exporter actualizado y validado"
