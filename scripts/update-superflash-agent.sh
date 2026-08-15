#!/usr/bin/env bash
set -Eeuo pipefail
if [[ $EUID -ne 0 ]]; then echo "Ejecuta este script como root." >&2; exit 2; fi
[[ -f /etc/systemd/system/superflash-agent.service ]] || { echo "SuperFlash Agent no está instalado." >&2; exit 1; }
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
"$SCRIPT_DIR/install-superflash-agent.sh"
echo "SuperFlash Agent actualizado y validado."
