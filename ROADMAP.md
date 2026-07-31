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

**Estado: Fase 1 implementada**

- [x] FastAPI modular con configuración tipada.
- [x] Persistencia PostgreSQL con SQLAlchemy y Alembic.
- [x] Scheduler de recolección en proceso único.
- [x] Adaptador mock determinista.
- [x] Históricos de servidores, canales y ejecuciones.
- [x] API key para endpoints internos y healthcheck público.
- [ ] Versionado formal de contratos API.
- [ ] Pruebas de contrato compartidas con el frontend.
- [ ] Definir una estrategia de ejecución del scheduler cuando existan
  múltiples réplicas.

## 3. Frontend

**Estado: fundación visual implementada**

- [x] React 19 + Vite + TypeScript.
- [x] React Router con rutas Dashboard, Servers, Channels, Alerts y Settings.
- [x] Shell responsive con Sidebar, Topbar y layout principal.
- [x] Tema oscuro y tokens visuales base con TailwindCSS.
- [x] Estado de UI inicial con Zustand.
- [x] Fronteras preparadas para TanStack Query y Axios sin requests.
- [ ] Definir sistema de diseño compartido y accesibilidad AA.
- [ ] Añadir testing de componentes y navegación.
- [ ] Añadir manejo de errores y estados loading/empty/error.

## 4. Dashboard

**Estado: placeholders mock**

- [x] Tarjetas de CPU, RAM, disco, Network IN y Network OUT.
- [x] Tarjetas de servidores, canales, alertas y estado general.
- [x] Gráficos mock de carga y tráfico con Recharts.
- [x] Actividad reciente y tabla de salud de servidores.
- [ ] Conectar métricas reales con un selector de rango temporal.
- [ ] Añadir drill-down de servidor y canal.
- [ ] Diseñar estados de carga, vacío y datos obsoletos.

## 5. Integración API

**Estado: pendiente**

- [ ] Acordar contratos de lectura entre FastAPI y frontend.
- [ ] Implementar funciones tipadas en `frontend/src/services/`.
- [ ] Crear hooks TanStack Query por recurso.
- [ ] Configurar autenticación de lectura sin exponer secretos en el bundle.
- [ ] Manejar cache, invalidación, retries y errores de red.
- [ ] Añadir un entorno local explícito para el proxy de Vite.

## 6. Métricas

**Estado: pendiente**

- [ ] Servidores: CPU, RAM, disco, red, uptime y capacidad.
- [ ] Canales: viewers, bitrate, estado y output estimado.
- [ ] Históricos con rangos, agregaciones y paginación.
- [ ] Comparación entre periodos y detección de datos obsoletos.
- [ ] Optimizar visualizaciones para datasets grandes.

## 7. Alertas

**Estado: contrato inicial en backend; UI mock**

- [x] Umbrales internos de solo lectura en el backend.
- [x] Vista placeholder de alertas en el frontend.
- [ ] Consumir alertas reales con severidad y timestamps.
- [ ] Filtros por severidad, recurso, estado y periodo.
- [ ] Detalle de causa y contexto histórico.
- [ ] Integrar notificaciones externas solo después de definir permisos y
  auditoría.

## 8. Optimizer

**Estado: diseño futuro**

- [ ] Calcular capacidad disponible por servidor.
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
