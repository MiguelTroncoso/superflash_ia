#!/usr/bin/env bash
set -Eeuo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "Ejecuta este script como root." >&2
  exit 2
fi
command -v curl >/dev/null || { echo "curl es requerido" >&2; exit 2; }
command -v tar >/dev/null || { echo "tar es requerido" >&2; exit 2; }
command -v sha256sum >/dev/null || { echo "sha256sum es requerido" >&2; exit 2; }
command -v systemctl >/dev/null || { echo "systemd es requerido" >&2; exit 2; }

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="${INSTALL_DIR:-/usr/local/bin}"
SERVICE_FILE="/etc/systemd/system/node_exporter.service"
MONITOR_IP="${MONITOR_IP:-178.104.98.19}"
SKIP_FIREWALL="${SKIP_FIREWALL:-0}"
TMP_DIR="$(mktemp -d)"
BACKUP_BINARY="${INSTALL_DIR}/node_exporter.sprint62.bak"
BACKUP_UNIT="${SERVICE_FILE}.sprint62.bak"
NEW_BINARY="${INSTALL_DIR}/node_exporter.sprint62.new"
ROLLBACK_NEEDED=0
cleanup() { rm -rf "$TMP_DIR"; rm -f "$NEW_BINARY"; }
rollback() {
  if [[ $ROLLBACK_NEEDED -eq 1 ]]; then
    systemctl stop node_exporter >/dev/null 2>&1 || true
    if [[ -f "$BACKUP_BINARY" ]]; then install -m 0755 "$BACKUP_BINARY" "${INSTALL_DIR}/node_exporter"; else rm -f "${INSTALL_DIR}/node_exporter"; fi
    if [[ -f "$BACKUP_UNIT" ]]; then install -m 0644 "$BACKUP_UNIT" "$SERVICE_FILE"; else rm -f "$SERVICE_FILE"; fi
    systemctl daemon-reload >/dev/null 2>&1 || true
    systemctl enable --now node_exporter >/dev/null 2>&1 || true
    echo "Instalación revertida tras un fallo de validación." >&2
  fi
}
trap 'rollback; cleanup' EXIT

case "$(uname -m)" in
  x86_64) ARCH=amd64 ;;
  aarch64) ARCH=arm64 ;;
  armv7l|armv7) ARCH=armv7 ;;
  *) echo "Arquitectura no soportada: $(uname -m)" >&2; exit 2 ;;
esac

RELEASE_JSON="$(curl --fail --silent --show-error --location https://api.github.com/repos/prometheus/node_exporter/releases/latest)"
VERSION="$(printf '%s' "$RELEASE_JSON" | sed -n 's/.*"tag_name"[[:space:]]*:[[:space:]]*"v\([^"]*\)".*/\1/p' | head -n 1)"
[[ -n "$VERSION" ]] || { echo "No se pudo determinar la versión estable." >&2; exit 1; }
ARCHIVE="node_exporter-${VERSION}.linux-${ARCH}.tar.gz"
BASE_URL="https://github.com/prometheus/node_exporter/releases/download/v${VERSION}"
curl --fail --silent --show-error --location -o "$TMP_DIR/$ARCHIVE" "$BASE_URL/$ARCHIVE"
curl --fail --silent --show-error --location -o "$TMP_DIR/sha256sums.txt" "$BASE_URL/sha256sums.txt"
(cd "$TMP_DIR" && grep "  $ARCHIVE$" sha256sums.txt | sha256sum -c -)
tar -xzf "$TMP_DIR/$ARCHIVE" -C "$TMP_DIR"

id node_exporter >/dev/null 2>&1 || useradd --system --no-create-home --shell /usr/sbin/nologin node_exporter
if [[ -f "${INSTALL_DIR}/node_exporter" ]]; then install -m 0755 "${INSTALL_DIR}/node_exporter" "$BACKUP_BINARY"; fi
if [[ -f "$SERVICE_FILE" ]]; then install -m 0644 "$SERVICE_FILE" "$BACKUP_UNIT"; fi
install -m 0755 "$TMP_DIR/node_exporter-${VERSION}.linux-${ARCH}/node_exporter" "$NEW_BINARY"
install -m 0755 "$NEW_BINARY" "${INSTALL_DIR}/node_exporter"
ROLLBACK_NEEDED=1

cat > "$TMP_DIR/node_exporter.service" <<EOF
[Unit]
Description=Prometheus Node Exporter
After=network-online.target

[Service]
User=node_exporter
Group=node_exporter
ExecStart=${INSTALL_DIR}/node_exporter --web.listen-address=0.0.0.0:9100
Restart=on-failure
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF
install -m 0644 "$TMP_DIR/node_exporter.service" "$SERVICE_FILE"
systemctl daemon-reload
systemctl enable --now node_exporter
sleep 1
systemctl is-active --quiet node_exporter
curl --fail --silent --show-error --max-time 5 http://127.0.0.1:9100/metrics | grep -q '^# HELP'

if [[ "$SKIP_FIREWALL" != 1 ]]; then
  MONITOR_IP="$MONITOR_IP" "$SCRIPT_DIR/configure-node-exporter-firewall.sh"
fi
ROLLBACK_NEEDED=0
rm -f "$BACKUP_BINARY" "$BACKUP_UNIT"
echo "Node Exporter ${VERSION} instalado: arquitectura=${ARCH}, monitor_ip=${MONITOR_IP}"
