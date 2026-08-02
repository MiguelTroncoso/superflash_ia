# SuperFlash Monitor — Roadmap técnico

Este roadmap mantiene la evolución del sistema por capas. Cada fase debe
preservar el principio de solo lectura sobre la infraestructura monitoreada y
evitar acoplar el frontend directamente al dominio o a una fuente externa.

## 1. Infraestructura

**Estado: base preparada**

- [x] Dockerfile y Compose de producción para API, PostgreSQL y Nginx.
- [x] Redes separadas, healthchecks y volumen persistente de PostgreSQL.
- [x] Scripts operativos de despliegue, backup y restauración.
- [x] Guía de instalación para Ubuntu 24.04.
- [ ] Automatizar backups con una política operativa del host.
- [ ] Incorporar observabilidad de contenedores y rotación de logs.
- [ ] Definir estrategia de secretos para entornos gestionados.

## 2. Backend

**Estado: núcleo v1 implementado**

- [x] FastAPI modular con configuración tipada.
- [x] Persistencia PostgreSQL con SQLAlchemy y Alembic.
- [x] Scheduler de recolección en proceso único.
- [x] Adaptador mock determinista.
- [x] Históricos de servidores, canales y ejecuciones.
- [x] API key para endpoints internos y healthcheck público.
- [x] Inventario CRUD de servidores con proveedor, datacenter, grupo, etiquetas,
  tipo, red, Prometheus y heartbeat.
- [x] Provider Prometheus por servidor, manteniendo adapter mock compatible.
- [x] Migraciones para inventario, métricas extendidas y alertas persistentes.
- [ ] Versionado formal de contratos API.
- [ ] Pruebas de contrato compartidas con el frontend.
- [ ] Definir una estrategia de ejecución del scheduler cuando existan
  múltiples réplicas.

## 3. Frontend

**Estado: foundation conectada a API**

- [x] React 19 + Vite + TypeScript.
- [x] React Router con rutas Dashboard, Servers, Channels, Alerts y Settings.
- [x] Shell responsive con Sidebar, Topbar y layout principal.
- [x] Tema oscuro y tokens visuales base con TailwindCSS.
- [x] Estado de UI inicial con Zustand.
- [x] Servicios tipados y hooks TanStack Query por recurso.
- [x] Tabla y detalle de servidores, canales, balance, recomendaciones y alertas.
- [x] Estados loading, empty, error, stale, última actualización y retry.
- [ ] Definir sistema de diseño compartido y accesibilidad AA.
- [ ] Añadir testing de componentes y navegación.
- [ ] Añadir manejo de errores y estados loading/empty/error.

## 4. Dashboard

**Estado: datos reales de lectura**

- [x] Tarjetas de CPU, RAM, disco, Network IN y Network OUT.
- [x] Tarjetas de servidores, canales, alertas y estado general.
- [x] Gráficos de carga y tráfico con las últimas 24 muestras reales.
- [x] Actividad reciente y tabla de salud de servidores.
- [ ] Conectar métricas reales con selector de rango temporal y agregaciones.
- [ ] Añadir drill-down de servidor y canal.
- [ ] Diseñar estados de carga, vacío y datos obsoletos.

## 5. Integración API

**Estado: integración inicial implementada**

- [x] Contratos de lectura entre FastAPI y frontend.
- [x] Funciones tipadas en `frontend/src/services/`.
- [x] Hooks TanStack Query por recurso.
- [x] Proxy con `X-API-Key` server-side sin exponer secretos en el bundle.
- [x] Cache, refresh, retries y errores de red.
- [ ] Añadir un entorno local explícito para el proxy de Vite.

## 6. Métricas

**Estado: señales v1 implementadas**

- [x] Servidores: CPU, RAM, swap, filesystem, IO, red, load, uptime y capacidad.
- [x] Canales: viewers, bitrate, estado y output estimado.
- [ ] Históricos con rangos, agregaciones y paginación.
- [ ] Comparación entre periodos y detección de datos obsoletos.
- [ ] Optimizar visualizaciones para datasets grandes.

## 7. Alertas

**Estado: persistencia y UI conectadas**

- [x] Umbrales internos de solo lectura en el backend.
- [x] Vista de alertas persistidas en el frontend.
- [x] Alertas reales con severidad, estado y timestamps.
- [x] Filtros por estado y contexto de servidor.
- [ ] Detalle de causa y contexto histórico.
- [ ] Integrar notificaciones externas solo después de definir permisos y
  auditoría.

## 8. Optimizer

**Estado: balance y reglas iniciales implementados**

- [x] Calcular capacidad disponible por servidor.
- [x] Exponer `/api/v1/balance` y `/api/v1/recommendations`.
- [x] Reglas explicables para saturación, heartbeat, ausencia de datos y baja utilización.
- [ ] Simular escenarios de distribución de canales.
- [ ] Generar recomendaciones explicables y solo informativas.
- [ ] Mostrar impacto estimado, confianza y datos usados.
- [ ] Mantener cualquier aplicación de cambios fuera de esta plataforma.

## 9. Inteligencia Artificial

**Estado: investigación futura**

- [ ] Definir casos de uso con valor operativo medible.
- [ ] Preparar datasets históricos anonimizados y trazables.
- [ ] Evaluar modelos para resumen, diagnóstico y recomendaciones.
- [ ] Añadir revisión humana, límites de confianza y auditoría.
- [ ] Nunca permitir que un modelo ejecute acciones sobre infraestructura.

## Criterios de avance

Una fase puede avanzar cuando tenga contratos claros, pruebas automatizadas,
telemetría suficiente y una estrategia de rollback. Las fases de frontend no
deben modificar la infraestructura de producción; las fases de integración no
deben convertir el sistema en un agente de escritura remota.
