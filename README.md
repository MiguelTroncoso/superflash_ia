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
  de muestras, aislamiento de errores por elemento y **exclusión mutua**:
  nunca corren dos recolecciones a la vez en el mismo proceso.
- Endpoint interno protegido por **API key** (`COLLECTION_API_KEY`,
  fail-closed) y endpoint de estado (`/api/v1/collection/status`).
- **Scheduler opcional** de recolección periódica (cada 5 minutos por
  defecto), deshabilitado salvo que se active explícitamente.
- **Arquitectura multi-fuente**: contratos separados para métricas de
  infraestructura (`InfrastructureMetricsAdapter`: CPU, RAM, disco, red,
  load, uptime, estado) y de streaming (`StreamingMetricsAdapter`:
  espectadores, bitrate, estado del canal), con mocks de demostración,
  adaptador compuesto (`MONITORING_ADAPTER=composite`) y comando de
  diagnóstico sin persistencia (`python -m app.tasks.diagnose_source`).
- API de consulta: servidores, canales, históricos por rango de fechas y
  resumen agregado (`/api/v1/overview`).
- Migraciones con Alembic y despliegue con Docker Compose.
- CI en GitHub Actions: lint, tipos, pruebas y smoke test end-to-end
  contra PostgreSQL real (incluido el ciclo de migraciones).
- Sin fuente real, sin escritura externa.

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
| GET  | `/api/v1/channels` | Canales (filtros `server_id`, `category`, `enabled`) |
| GET  | `/api/v1/channels/{id}/metrics` | Histórico del canal (`start`, `end`, `limit`) |
| POST | `/api/v1/collection/run` | **Interno, requiere API key**: ejecuta una recolección |
| GET  | `/api/v1/collection/status` | Estado del recolector y del scheduler |
| GET  | `/api/v1/overview` | Estadísticas agregadas actuales |

### Autenticación del endpoint interno

`POST /api/v1/collection/run` exige la cabecera `X-API-Key` con el valor
de `COLLECTION_API_KEY` (solo variable de entorno, nunca en el código).
La política es *fail-closed*: si la variable no está configurada, el
endpoint responde `503` en lugar de quedar abierto. Clave ausente o
incorrecta → `401`. Si ya hay una recolección en curso → `409`.

### Recolección automática (scheduler)

Con `SCHEDULER_ENABLED=true` la API ejecuta una recolección cada
`COLLECTION_INTERVAL_SECONDS` (300 = 5 minutos, mínimo 5). Está
**deshabilitado por defecto** y comparte el mismo lock que el endpoint
manual, por lo que un ciclo nunca se solapa con una ejecución manual: el
que llegue segundo se omite y queda registrado en el log.
`GET /api/v1/collection/status` muestra el próximo ciclo (`next_run_at`).

El scheduler es de proceso único: actívalo solo con una instancia de la
API. Con réplicas múltiples se usará un programador externo o un lock
distribuido (ver `docs/architecture.md`).

## Ejemplo de recolección

```bash
# Vía API (requiere la clave configurada en COLLECTION_API_KEY)
curl -X POST -H "X-API-Key: $COLLECTION_API_KEY" \
    http://localhost:8000/api/v1/collection/run

# Estado del recolector
curl http://localhost:8000/api/v1/collection/status

# Vía CLI (mismo comportamiento, sin pasar por HTTP; --seed opcional)
python -m app.tasks.collect --seed 42

# Diagnóstico de fuentes: valida configuración y muestra qué datos
# entregaría cada fuente, SIN escribir en la base de datos.
python -m app.tasks.diagnose_source
python -m app.tasks.diagnose_source --source infrastructure
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
- **Runner con lock de proceso**: el endpoint manual y el scheduler pasan
  por el mismo `CollectionRunner`; la segunda recolección simultánea se
  rechaza (409) o se omite, nunca se ejecuta en paralelo.
- **API key fail-closed**: sin `COLLECTION_API_KEY` el endpoint interno
  responde 503; la comparación usa `secrets.compare_digest` y la clave
  jamás se loguea.
- **Migraciones en contenedor one-shot**: una sola ejecución de
  `alembic upgrade` por despliegue, sin carreras entre réplicas.
- **Esquema portable (PostgreSQL/SQLite)**: los tests corren contra
  SQLite en memoria sin necesitar PostgreSQL.
- **Timestamps siempre en UTC** (`TIMESTAMPTZ`); los rangos sin zona
  horaria se interpretan como UTC.

## Limitaciones actuales

- Solo datos simulados: no existe todavía adaptador para el panel real.
- El lock de recolección y el estado de `/collection/status` viven en
  memoria del proceso: válidos para **una** instancia de la API. Con
  réplicas se necesitará un lock distribuido (p. ej. `pg_advisory_lock`).
- El scheduler es in-process y de instancia única.
- Los endpoints de consulta (GET) no requieren autenticación: pensados
  para red privada.
- Sin paginación por cursor en históricos (solo `limit` + rango).
- Sin retención/compactación de métricas antiguas.

## Próximos pasos

1. Adaptador de la fuente real (solo lectura, credenciales por entorno),
   implementando los contratos de `app/adapters/sources.py`; opciones
   evaluadas y recomendaciones en `docs/real-source-integration.md`.
2. Lock distribuido y estado compartido para despliegues con réplicas.
3. Autenticación para el resto de endpoints si salen de la red privada.
4. Política de retención de métricas históricas.
5. Motor de recomendaciones de distribución de canales (solo sugerencias,
   nunca acciones automáticas).
