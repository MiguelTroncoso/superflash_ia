#!/usr/bin/env bash
set -Eeuo pipefail

# Permite Node Exporter únicamente desde el VPS Monitor. Nunca elimina reglas
# existentes; añade una regla explícita de allow y otra de deny.
MONITOR_IP="${MONITOR_IP:-178.104.98.19}"
NODE_EXPORTER_PORT="${NODE_EXPORTER_PORT:-9100}"

if [[ ! "$MONITOR_IP" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]]; then
  echo "MONITOR_IP inválida: $MONITOR_IP" >&2
  exit 2
fi
if [[ $EUID -ne 0 ]]; then
  echo "Ejecuta este script como root." >&2
  exit 2
fi

if command -v ufw >/dev/null 2>&1 && ufw status 2>/dev/null | grep -q '^Status: active'; then
  # Keep the monitor allow rule before the catch-all deny rule. UFW evaluates
  # rules in order, so appending allow and inserting deny first would block
  # the Prometheus scrape as well.
  ufw insert 1 allow from "$MONITOR_IP" to any port "$NODE_EXPORTER_PORT" proto tcp >/dev/null || true
  ufw insert 2 deny "$NODE_EXPORTER_PORT/tcp" >/dev/null || true
  echo "firewall=ufw monitor_ip=$MONITOR_IP port=$NODE_EXPORTER_PORT"
  exit 0
fi

if command -v nft >/dev/null 2>&1 && nft list ruleset >/dev/null 2>&1; then
  nft list table inet superflash_node_exporter >/dev/null 2>&1 || \
    nft add table inet superflash_node_exporter
  nft list chain inet superflash_node_exporter input >/dev/null 2>&1 || \
    nft 'add chain inet superflash_node_exporter input { type filter hook input priority -100; policy accept; }'
  nft list chain inet superflash_node_exporter input | grep -Fq "ip saddr $MONITOR_IP tcp dport $NODE_EXPORTER_PORT accept" || \
    nft add rule inet superflash_node_exporter input ip saddr "$MONITOR_IP" tcp dport "$NODE_EXPORTER_PORT" accept
  nft list chain inet superflash_node_exporter input | grep -Fq "tcp dport $NODE_EXPORTER_PORT drop" || \
    nft add rule inet superflash_node_exporter input tcp dport "$NODE_EXPORTER_PORT" drop
  echo "firewall=nftables monitor_ip=$MONITOR_IP port=$NODE_EXPORTER_PORT"
  exit 0
fi

if command -v iptables >/dev/null 2>&1; then
  iptables -C INPUT -p tcp -s "$MONITOR_IP" --dport "$NODE_EXPORTER_PORT" -j ACCEPT 2>/dev/null || \
    iptables -I INPUT 1 -p tcp -s "$MONITOR_IP" --dport "$NODE_EXPORTER_PORT" -j ACCEPT
  iptables -C INPUT -p tcp --dport "$NODE_EXPORTER_PORT" -j DROP 2>/dev/null || \
    iptables -I INPUT 2 -p tcp --dport "$NODE_EXPORTER_PORT" -j DROP
  echo "firewall=iptables monitor_ip=$MONITOR_IP port=$NODE_EXPORTER_PORT"
  exit 0
fi

echo "No se detectó ufw, nftables ni iptables activos; no se modificó el firewall." >&2
exit 3
