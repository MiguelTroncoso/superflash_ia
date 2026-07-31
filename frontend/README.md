# SuperFlash Monitor Frontend

Base visual del frontend de SuperFlash Monitor. La aplicación muestra datos
ficticios, no ejecuta llamadas HTTP y ahora puede servirse dentro del stack de
producción a través del servicio `frontend` y el Nginx existente.

## Tecnologías

- React 19 + TypeScript.
- Vite para desarrollo y build.
- React Router para navegación local.
- TanStack Query preparado para la futura capa de datos.
- Axios encapsulado en `services/httpClient.ts`, sin requests en esta fase.
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

Para validar el build estático:

```bash
npm run typecheck
npm run build
npm run preview
```

El Dockerfile construye la imagen estática del frontend. El runtime usa Nginx
interno con fallback SPA mediante `try_files`, pero no ejecuta Vite en modo
desarrollo:

```bash
docker build -t superflash-monitor-frontend ./frontend
docker run --rm -p 8080:80 superflash-monitor-frontend
```

En producción, el servicio se integra mediante
`docker-compose.prod.yml`. El Nginx público enruta `/` al frontend, mientras
`/api/` y `/health` continúan apuntando al backend FastAPI.

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
│   │   └── tables/          # Tablas de datos mock
│   ├── hooks/               # Hooks de presentación
│   ├── layouts/             # Layouts de página
│   ├── pages/               # Dashboard, Servers, Channels, Alerts, Settings
│   ├── routes/              # Mapa de rutas React Router
│   ├── services/            # Frontera para la futura API
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
3. Los componentes de dashboard reciben datos simples y no conocen Axios ni
   la API.
4. `httpClient` y `QueryClient` establecen fronteras de integración sin
   consumir endpoints.
5. Los datos ficticios viven en `utils/mockData.ts`, claramente aislados de
   los tipos y componentes.
6. El estado global se limita a navegación responsive; no se introduce
   autenticación, persistencia ni lógica de negocio.

## Alcance actual

Incluido: shell visual oscuro, sidebar responsive, topbar, rutas, dashboard
mock, tablas, gráficos y placeholders de configuración.

Excluido: login, JWT, llamadas HTTP, WebSockets, integración con FastAPI,
modificaciones de backend, conexión con producción y despliegue.
