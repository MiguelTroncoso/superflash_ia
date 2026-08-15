# Infrastructure Intelligence Engine

El motor de Sprint 5A es una capa local, determinista y de solo lectura sobre el inventario y las últimas métricas persistidas. La única escritura nueva es el historial local de `simulations`; una simulación no modifica servidores, canales, fuentes externas ni cargas activas.

## Contrato de capacidad

Cada servidor puede declarar `network_capacity_mbps`, `operational_network_limit_mbps`, `recommended_network_limit_mbps` y `minimum_network_reserve_mbps`. Si los tres límites operativos son nulos, el cálculo usa la capacidad física como fallback explícito. No existe un límite codificado por tipo de servidor.

El motor usa `ServerMetric.output_mbps` como carga de red observada. Para una decisión confiable deben existir, como mínimo:

- capacidad física y límites operativos configurados;
- una última métrica con `collected_at`, `output_mbps`, CPU, memoria y disco;
- costes con moneda homogénea si se quiere comparar totales.

La respuesta marca `data_quality=insufficient_data` y recomendaciones de baja confianza cuando falta alguno de estos insumos. No sustituye datos ausentes por números simulados.

## Futuras fuentes de datos

La integración real de Prometheus podrá alimentar un adaptador normalizado con:

```text
server_id, collected_at, cpu_percent, memory_percent, swap_percent,
filesystem_percent, disk_percent, io_read_mbps, io_write_mbps,
input_mbps, output_mbps, load_average_1m, load_average_5m,
load_average_15m, uptime_seconds
```

La integración real de Xtream podrá aportar:

```text
source_id, external_id, channel_id, channel_type, event_id,
viewers, bitrate_mbps, estimated_output_mbps, active, collected_at
```

El frontend no recibe tokens de Prometheus/Xtream. Las URLs privadas y credenciales continúan siendo configuración del backend/adaptador y no se copian a contratos públicos.

## Distribución y simulación

El algoritmo ordena las unidades de carga de mayor a menor y asigna cada una al servidor con mayor margen libre que pueda contenerla dentro de `recommended_limit_mbps - minimum_network_reserve_mbps`. Reporta unidades no asignadas y nunca excede límites para marcar una simulación como factible.

Una petición puede usar unidades genéricas `channel`, `stream`, `category`, `group`, `event`, `traffic_block` o `server_aggregate`. Los escenarios de reemplazo, baja de coste y capacidad adicional son virtuales y quedan guardados solo en `simulations`.

## Fixture

`config/infrastructure-intelligence.example.yaml` documenta los servidores de demostración y sus costes aproximados. Es una fixture explícita: no se carga en producción ni contiene secretos.
