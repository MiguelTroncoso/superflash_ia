#!/usr/bin/env bash
set -Eeuo pipefail
if [[ $EUID -ne 0 ]]; then echo "Ejecuta este script como root." >&2; exit 2; fi
AGENT_VERSION="${SUPERFLASH_AGENT_VERSION:-0.1.0}"
BIN="/usr/local/bin/superflash-agent"
UNIT="/etc/systemd/system/superflash-agent.service"
STATE_DIR="/var/lib/superflash-agent"
TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT
id superflash-agent >/dev/null 2>&1 || useradd --system --no-create-home --shell /usr/sbin/nologin superflash-agent
install -d -o superflash-agent -g superflash-agent -m 0750 "$STATE_DIR"
cat > "$TMP" <<'AGENT'
#!/usr/bin/env bash
set -Eeuo pipefail
VERSION="${SUPERFLASH_AGENT_VERSION:-0.1.0}"
STATE_DIR="/var/lib/superflash-agent"
ARCH="$(uname -m)"
OS="$(. /etc/os-release 2>/dev/null && printf '%s %s' "${PRETTY_NAME:-Linux}" "${VERSION_ID:-}" || printf 'Linux')"
IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
printf '{"version":"%s","hostname":"%s","architecture":"%s","os":"%s","ip":"%s","status":"ready"}\n' \
  "$VERSION" "$(hostname)" "$ARCH" "$OS" "${IP:-unknown}" > "$STATE_DIR/status.json"
AGENT
install -m 0755 "$TMP" "$BIN"
cat > "$UNIT" <<EOF
[Unit]
Description=SuperFlash Monitor Agent bootstrap
After=network.target

[Service]
Type=oneshot
User=superflash-agent
Group=superflash-agent
Environment=SUPERFLASH_AGENT_VERSION=${AGENT_VERSION}
ExecStart=${BIN}
RemainAfterExit=yes
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths=${STATE_DIR}

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable --now superflash-agent
test -s "$STATE_DIR/status.json"
echo "SuperFlash Agent bootstrap instalado; sin puertos ni conexiones externas."
