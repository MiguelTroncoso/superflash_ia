#!/usr/bin/env bash
set -Eeuo pipefail

# Only manages rules tagged as SuperFlash. Existing firewall rules are never
# deleted or replaced. FIREWALL_ACTION=remove is used only by rollback.
MONITOR_IP="${MONITOR_IP:-178.104.98.19}"
NODE_EXPORTER_PORT="${NODE_EXPORTER_PORT:-9100}"
FIREWALL_ACTION="${FIREWALL_ACTION:-configure}"
RULE_COMMENT="superflash-node-exporter"

if [[ ! "$MONITOR_IP" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]]; then
  echo "MONITOR_IP inválida" >&2
  exit 2
fi
if [[ ! "$NODE_EXPORTER_PORT" =~ ^[0-9]+$ ]]; then
  echo "NODE_EXPORTER_PORT inválido" >&2
  exit 2
fi
if [[ "$FIREWALL_ACTION" != "configure" && "$FIREWALL_ACTION" != "remove" ]]; then
  echo "FIREWALL_ACTION inválida" >&2
  exit 2
fi
if [[ $EUID -ne 0 ]]; then
  echo "Ejecuta este script como root." >&2
  exit 2
fi

if command -v ufw >/dev/null 2>&1 && ufw status 2>/dev/null | grep -q '^Status: active'; then
  if [[ "$FIREWALL_ACTION" == "remove" ]]; then
    ufw delete allow from "$MONITOR_IP" to any port "$NODE_EXPORTER_PORT" proto tcp comment "$RULE_COMMENT" >/dev/null 2>&1 || true
    ufw delete deny "$NODE_EXPORTER_PORT/tcp" comment "$RULE_COMMENT" >/dev/null 2>&1 || true
    echo "firewall=ufw managed_rules_removed"
  else
    # UFW evaluates rules in order: the allow must precede the catch-all deny.
    ufw status | grep -Fq "$NODE_EXPORTER_PORT/tcp ALLOW IN $MONITOR_IP" || \
      ufw insert 1 allow from "$MONITOR_IP" to any port "$NODE_EXPORTER_PORT" proto tcp comment "$RULE_COMMENT"
    ufw status | grep -Fq "$NODE_EXPORTER_PORT/tcp DENY IN Anywhere" || \
      ufw insert 2 deny "$NODE_EXPORTER_PORT/tcp" comment "$RULE_COMMENT"
    echo "firewall=ufw monitor_ip=$MONITOR_IP port=$NODE_EXPORTER_PORT"
  fi
  exit 0
fi

if command -v nft >/dev/null 2>&1 && nft list ruleset >/dev/null 2>&1; then
  if [[ "$FIREWALL_ACTION" == "remove" ]]; then
    nft delete table inet superflash_node_exporter >/dev/null 2>&1 || true
    echo "firewall=nftables managed_rules_removed"
    exit 0
  fi
  nft list table inet superflash_node_exporter >/dev/null 2>&1 || nft add table inet superflash_node_exporter
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
  if [[ "$FIREWALL_ACTION" == "remove" ]]; then
    iptables -D INPUT -p tcp -s "$MONITOR_IP" --dport "$NODE_EXPORTER_PORT" \
      -m comment --comment "$RULE_COMMENT" -j ACCEPT >/dev/null 2>&1 || true
    iptables -D INPUT -p tcp --dport "$NODE_EXPORTER_PORT" \
      -m comment --comment "$RULE_COMMENT" -j DROP >/dev/null 2>&1 || true
    echo "firewall=iptables managed_rules_removed"
  else
    iptables -C INPUT -p tcp -s "$MONITOR_IP" --dport "$NODE_EXPORTER_PORT" \
      -m comment --comment "$RULE_COMMENT" -j ACCEPT >/dev/null 2>&1 || \
      iptables -I INPUT 1 -p tcp -s "$MONITOR_IP" --dport "$NODE_EXPORTER_PORT" \
        -m comment --comment "$RULE_COMMENT" -j ACCEPT
    iptables -C INPUT -p tcp --dport "$NODE_EXPORTER_PORT" \
      -m comment --comment "$RULE_COMMENT" -j DROP >/dev/null 2>&1 || \
      iptables -I INPUT 2 -p tcp --dport "$NODE_EXPORTER_PORT" \
        -m comment --comment "$RULE_COMMENT" -j DROP
    echo "firewall=iptables monitor_ip=$MONITOR_IP port=$NODE_EXPORTER_PORT"
  fi
  exit 0
fi

echo "No se detectó ufw, nftables ni iptables activos; no se modificó el firewall." >&2
exit 3
