# Production commissioning: real infrastructure

This runbook describes the production-only steps for connecting a server to
SuperFlash Monitor through Prometheus and Node Exporter. It does not connect
Xtream, execute actions on a monitored server, or replace the existing
Prometheus installation.

## Scope and safety

- The API uses `GET /api/v1/query` only. Prometheus tokens are read from the
  local server inventory and are never returned by the API or sent to React.
- `/health` remains public; `/api/v1/*` remains protected by `X-API-Key` at
  the existing Nginx boundary.
- The dashboard keeps MOCK only for enabled servers without a Prometheus URL
  and hostname. A configured server with no real sample is shown as `no_data`
  or `Waiting for metrics...`; synthetic values are not substituted.
- Xtream is a provider placeholder only. No Xtream HTTP request is made by
  this commissioning flow.

## Node Exporter on an Ubuntu 22.04 target

Copy the scripts from this repository to the target through the approved
administrative channel. Run them as root:

```bash
sudo MONITOR_IP=178.104.98.19 ./scripts/install-node-exporter.sh
```

The installer detects `amd64`, `arm64`, and `armv7`, downloads the latest
stable release and SHA-256 sums from the official Prometheus release, creates
the locked-down `node_exporter` system user, installs a systemd unit, enables
autostart, and verifies `http://127.0.0.1:9100/metrics`.

It is idempotent. If service or local metric validation fails, the previous
binary and unit are restored. The firewall rules added by the installer are
deliberately not deleted automatically during rollback; review them before
removing them because they may be part of the host's existing security policy.

Update the exporter with:

```bash
sudo MONITOR_IP=178.104.98.19 ./scripts/update-node-exporter.sh
```

Remove it with:

```bash
sudo ./scripts/remove-node-exporter.sh
```

Removal leaves firewall rules in place for manual review and does not delete
unrelated rules.

## Firewall policy

The installer calls `configure-node-exporter-firewall.sh`, which detects an
active UFW, nftables, or iptables backend. It adds an allow rule for
`178.104.98.19` to TCP/9100 and a deny rule for other sources without
deleting existing rules. Confirm the effective policy before commissioning:

```bash
sudo ufw status numbered                 # if UFW is active
sudo nft list ruleset                    # if nftables is in use
sudo iptables -S INPUT                   # if iptables is in use
```

Do not expose TCP/9100 publicly. If a provider security group exists, apply
the same source restriction there as well.

## SuperFlash Agent bootstrap

The optional base agent reports only local bootstrap facts: version,
hostname, architecture, operating system, first local IP, and readiness. It
opens no port and makes no network connection:

```bash
sudo ./scripts/install-superflash-agent.sh
sudo systemctl status superflash-agent.service
sudo cat /var/lib/superflash-agent/status.json
```

Update or remove it with `update-superflash-agent.sh` and
`remove-superflash-agent.sh`. It does not replace Node Exporter or Prometheus.

## Prometheus target configuration

Prometheus must scrape the target privately; the application does not
hardcode targets. A representative target is:

```yaml
scrape_configs:
  - job_name: superflash-node-exporter
    static_configs:
      - targets: ["SERVER_PRIVATE_HOSTNAME_OR_IP:9100"]
        labels:
          superflash_external_id: "SERVER_EXTERNAL_ID"
```

Use the existing Prometheus deployment and reload procedure. Never commit a
private target list or bearer token to this repository.

## Registering a server

From the existing Servers view, enter the name, immutable external ID,
hostname/IP, provider, capacity, Prometheus URL, and optional Prometheus
token. Optionally set `network_interface` to `eth0`, `ens18`, `ens3`, or an
`enp*` interface after discovery. Leaving it blank makes the provider
exclude loopback, bridge, veth, Docker, and other pseudo-interfaces
automatically.

The create flow saves the local inventory and performs one read-only
diagnostic. The API persists a deduplicated technical snapshot containing the
host facts returned by Node Exporter, the original Prometheus scrape time,
latency, and the selected interface. Repeating the diagnostic with the same
scrape timestamp does not create a duplicate.

Useful protected endpoints:

```text
POST   /api/v1/servers
PATCH  /api/v1/servers/{id}
DELETE /api/v1/servers/{id}
GET    /api/v1/servers/{id}/diagnose
GET    /api/v1/servers/{id}/inventory
GET    /api/v1/servers/{id}/metrics
GET    /api/v1/capacity/overview
```

The CRUD affects only the local SuperFlash Monitor inventory. No remote
server configuration is changed by these endpoints.

## Recovery and rollback

1. In the Servers view, disable the target or clear its Prometheus URL to
   stop real-source collection while preserving local history.
2. Inspect the diagnostic response and the last persisted inventory snapshot;
   it contains no stack trace or secret.
3. On the target, run `remove-node-exporter.sh` only after reviewing the
   service dependency and manually reviewing TCP/9100 firewall rules.
4. If an exporter update fails, rerun the previous approved installer or use
   the installer's automatic binary/unit rollback.
5. Roll back the application with the deployment's normal image rollback,
   then run the database migration downgrade only according to the backup
   procedure. Migrations `0011` and `0012` are additive and their downgrades
   remove only their own snapshot table or nullable interface column.

Before a deployment window, confirm the Compose plugin on the VPS with:

```bash
docker compose version
```

The commissioning stack uses the Compose v2 service dependency condition
`service_completed_successfully` for the one-shot migrations job. Validate
that the reported VPS version supports it before applying the stack.

## Commissioning checklist

For each approved target (initially MainServer, 10GBS, Live 1, Live 2, and
Live 3), record the result of:

- Node Exporter service and local `/metrics` check;
- Prometheus `up` and last scrape timestamp;
- firewall source restriction and latency;
- automatic hostname, OS, architecture, CPU, memory, disks, interfaces,
  kernel, virtualization, boot time, and uptime discovery;
- real CPU, RAM, Swap, filesystem, disk, load, RX, TX, and uptime in the
  dashboard;
- optimizer capacity statistics sourced from persisted real metrics.

This repository change cannot certify those five production targets without
access to their Prometheus instances and firewall configuration. The release
must remain pending until that operational checklist is completed.
