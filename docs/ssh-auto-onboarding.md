# SSH auto-onboarding seguro

El onboarding prepara únicamente el inventario local de SuperFlash Monitor,
Node Exporter y las reglas que el propio instalador administra. No existe un
terminal remoto ni se aceptan comandos arbitrarios desde el navegador. Xtream,
Prometheus de escritura y acciones sobre streams quedan fuera de este flujo.

## Preparación del servidor Monitor

1. Cree el archivo de host keys fuera del repositorio, con permisos `600`:

   ```bash
   mkdir -p secrets
   chmod 700 secrets
   ssh-keyscan -t ed25519,rsa SERVIDOR_REAL > secrets/ssh_known_hosts
   chmod 600 secrets/ssh_known_hosts
   ```

   La salida debe revisarse contra la consola del proveedor o una fuente
   independiente antes de habilitar el onboarding. El servicio usa
   `RejectPolicy` y nunca acepta automáticamente una host key desconocida.

2. Configure en `.env.production`:

   ```dotenv
   ONBOARDING_ENABLED=true
   ONBOARDING_MONITOR_IP=178.104.98.19
   SSH_KNOWN_HOSTS_HOST_PATH=./secrets/ssh_known_hosts
   SSH_KNOWN_HOSTS_FILE=/etc/ssh/ssh_known_hosts
   NODE_EXPORTER_VERSION=
   ```

   `ONBOARDING_MONITOR_IP` es la única fuente permitida para el acceso al
   puerto 9100. Además, configure el security group del proveedor para
   permitir TCP/9100 únicamente desde esa IP. El script no elimina políticas
   ni reglas preexistentes.

## Flujo desde la web

En `Servers → Add server`, complete nombre, IP/hostname, puerto SSH, usuario,
método de autenticación y los metadatos financieros/operativos disponibles.
La clave privada o contraseña vive solo en memoria durante la solicitud; se
borra del estado del formulario al comenzar el trabajo y nunca se persiste,
devuelve o escribe en logs.

El proceso ejecuta, en orden: conexión SSH y host key, autenticación/sudo,
precheck del sistema, descubrimiento de hardware e interfaz, instalación o
actualización idempotente de Node Exporter, firewall, verificación de métricas,
snapshot de inventario, validación Prometheus y diagnóstico final. El modal se
actualiza automáticamente y sobrevive a un refresh porque el estado se lee de
`GET /api/v1/onboarding/{id}`.

Estados terminales admiten retry. `Rollback managed changes` elimina solo el
servicio/binario y las reglas marcadas por SuperFlash; no revierte cambios
externos ni reinicia el servidor completo. Cancelar evita continuar en el
siguiente punto de control.

## Scripts y operación en Ubuntu 22.04 x86_64

Los scripts versionados son `install-node-exporter.sh`,
`update-node-exporter.sh`, `remove-node-exporter.sh` y
`configure-node-exporter-firewall.sh`. Son idempotentes, usan systemd,
validan arquitectura, checksum y servicio, y dejan el puerto 9100 sin
exposición pública. También existen scripts mínimos del agente opcional, que
no se instalan automáticamente en este flujo.

Para actualizar, defina `NODE_EXPORTER_VERSION` a una versión aprobada y use
retry o el proceso de onboarding; una instalación correcta no se reinstala si
la versión ya coincide. Para retirar el exporter use rollback o el script de
remoción desde una operación controlada. Revise siempre el diagnóstico y el
firewall del proveedor después de cada cambio.

## API y permisos

Todas las rutas `/api/v1` requieren `X-API-Key`; `/health` continúa público.
Las credenciales no aparecen en los esquemas de respuesta. El API key solo se
inyecta en Nginx en producción. La autorización fina por permisos de operador
queda pendiente de la capa de identidad existente; mientras tanto, el acceso
al router protegido debe restringirse a operadores autorizados.

Rutas del flujo:

- `POST /api/v1/onboarding`
- `GET /api/v1/onboarding/{id}`
- `GET /api/v1/onboarding/{id}/audit`
- `POST /api/v1/onboarding/{id}/retry`
- `POST /api/v1/onboarding/{id}/cancel`
- `POST /api/v1/onboarding/{id}/rollback`
- `GET /api/v1/onboarding/server/{server_id}`

El mock continúa disponible si `INFRASTRUCTURE_SOURCE=mock`. Prometheus solo se
consulta mediante GET y las métricas reales se usan únicamente cuando el
servidor tiene una fuente válida.
