#!/usr/bin/env bash
set -Eeuo pipefail
if [[ $EUID -ne 0 ]]; then echo "Ejecuta este script como root." >&2; exit 2; fi
systemctl disable --now superflash-agent >/dev/null 2>&1 || true
rm -f /etc/systemd/system/superflash-agent.service /usr/local/bin/superflash-agent
rm -f /var/lib/superflash-agent/status.json
rmdir /var/lib/superflash-agent >/dev/null 2>&1 || true
systemctl daemon-reload
userdel superflash-agent >/dev/null 2>&1 || true
echo "SuperFlash Agent bootstrap eliminado."
