# SuperFlash Monitor

Plataforma privada de monitoreo y análisis para una infraestructura
autorizada de distribución de contenido audiovisual.

> ⚠️ **La versión actual utiliza únicamente datos simulados y no
> modifica ninguna infraestructura externa.** La aplicación es
> exclusivamente de lectura y monitoreo: no mueve canales, no toca
> configuraciones de paneles externos y no ejecuta ninguna acción
> remota.

## Propósito

Recopilar métricas históricas de servidores y canales (cada cinco
minutos en fases futuras), almacenarlas en PostgreSQL y exponerlas por
una API HTTP para análisis. En fases posteriores la plataforma
recomendará cómo distribuir canales entre servidores; esta primera
versión solo observa.

## Alcance actual (v0.1.0)

- Modelos de datos: `Server`, `ServerMetric`, `Channel`, `ChannelMetric`.
- Adaptador simulado (`MockMonitoringAdapter`) reproducible por semilla:
  5 servidores con capacidades distintas y 24 canales con audiencias
  variadas y coherentes.
- Recolección manual (endpoint interno y comando CLI) con deduplicación
  de muestras, aislamiento de errores por elemento y **exclusión mutua en
  dos niveles**: lock de hilo en el proceso y **advisory lock de
  PostgreSQL** entre instancias (con fallback en memoria para
  SQLite/tests).
- **Historial persistido** de ejecuciones (`collection_runs`: inicio,
  fin, duración, origen manual/scheduler, contadores y errores);
  `/api/v1/collection/status` lo lee de la base, por lo que sobrevive a
  reinicios y es visible desde cualquier instancia.
- **API key global**: todos los endpoints `/api/v1` exigen `X-API-Key`
  (`API_KEY`, fail-closed); solo `/health` es público.
- **Paginación por cursor** en los históricos (cabecera `X-Next-Cursor`),
  compatible con los clientes que solo usan `limit`.
- **Retención configurable** del histórico propio, deshabilitada por
  defecto (`METRICS_RETENTION_DAYS` + `python -m app.tasks.prune_metrics`).
- **Alertas internas de solo lectura** (`GET /api/v1/alerts`): CPU, RAM,
  disco, utilización de red y servidores sin muestra reciente; sin
  notificaciones externas.
- **Scheduler opcional** de recolección periódica (cada 5 minutos por
  defecto), deshabilitado salvo que se active explícitamente.
- **Arquitectura multi-fuente**: contratos separados para métricas de
  infraestructura (`InfrastructureMetricsAdapter`: CPU, RAM, disco, red,
  load, uptime, estado) y de streaming (`StreamingMetricsAdapter`:
  espectadores, bitrate, estado del canal), con mocks de demostración,
  adaptador compuesto (`MONITORING_ADAPTER=composite`) y comando de
  diagnóstico sin persistencia (`python -m app.tasks.diagnose_source`).
- **Fuente de infraestructura real Prometheus**
  (`INFRASTRUCTURE_SOURCE=prometheus`): consulta node_exporter por HTTP
  (solo GET), con inventario local no versionado, timeout y bearer token
  configurables, TLS verificado y obligatorio en producción. La fuente
  de streaming real aún no existe.
- API de consulta: servidores, canales, históricos por rango de fechas y
  resumen agregado (`/api/v1/overview`).
- Historial de recolecciones con **heartbeat persistido**: una ejecución
  se considera abandonada solo si su heartbeat supera
  `COLLECTION_TIMEOUT_SECONDS`.
- Migraciones con Alembic y despliegue con Docker Compose.
- CI en GitHub Actions: lint, tipos, pruebas y smoke test end-to-end
  contra PostgreSQL real (incluido el ciclo de migraciones).
- El mock sigue siendo la fuente por defecto; sin escritura externa.

## Arquitectura

```
app/
  api/            # Routers FastAPI (health + /api/v1)
  core/           # Configuración (Pydantic Settings) y logging
  database/       # Base declarativa, motor y sesiones
  models/         # Modelos ORM (SQLAlchemy 2)
  schemas/        # Esquemas Pydantic de la API
  repositories/   # Consultas y persistencia
  services/       # Lógica de negocio (overview)
  collectors/     # Servicio de recolección
  adapters/       # Interfaz MonitoringSourceAdapter + mock
  tasks/          # Comandos CLI y scheduler periódico opcional
  main.py         # Fábrica de la aplicación
alembic/          # Migraciones
tests/            # Pruebas unitarias y de integración
docs/             # Documentación de arquitectura
```

El detalle de responsabilidades y flujos está en
[`docs/architecture.md`](docs/architecture.md).

## Requisitos

- Python 3.12
- PostgreSQL 16 (o Docker)
- Docker + Docker Compose (para el despliegue contenedorizado)

## Instalación local

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

cp .env.example .env   # ajusta DATABASE_URL a tu PostgreSQL local
alembic upgrade head
uvicorn app.main:app --reload
```

La documentación interactiva queda en `http://localhost:8000/docs`.

## Ejecución con Docker

```bash
cp .env.example .env   # opcional: cambia puertos y credenciales
docker compose up --build
```

Servicios:

- `db`: PostgreSQL 16 con volumen persistente (`pgdata`) y healthcheck.
- `migrations`: contenedor *one-shot* que ejecuta `alembic upgrade head`
  una única vez cuando la base está sana. La API no arranca hasta que
  termina con éxito. Este patrón evita condiciones de carrera cuando en
  el futuro existan varias réplicas de la API: ninguna réplica ejecuta
  migraciones por su cuenta.
- `api`: FastAPI en el puerto `${API_PORT:-8000}`, con healthcheck sobre
  `/health`.

Las credenciales por defecto son solo para desarrollo local; en
cualquier entorno real defínelas en `.env` (nunca versionado).

Para el despliegue en producción sobre Ubuntu 24.04 usa la guía
[`docs/deployment.md`](docs/deployment.md), que incluye el Compose de
producción, Nginx, backups, restauración, rollback y validaciones.

## Migraciones

```bash
alembic upgrade head            # aplicar
alembic downgrade -1            # revertir la última
alembic revision -m "mensaje"   # crear una nueva (editar a mano)
```

La URL de conexión se toma siempre de `DATABASE_URL` (entorno o `.env`),
nunca de `alembic.ini`.

## Pruebas y calidad

```bash
pytest          # pruebas (SQLite en memoria, no requiere PostgreSQL)
ruff check .    # linter
ruff format .   # formateo
mypy app        # verificación de tipos

# Smoke test end-to-end (migraciones + API real). Requiere una BD:
DATABASE_URL=postgresql+psycopg://... COLLECTION_API_KEY=una-clave \
    python scripts/smoke_test.py
```

La integración continua (`.github/workflows/ci.yml`) ejecuta en cada
push: `ruff check`, `ruff format --check`, `mypy app`, `pytest`, y un
smoke test contra PostgreSQL 16 real (servicio de GitHub Actions) que
verifica el ciclo completo de migraciones (`upgrade` → `downgrade` →
`upgrade`), la autenticación, la recolección con deduplicación, el
overview y el endpoint de estado.

## Endpoints disponibles

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET  | `/health` | Estado de la app, conexión a PostgreSQL y versión |
| GET  | `/api/v1/servers` | Lista de servidores |
| GET  | `/api/v1/servers/{id}` | Detalle de un servidor |
| GET  | `/api/v1/servers/{id}/metrics` | Histórico (`start`, `end`, `limit`) |
| GET  | `/api/v1/channels` | Canales dinámicos paginados (filtros `server_id`, `source_id`, `category`, `category_id`, `channel_type`, `active`, fecha de evento, `enabled`) |
| GET  | `/api/v1/channels/{id}/metrics` | Histórico del canal (`start`, `end`, `limit`, `cursor`) |
| POST | `/api/v1/collection/run` | Ejecuta una recolección (409 si ya hay una en curso) |
| GET  | `/api/v1/collection/status` | Estado persistido del recolector y del scheduler |
| GET  | `/api/v1/alerts` | Alertas internas según las últimas muestras |
| GET  | `/api/v1/overview` | Estadísticas agregadas actuales |

### Autenticación

**Todos** los endpoints `/api/v1` exigen la cabecera `X-API-Key` con el
valor de `API_KEY` (solo variable de entorno, nunca en el código; se
acepta el nombre histórico `COLLECTION_API_KEY` como alias). `/health`
permanece público para orquestadores. La política es *fail-closed*: sin
la variable configurada, la API responde `503` en lugar de quedar
abierta. Clave ausente o incorrecta → `401`.

### Paginación por cursor

Los históricos (`/servers/{id}/metrics`, `/channels/{id}/metrics`)
aceptan `cursor` y devuelven, cuando hay más resultados, la cabecera
`X-Next-Cursor` con el cursor opaco de la página siguiente. El cuerpo
sigue siendo la lista de siempre: los clientes que solo usan `limit`
funcionan sin cambios. Un cursor malformado responde `400`.

### Canales dinámicos y eventos

Los canales se identifican por `source_id + external_id`; el nombre nunca
es una identidad. Cada canal puede ser `permanent`, `event`, `temporary`,
`scheduled` o `archived`. La sincronización conserva el historial de
métricas y categorías cuando un evento cambia de nombre o desaparece de la
fuente Xtream:

- una ausencia marca el canal como `active=false` y no borra datos;
- una reaparición reactiva la misma fila, sin duplicarla;
- el archivado se aplica después de `EVENT_INACTIVE_GRACE_HOURS` y de la
  retención configurada (`EVENT_ARCHIVE_DAYS` o `PERMANENT_ARCHIVE_DAYS`);
- eventos y streams técnicos son entidades separadas, de modo que un mismo
  stream técnico puede reutilizarse para eventos de fechas diferentes.

Cada recolección devuelve y persiste contadores de `created`, `updated`,
`reactivated`, `deactivated`, `archived`, `unchanged` y `failed`.

### Retención del histórico

Deshabilitada por defecto. Con `METRICS_RETENTION_DAYS` configurado:

```bash
python -m app.tasks.prune_metrics --dry-run  # cuenta sin borrar
python -m app.tasks.prune_metrics            # borra lo anterior al corte
```

Sin esa variable el comando se niega a borrar y termina con código 2.
Solo afecta a la base propia de la plataforma (métricas y ejecuciones);
jamás toca infraestructura externa.

### Alertas internas

`GET /api/v1/alerts` evalúa bajo demanda la última muestra de cada
servidor habilitado contra los umbrales configurables (`ALERT_*`):
CPU alta, RAM alta, disco alto, utilización de red alta y servidor sin
muestra reciente. No se persiste nada ni se envían notificaciones
externas; los datos ausentes (disco desconocido, capacidad 0) nunca
generan falsas alertas.

### Recolección automática (scheduler)

Con `SCHEDULER_ENABLED=true` la API ejecuta una recolección cada
`COLLECTION_INTERVAL_SECONDS` (300 = 5 minutos, mínimo 5). Está
**deshabilitado por defecto** y comparte el mismo lock que el endpoint
manual, por lo que un ciclo nunca se solapa con una ejecución manual: el
que llegue segundo se omite y queda registrado en el log.
`GET /api/v1/collection/status` muestra el próximo ciclo (`next_run_at`).

### Estado de la recolección y heartbeat

`GET /api/v1/collection/status` describe la ejecución relevante (la que
está en curso, o la última terminada) con un contrato plano y estable:
`running`, `run_id`, `source`, `triggered_by`, `started_at`,
`heartbeat_at`, `finished_at`, `duration_ms`, `status`, `inserted`,
`skipped`, `errors`, `next_run_at`. Cada pasada actualiza un heartbeat
persistido; una fila `running` solo se considera realmente en curso
mientras su heartbeat no supere `COLLECTION_TIMEOUT_SECONDS` (default
600 s). Al iniciar una nueva recolección, las filas `running` con
heartbeat vencido (proceso caído) se marcan como `error`.

### Conectar un servidor Prometheus real (infraestructura)

Ver también `docs/real-source-integration.md`. Pasos:

1. **Node exporter** corriendo en cada servidor y un Prometheus que lo
   scrapea (esta plataforma no instala ni configura nada remoto).
2. **Inventario local**: copia el ejemplo y edítalo con tus servidores;
   `node_exporter_instance` debe coincidir con la etiqueta `instance` de
   Prometheus. El archivo real **no se versiona**.
   ```bash
   cp config/inventory.example.yaml config/inventory.yaml
   ```
3. **Configuración** en tu `.env` (nunca en el repositorio):
   ```bash
   INFRASTRUCTURE_SOURCE=prometheus
   MONITORING_ADAPTER=composite          # infra real + streaming mock (aún)
   PROMETHEUS_URL=https://prometheus.tu-red.internal:9090
   PROMETHEUS_BEARER_TOKEN=...            # opcional
   INFRASTRUCTURE_INVENTORY_FILE=config/inventory.yaml
   ```
4. **Diagnostica** antes de recolectar (no escribe en la base de datos):
   ```bash
   python -m app.tasks.diagnose_source --infrastructure prometheus
   ```
5. **Recolecta** cuando el diagnóstico esté verde:
   ```bash
   curl -X POST -H "X-API-Key: $API_KEY" \
       http://localhost:8000/api/v1/collection/run
   ```

La verificación TLS está activa por defecto y **no puede desactivarse**
con `APP_ENV=production`. Solo se hacen solicitudes GET de consulta.

El scheduler es de proceso único: actívalo solo con una instancia de la
API. Con réplicas múltiples se usará un programador externo o un lock
distribuido (ver `docs/architecture.md`).

## Ejemplo de recolección

```bash
# Vía API (toda la v1 requiere la clave configurada en API_KEY)
curl -X POST -H "X-API-Key: $API_KEY" \
    http://localhost:8000/api/v1/collection/run

# Estado del recolector (historial persistido)
curl -H "X-API-Key: $API_KEY" http://localhost:8000/api/v1/collection/status

# Alertas internas
curl -H "X-API-Key: $API_KEY" http://localhost:8000/api/v1/alerts

# Vía CLI (mismo comportamiento, sin pasar por HTTP; --seed opcional)
python -m app.tasks.collect --seed 42

# Diagnóstico de fuentes: valida configuración y muestra qué datos
# entregaría cada fuente, SIN escribir en la base de datos.
python -m app.tasks.diagnose_source
python -m app.tasks.diagnose_source --source infrastructure

# Diagnóstico de Prometheus: comprueba conectividad, lista las métricas
# disponibles por host y valida las consultas (los tokens quedan ocultos).
python -m app.tasks.diagnose_source --infrastructure prometheus
```

Respuesta típica:

```json
{
  "adapter": "mock",
  "servers_synced": 5,
  "channels_synced": 24,
  "server_metrics_inserted": 5,
  "channel_metrics_inserted": 24,
  "server_metrics_skipped": 0,
  "channel_metrics_skipped": 0,
  "errors": []
}
```

Repetir la recolección dentro del mismo minuto no duplica muestras
(`*_skipped` se incrementa): cada muestra se identifica por
`(server|channel, collected_at)` y está protegida además por una
constraint de unicidad en la base de datos.

## Decisiones técnicas

- **SQLAlchemy 2 síncrono**: suficiente para una API de lectura con
  recolección cada 5 minutos; evita la complejidad extra de async sin
  beneficio real en esta fase.
- **Snapshots Pydantic en la frontera de adaptadores**: los datos de la
  fuente externa se validan antes de tocar la persistencia.
- **Deduplicación en dos capas**: verificación previa + constraint única
  `(server_id, collected_at)` / `(channel_id, collected_at)`.
- **Savepoints por elemento en la recolección**: un servidor o canal que
  falla se registra y no aborta el resto de la pasada.
- **Exclusión mutua en dos niveles**: lock de hilo (mismo proceso) +
  advisory lock de PostgreSQL sobre una conexión dedicada (entre
  instancias; si el proceso muere, PostgreSQL libera el lock solo). En
  SQLite el nivel distribuido es un no-op y basta el lock de hilo.
- **Historial en `collection_runs`**: cada pasada se inserta al empezar
  (estado `running`) y se completa al terminar; el status se lee de la
  base y las filas `running` huérfanas (> 30 min) se ignoran.
- **API key fail-closed global**: sin `API_KEY` toda la v1 responde 503;
  la comparación usa `secrets.compare_digest` y la clave jamás se loguea.
- **Snapshot compuesto por ciclo**: en modo `composite`, cada fuente se
  consulta una sola vez por pasada y servidores/canales comparten la
  misma muestra (consistencia temporal garantizada).
- **Cursor en cabecera**: `X-Next-Cursor` mantiene el cuerpo de las
  respuestas históricas sin cambios durante la transición.
- **Migraciones en contenedor one-shot**: una sola ejecución de
  `alembic upgrade` por despliegue, sin carreras entre réplicas.
- **Esquema portable (PostgreSQL/SQLite)**: los tests corren contra
  SQLite en memoria sin necesitar PostgreSQL.
- **Timestamps siempre en UTC** (`TIMESTAMPTZ`); los rangos sin zona
  horaria se interpretan como UTC.

## Limitaciones actuales

- Solo datos simulados: no existe todavía adaptador para el panel real.
- El scheduler sigue siendo in-process: con varias réplicas conviene
  activarlo en una sola (el advisory lock impide duplicar recolecciones
  en cualquier caso, pero los ciclos extra se desperdician).
- Una única API key compartida (sin usuarios ni roles).
- La limpieza de retención es manual (comando); no hay tarea programada.
- Las alertas se evalúan bajo demanda; no hay notificaciones externas ni
  historial de alertas.

## Próximos pasos

1. Adaptador de la fuente real (solo lectura, credenciales por entorno),
   implementando los contratos de `app/adapters/sources.py`; opciones
   evaluadas y recomendaciones en `docs/real-source-integration.md`.
2. Programación opcional de la limpieza de retención.
3. Historial y silenciamiento de alertas; notificaciones opcionales.
4. Motor de recomendaciones de distribución de canales (solo sugerencias,
   nunca acciones automáticas).
