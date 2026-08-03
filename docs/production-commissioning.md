# Production commissioning: Prometheus + Node Exporter

Esta guía activa la primera conexión real sin cambiar la arquitectura ni
ejecutar acciones en los servidores monitorizados. La API solo hace consultas
`GET` a Prometheus y guarda el resultado en la base local.

## Configuración de la aplicación

En el VPS, copia `.env.production.example` a `.env.production`, conserva el
archivo con permisos `600` y cambia únicamente la configuración de la fuente:

```dotenv
MONITORING_ADAPTER=composite
INFRASTRUCTURE_SOURCE=prometheus
STREAMING_SOURCE=mock
PROMETHEUS_TIMEOUT_SECONDS=10
PROMETHEUS_TLS_VERIFY=true
SCHEDULER_ENABLED=true
```

Con la API funcionando sobre la base de datos, los targets no se hardcodean en
el repositorio: se registran desde `Servers → Add server`. Para cada servidor
rellena `Hostname / IP` y `Prometheus URL`; `Prometheus token` es opcional y
solo se usa en memoria al consultar. La respuesta de la API no devuelve URL ni
token, y Nginx continúa inyectando `X-API-Key` únicamente en el proxy interno.

Si se usa el comando de diagnóstico con un inventario YAML, define además
`PROMETHEUS_URL` e `INFRASTRUCTURE_INVENTORY_FILE`. Ese archivo real debe
permanecer fuera de Git; `config/inventory.example.yaml` contiene únicamente
direcciones de documentación.

## Prometheus

Prometheus debe poder alcanzar el puerto `9100` de cada Node Exporter. Los
targets se administran en la configuración de Prometheus, nunca en código:

```yaml
scrape_configs:
  - job_name: superflash-node-exporter
    scrape_interval: 30s
    static_configs:
      - targets:
          - server-a.example.net:9100
          - server-b.example.net:9100
```

El valor `Hostname / IP` del formulario debe corresponder al host de la serie
`instance` que Prometheus expone; si no se especifica un puerto, el provider
usa `9100`. La aplicación consulta `up`, CPU, memoria, swap, filesystem, IO,
RX, TX, load average y uptime mediante PromQL de solo lectura.

## Node Exporter

Ejemplo para Ubuntu/Debian. Sustituye `NODE_EXPORTER_VERSION` por la versión
aprobada por operaciones y verifica el checksum publicado por el proyecto
antes de instalarlo.

### Instalación

```bash
export NODE_EXPORTER_VERSION=1.8.2
curl -fL -o /tmp/node_exporter.tar.gz \
  "https://github.com/prometheus/node_exporter/releases/download/v${NODE_EXPORTER_VERSION}/node_exporter-${NODE_EXPORTER_VERSION}.linux-amd64.tar.gz"
curl -fL -o /tmp/node_exporter.sha256 \
  "https://github.com/prometheus/node_exporter/releases/download/v${NODE_EXPORTER_VERSION}/sha256sums.txt"
grep "node_exporter-${NODE_EXPORTER_VERSION}.linux-amd64.tar.gz" /tmp/node_exporter.sha256 | sha256sum -c -

sudo useradd --system --no-create-home --shell /usr/sbin/nologin node_exporter || true
sudo install -m 0755 "/tmp/node_exporter-${NODE_EXPORTER_VERSION}.linux-amd64/node_exporter" /usr/local/bin/node_exporter
sudo tee /etc/systemd/system/node_exporter.service >/dev/null <<'EOF'
[Unit]
Description=Prometheus Node Exporter
After=network-online.target

[Service]
User=node_exporter
Group=node_exporter
ExecStart=/usr/local/bin/node_exporter --web.listen-address=0.0.0.0:9100
Restart=on-failure
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now node_exporter
curl --fail http://127.0.0.1:9100/metrics | head
```

### Firewall

No publiques `9100` al mundo. Permite exclusivamente la IP privada o pública
del VPS Monitor que ejecuta Prometheus y rechaza el resto:

```bash
export MONITOR_VPS_IP=203.0.113.10
sudo ufw deny 9100/tcp
sudo ufw allow from "$MONITOR_VPS_IP" to any port 9100 proto tcp
sudo ufw status numbered
```

Si el proveedor usa security groups o ACLs, aplica la misma regla allí. La
regla debe existir tanto en el servidor monitorizado como en la red del
proveedor. Comprueba desde el VPS Monitor:

```bash
nc -vz server-a.example.net 9100
```

### Actualización

Instala el binario nuevo en una ruta temporal, verifica checksum, reemplaza el
binario y reinicia. El servicio conserva la misma configuración y puerto:

```bash
sudo systemctl stop node_exporter
sudo install -m 0755 /tmp/node_exporter-new /usr/local/bin/node_exporter
sudo systemctl start node_exporter
systemctl is-active node_exporter
```

### Desinstalación

Antes de desinstalar, elimina el target de Prometheus o acepta que la
diagnosis quede en error:

```bash
sudo systemctl disable --now node_exporter
sudo rm -f /etc/systemd/system/node_exporter.service /usr/local/bin/node_exporter
sudo systemctl daemon-reload
sudo userdel node_exporter 2>/dev/null || true
```

## Procedimiento para conectar un servidor

1. Instala Node Exporter y limita `9100/tcp` a la IP del VPS Monitor.
2. Agrega el target al `scrape_configs` de Prometheus y recarga Prometheus.
3. En el dashboard, abre `Servers → Add server`.
4. Guarda nombre, external ID, hostname/IP, capacidad, URL de Prometheus y el
   token de solo lectura si corresponde.
5. Usa `Test connection` o abre el detalle del servidor. Debe mostrar
   `Prometheus OK`, `Node Exporter OK`, latencia y última muestra.
6. Ejecuta una recolección manual o espera al scheduler y verifica que la
   métrica tenga `source=prometheus`. Los servidores sin configuración siguen
   usando exclusivamente `source=mock`; un servidor configurado que falle no
   se disfraza con datos simulados.
7. Revisa Dashboard y Optimizer. Ambos consumen el histórico persistido y no
   ejecutan cambios en infraestructura.

## Diagnóstico y límites

`GET /api/v1/servers/{id}/diagnose` es protegido por `X-API-Key`, no persiste
nada y devuelve mensajes sanitizados. No devuelve stack traces, tokens ni
URLs privadas. `/health` continúa siendo público.

Antes de considerar la conexión productiva aprobada, valida firewall,
`up==1`, una muestra Prometheus reciente, valores de CPU/RAM/red coherentes y
al menos dos ciclos de recolección. Xtream continúa fuera de este sprint.
