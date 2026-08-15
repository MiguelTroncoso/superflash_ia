#!/usr/bin/env bash
set -Eeuo pipefail

if [[ $EUID -ne 0 ]]; then echo "Ejecuta este script como root." >&2; exit 2; fi
systemctl disable --now node_exporter >/dev/null 2>&1 || true
rm -f /etc/systemd/system/node_exporter.service /usr/local/bin/node_exporter
systemctl daemon-reload
# Las reglas de firewall no se eliminan automáticamente: pueden proteger otro
# servicio y deben retirarse manualmente tras revisar el ruleset.
echo "Node Exporter eliminado. Revisa manualmente las reglas del puerto 9100."
