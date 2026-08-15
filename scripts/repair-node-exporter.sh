#!/usr/bin/env bash
set -Eeuo pipefail

if [[ $EUID -ne 0 ]]; then echo "Ejecuta este script como root." >&2; exit 2; fi
for tool in systemctl curl; do command -v "$tool" >/dev/null || { echo "$tool es requerido" >&2; exit 2; }; done

INSTALL_DIR="${INSTALL_DIR:-/usr/local/bin}"
SERVICE_FILE="/etc/systemd/system/node_exporter.service"
[[ -x "$INSTALL_DIR/node_exporter" ]] || { echo "Node Exporter no está instalado." >&2; exit 1; }

id node_exporter >/dev/null 2>&1 || useradd --system --no-create-home --shell /usr/sbin/nologin node_exporter
chown root:root "$INSTALL_DIR/node_exporter"
chmod 0755 "$INSTALL_DIR/node_exporter"

if [[ ! -f "$SERVICE_FILE" ]]; then
  install -d -m 0755 "$(dirname "$SERVICE_FILE")"
  cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=Prometheus Node Exporter
After=network-online.target

[Service]
User=node_exporter
Group=node_exporter
ExecStart=${INSTALL_DIR}/node_exporter --web.listen-address=0.0.0.0:9100
Restart=on-failure
RestartSec=5s
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF
fi

systemctl daemon-reload
systemctl enable --now node_exporter
sleep 1
systemctl is-active --quiet node_exporter
curl --fail --silent --show-error --max-time 5 http://127.0.0.1:9100/metrics | grep -q '^# HELP'
echo "Node Exporter reparado y validado"
