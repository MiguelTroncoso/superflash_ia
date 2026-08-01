# SuperFlash Monitor Frontend

Frontend del SuperFlash Monitor. El dashboard consume los contratos de lectura
de FastAPI a través de Nginx; solo los gráficos históricos y la actividad
reciente permanecen simulados porque todavía no existe un endpoint adecuado.

## Tecnologías

- React 19 + TypeScript.
- Vite para desarrollo y build.
- React Router para navegación local.
- TanStack Query para cache, estados de carga, errores y datos stale.
- Axios encapsulado en `services/apiService.ts` y `services/httpClient.ts`.
- Zustand para estado de UI.
- TailwindCSS 4 para estilos.
- Recharts para gráficos mock.
- Lucide React para iconografía.

## Ejecutar localmente

Desde la raíz del repositorio:

```bash
cd frontend
npm install
npm run dev
```

Vite mostrará la URL local, normalmente `http://localhost:5173`.

Para validar el build estático y las pruebas:

```bash
npm run typecheck
npm run build
npm test
npm run test:security
npm run preview
```

El Dockerfile construye la imagen estática del frontend. El runtime usa Nginx
interno con fallback SPA mediante `try_files`, pero no ejecuta Vite en modo
desarrollo:

```bash
docker build -t superflash-monitor-frontend ./frontend
docker run --rm -p 8080:80 superflash-monitor-frontend
```

En producción, el servicio se integra mediante `docker-compose.prod.yml`. El
navegador llama al mismo origen (`/api/v1/...`) y nunca conoce `API_KEY`.
Nginx recibe la clave como Docker secret desde la variable `API_KEY` del
servidor, renderiza su configuración al iniciar y la añade únicamente hacia
FastAPI. `/health` permanece público.

Configura la clave solo en el servidor, por ejemplo en un `.env.production`
fuera del repositorio:

```dotenv
API_KEY=una-clave-larga-generada-en-el-servidor
```

Luego inicia el stack con:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml up -d --build
```

No coloques `API_KEY` en `frontend/`, `VITE_*`, HTML, source maps ni código
TypeScript.

## Estructura

```text
frontend/
├── Dockerfile
├── index.html
├── package.json
├── src/
│   ├── app/                 # Composición de providers y aplicación raíz
│   ├── assets/              # Marca y recursos estáticos
│   ├── components/
│   │   ├── charts/          # Gráficos Recharts
│   │   ├── common/          # Primitivas visuales reutilizables
│   │   ├── dashboard/       # Bloques propios del dashboard
│   │   ├── layout/          # Sidebar y topbar
│   │   └── tables/          # Tablas de salud del dashboard
│   ├── hooks/               # Hooks de presentación
│   ├── layouts/             # Layouts de página
│   ├── pages/               # Dashboard, Servers, Channels, Alerts, Settings
│   ├── routes/              # Mapa de rutas React Router
│   ├── services/            # Cliente HTTP y servicios tipados de lectura
│   ├── store/               # Estado global de UI con Zustand
│   ├── styles/              # Tailwind y tokens visuales
│   ├── types/               # Contratos TypeScript
│   └── utils/               # Formateadores y datos ficticios
└── ...
```

## Decisiones de arquitectura

1. `MonitorLayout` concentra el chrome de la aplicación; las páginas solo
   conocen su contenido.
2. Las rutas están separadas de la composición de la aplicación para poder
   añadir guardas, loaders o layouts anidados cuando exista autenticación.
3. Los componentes del dashboard reciben datos mapeados y no conocen Axios ni
   la forma cruda de las respuestas HTTP.
4. `apiService` concentra los endpoints tipados y `useDashboardData` coordina
   cache, refresh, errores, empty y stale con TanStack Query.
5. `utils/mockData.ts` queda aislado para gráficos históricos y actividad sin
   endpoint real; la interfaz los marca como datos simulados.
6. La API sigue siendo de solo lectura desde el frontend; no se agregan
   autenticación, persistencia ni lógica de negocio.

## Alcance actual

Incluido: shell visual oscuro, sidebar responsive, topbar, rutas, dashboard
con datos reales de lectura, estados de UX, tabla de servidores y gráficos
históricos simulados claramente marcados.

Excluido: login, JWT, WebSockets, integración con Prometheus real, acciones de
escritura, modificaciones de backend y despliegue al VPS.
