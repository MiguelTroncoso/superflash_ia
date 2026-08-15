#!/usr/bin/env bash
set -Eeuo pipefail
if [[ $EUID -ne 0 ]]; then echo "Ejecuta este script como root." >&2; exit 2; fi
[[ -x /usr/local/bin/node_exporter ]] || { echo "Node Exporter no está instalado." >&2; exit 1; }
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
MONITOR_IP="${MONITOR_IP:-178.104.98.19}"
NODE_EXPORTER_VERSION="${NODE_EXPORTER_VERSION:-}"
NODE_EXPORTER_PRIMARY_BASE_URL="${NODE_EXPORTER_PRIMARY_BASE_URL:-https://github.com/prometheus/node_exporter/releases/download}"
NODE_EXPORTER_MIRROR_BASE_URL="${NODE_EXPORTER_MIRROR_BASE_URL:-}"
NODE_EXPORTER_ALLOWED_SHA256="${NODE_EXPORTER_ALLOWED_SHA256:-}"
SKIP_FIREWALL=1 MONITOR_IP="$MONITOR_IP" NODE_EXPORTER_VERSION="$NODE_EXPORTER_VERSION" \
  NODE_EXPORTER_PRIMARY_BASE_URL="$NODE_EXPORTER_PRIMARY_BASE_URL" \
  NODE_EXPORTER_MIRROR_BASE_URL="$NODE_EXPORTER_MIRROR_BASE_URL" \
  NODE_EXPORTER_ALLOWED_SHA256="$NODE_EXPORTER_ALLOWED_SHA256" \
  "$SCRIPT_DIR/install-node-exporter.sh"
echo "Node Exporter actualizado y validado"
