# SuperFlash Monitor Frontend

Frontend del SuperFlash Monitor. La aplicación consume los contratos de
lectura de FastAPI mediante Axios y TanStack Query a través del mismo origen
servido por Nginx. No contiene credenciales ni ejecuta acciones sobre la
infraestructura monitoreada.

## Tecnologías

- React 19 + TypeScript + Vite.
- React Router para navegación SPA.
- TanStack Query para cache, refresh, loading, error y stale state.
- Axios para HTTP y Zustand para estado de UI.
- TailwindCSS 4, Recharts y Lucide React.

## Ejecutar localmente

```bash
cd frontend
npm ci
npm run dev
```

Para validar la aplicación:

```bash
npm run typecheck
npm test
npm run build
npm run test:security
npm run preview
```

El Dockerfile produce `dist/` y el runtime sirve únicamente Nginx; no ejecuta
Vite en modo desarrollo:

```bash
docker build -t superflash-monitor-frontend ./frontend
docker run --rm -p 8080:80 superflash-monitor-frontend
```

## API y secreto `X-API-Key`

El navegador llama siempre a `/api/v1/...` en el mismo origen. No se configura
`API_KEY`, `VITE_API_KEY` ni ningún secreto en React, HTML, source maps o el
bundle. Nginx agrega `X-API-Key` solo en el proxy hacia FastAPI usando el
Docker secret disponible en el servidor. `/health` permanece público.

En producción, configura la clave fuera del repositorio, por ejemplo en
`.env.production` con permisos restringidos:

```dotenv
API_KEY=una-clave-larga-generada-en-el-servidor
```

El stack se inicia con:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml up -d --build
```

La clave tampoco debe colocarse en `frontend/`, `VITE_*`, archivos de test
versionados ni logs. El script `npm run test:security` inspecciona el bundle.

## Estructura

```text
frontend/
├── Dockerfile
├── src/
│   ├── app/                 # providers y aplicación raíz
│   ├── assets/              # marca y recursos estáticos
│   ├── components/          # common, dashboard, charts, layout y tables
│   ├── hooks/               # TanStack Query y hooks de presentación
│   ├── layouts/             # layout operativo
│   ├── pages/               # Dashboard, Servers, Channels, Alerts, Balance,
│   │                        # Recommendations y Settings
│   ├── routes/              # React Router
│   ├── services/            # Axios y servicios tipados
│   ├── store/               # estado de UI con Zustand
│   ├── styles/              # tokens y Tailwind
│   ├── types/               # contratos TypeScript
│   └── utils/               # mapeos y formateadores
└── ...
```

## Decisiones de arquitectura

1. `MonitorLayout` concentra el shell visual; las páginas solo conocen su
   contenido.
2. `apiService` centraliza endpoints tipados; cada recurso tiene hooks Query
   independientes y refresh de 60 segundos.
3. Los componentes reciben datos normalizados y no conocen Axios ni la forma
   cruda de las respuestas HTTP.
4. Todas las páginas exponen loading, error, empty, stale, última actualización
   y reintento cuando aplica.
5. Los gráficos del dashboard usan las últimas 24 muestras reales del API.
   No se mantienen mocks de runtime; los mocks restantes están únicamente en
   fixtures de pruebas.
6. La UI de este sprint es de solo lectura. El endpoint de alertas persiste la
   evaluación local, pero el frontend no ejecuta acciones de infraestructura.

## Rutas conectadas

- `/dashboard`: overview, servidores, canales, alertas, colección, health e
  histórico real de servidores.
- `/servers`: inventario, filtros, búsqueda, ordenamiento, paginación y últimas
  métricas.
- `/server/:id`: detalle, filesystem, swap, IO, load, uptime, heartbeat,
  colección, alertas y muestras recientes.
- `/channels`: inventario y última muestra por canal; Xtream no está integrado.
- `/balance`: capacidad y utilización agregada.
- `/recommendations`: reglas deterministas sin IA.
- `/alerts`: ciclo de vida persistido y filtros de estado.
- `/settings`: límites visuales para preferencias futuras.
