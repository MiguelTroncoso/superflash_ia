# Integración de fuentes reales de monitoreo

Estado: la fuente de **infraestructura Prometheus ya está implementada**
(`PrometheusInfrastructureAdapter`); la de **streaming** sigue en diseño
(solo mock). El adaptador Prometheus no está conectado a ningún servidor
real: se activa por configuración y aquí se documenta cómo hacerlo.
Este documento define cómo evaluar e integrar fuentes reales manteniendo
la plataforma **estrictamente de solo lectura**.

## Principios innegociables

1. **Solo lectura**: un adaptador consulta datos; jamás modifica la
   fuente, mueve canales, cambia configuraciones ni ejecuta acciones.
2. **Credenciales solo por entorno**: URL, tokens y usuarios llegan por
   variables declaradas en `Settings`; nunca en el código, el
   repositorio ni los logs.
3. **Destinos fijos por configuración**: la API de esta plataforma no
   acepta URLs arbitrarias de terceros; el destino de cada fuente se
   fija en el despliegue.
4. **Sin ejecución remota**: no se implementará SSH interactivo, ni
   comandos remotos, ni agentes con capacidad de escritura.
5. **Cuentas de mínimo privilegio**: si la fuente soporta usuarios, se
   usa uno de solo lectura creado específicamente para el monitoreo.

## Opciones de integración evaluadas

| Opción | Seguridad | Dificultad | Datos disponibles | Recomendación |
|---|---|---|---|---|
| **API oficial del panel** | **Alta**: token con permisos de lectura, TLS, superficie controlada y auditable | Baja–media: HTTP + JSON, paginación y rate limits | Inventario de servidores y canales, espectadores, bitrates, estado de streams: exactamente el dominio de esta plataforma | ✅ **Primera opción** para la fuente de *streaming*. Es el contrato soportado por el proveedor y el único que conoce los canales |
| **Prometheus (node_exporter)** | **Alta**: endpoint de solo lectura por diseño, fácil de restringir por red/firewall | Media: desplegar exporters + consultas PromQL | CPU, RAM, disco, red, load, uptime con excelente resolución histórica | ✅ **Primera opción** para la fuente de *infraestructura* si se pueden instalar exporters |
| **Netdata** | Alta–media: API HTTP local de solo lectura; conviene restringirla a la red interna | Baja: viene con la API lista, sin configuración extra | CPU, RAM, disco, red, load, uptime en tiempo real; retención histórica limitada por defecto | ✅ Buena alternativa a Prometheus cuando ya está instalado o se busca lo más simple |
| **SSH solo lectura** | **Media–baja**: aunque la cuenta sea restringida, implica gestionar claves con acceso shell a producción; difícil de auditar y de limitar de verdad | Media: parsear salida de comandos frágiles ante cambios del sistema | Todo lo que exponga el sistema operativo | ⚠️ **Evitar**. Contradice el principio "sin ejecución remota" de este proyecto. Solo considerarlo como último recurso temporal y con cuenta forzada a comandos fijos |
| **SNMP** | Media: v3 con autenticación es aceptable; v1/v2c viaja sin cifrar | Media–alta: MIBs, OIDs y herramientas menos comunes en stacks modernos | CPU, RAM, interfaces de red, uptime; granularidad limitada | ➖ Solo si el equipamiento ya lo expone (routers, appliances) y no hay opción HTTP |
| **Lectura directa de la BD del panel** | **Baja**: acopla la plataforma al esquema interno de un producto ajeno; riesgo de bloqueos y de romperse en cada actualización del panel; requiere credenciales de BD de producción | Baja al inicio, **alta a largo plazo** (esquema no documentado ni estable) | Potencialmente todo lo que guarda el panel | ❌ **Descartada** salvo que el proveedor la documente oficialmente como interfaz de solo lectura (p. ej. una réplica dedicada) |

### Recomendación global

- **Streaming**: API oficial del panel (`STREAMING_SOURCE=panel`, futuro).
- **Infraestructura**: Prometheus (`INFRASTRUCTURE_SOURCE=prometheus`,
  **ya implementado**); Netdata como alternativa (`netdata`, futuro).
- SSH, SNMP y lectura directa de BD quedan fuera del plan salvo
  restricciones fuertes del entorno, y siempre bajo los principios de
  arriba.

## Fuente de infraestructura: Prometheus (implementada)

`PrometheusInfrastructureAdapter` (`app/adapters/prometheus.py`) consulta
la API HTTP de Prometheus (`GET /api/v1/query`, **solo GET**) y normaliza
las métricas estándar de node_exporter al contrato
`InfrastructureMetricsAdapter`.

**Configuración** (variables de entorno, ver `.env.example`):

| Variable | Descripción |
|---|---|
| `INFRASTRUCTURE_SOURCE=prometheus` | Activa esta fuente |
| `PROMETHEUS_URL` | URL base del servidor Prometheus (obligatoria) |
| `PROMETHEUS_TIMEOUT_SECONDS` | Timeout por consulta (default 10) |
| `PROMETHEUS_BEARER_TOKEN` | Token opcional (`Authorization: Bearer`), nunca se loguea |
| `PROMETHEUS_TLS_VERIFY` | Verificación TLS (default true; **obligatoria** en producción) |
| `INFRASTRUCTURE_INVENTORY_FILE` | Ruta del inventario local YAML/JSON (obligatoria) |

**Inventario local** (`app/adapters/inventory.py`): archivo YAML o JSON
**no versionado** que lista los servidores a monitorear y su etiqueta
`instance` de Prometheus. El repositorio solo incluye
`config/inventory.example.yaml` (con direcciones de documentación
RFC 5737). El campo `node_exporter_instance` se valida contra un patrón
que impide caracteres con significado en PromQL (evita inyección de
consultas).

**Métricas normalizadas** (PromQL en `build_queries()`):

| Campo | Fuente node_exporter |
|---|---|
| `cpu_percent` | `100 * (1 - avg(rate(node_cpu_seconds_total{mode="idle"}[5m])))` |
| `memory_percent` | `100 * (1 - MemAvailable / MemTotal)` |
| `disk_percent` | `max(1 - node_filesystem_avail / size)` (excluye tmpfs/overlay…) |
| `input_mbps` / `output_mbps` | `rate(node_network_*_bytes_total[5m]) * 8 / 1e6` (excluye lo/veth/docker) |
| `load_average_1m/5m/15m` | `node_load1/5/15` |
| `uptime_seconds` | `time() - node_boot_time_seconds` |
| `status` | derivado de `up` |

**Comportamiento ante fallos** (solo lectura, sin fabricar datos):

- Un host con `up == 0` o sin alguna métrica esencial (CPU, RAM, red)
  **no emite muestra** — no se inventan ceros; la alerta de "servidor sin
  muestra reciente" lo hará visible.
- Un host que falla (timeout, conexión rechazada, respuesta malformada)
  se omite y **no bloquea** a los demás.
- Si **todos** los hosts fallan, la pasada lanza `PrometheusSourceError`
  y la ejecución queda registrada como `error`.
- 401/403 lanzan `PrometheusAuthError` sin exponer el token.

**Netdata como alternativa**: expone una API HTTP de solo lectura
(`/api/v1/data`) con las mismas métricas. La integración sería un
`NetdataInfrastructureAdapter` análogo (mismo contrato, distinto cliente
y normalización); no está implementada todavía.

## Contratos a implementar

Una fuente real implementa una (o ambas) de estas interfaces de
`app/adapters/sources.py`:

- `InfrastructureMetricsAdapter`: `get_servers()` +
  `get_infrastructure_metrics()` → CPU, RAM, disco, tráfico de entrada y
  salida, load average, uptime y estado del servidor
  (`InfrastructureMetricSnapshot`).
- `StreamingMetricsAdapter`: `get_channels()` +
  `get_streaming_metrics()` → espectadores, bitrate estimado y estado
  por canal (`StreamingChannelMetricSnapshot`).

`CompositeMonitoringAdapter` (`app/adapters/composite.py`) une ambas
fuentes hacia el pipeline de recolección existente sin tocar
`CollectionService` ni el esquema de base de datos: las conexiones y
streams por servidor se derivan de la muestra de streaming.

## Pasos para añadir una fuente real

1. **Variables de entorno**: declarar en `Settings` (p. ej.
   `PANEL_API_URL`, `PANEL_API_TOKEN`) y en `.env.example` **sin
   valores**. Nunca commitear un `.env` real.
2. **Adaptador**: nuevo módulo `app/adapters/<fuente>.py` implementando
   la interfaz correspondiente. Timeouts explícitos, reintentos
   acotados y validación Pydantic en la frontera (los snapshots ya la
   imponen). No loguear tokens ni URLs con credenciales.
3. **Registro**: añadir el identificador en `factory.py`
   (`get_infrastructure_adapter` / `get_streaming_adapter`) y al
   `Literal` correspondiente de `Settings`.
4. **Diagnóstico sin persistencia**: verificar con
   `python -m app.tasks.diagnose_source` que la fuente entrega datos
   coherentes. Este comando no escribe en la base de datos.
5. **Pruebas**: tests unitarios con respuestas grabadas/mockeadas de la
   fuente (sin red en CI) cubriendo datos válidos, errores HTTP y datos
   malformados.
6. **Recolección en sombra**: activar `MONITORING_ADAPTER=composite` en
   un entorno de staging y comparar varios días de muestras contra lo
   esperado antes de considerarla fuente primaria.
7. **Producción**: cambiar la configuración del despliegue; el código no
   cambia.

## Qué NO se hará

- Escribir hacia el panel o los servidores monitoreados.
- Ejecutar comandos remotos o abrir sesiones SSH desde la aplicación.
- Aceptar URLs de fuentes vía API HTTP (solo configuración de despliegue).
- Guardar credenciales en el repositorio o en la base de datos.
- Mover canales automáticamente: cualquier recomendación futura será
  informativa y su aplicación quedará siempre en manos humanas.
