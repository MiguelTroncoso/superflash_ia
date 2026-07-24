#!/usr/bin/env bash

set -Eeuo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="${COMPOSE_FILE:-$ROOT_DIR/docker-compose.prod.yml}"
ENV_FILE="${ENV_FILE:-$ROOT_DIR/.env.production}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP_FILE="${1:-$ROOT_DIR/backups/superflash_${TIMESTAMP}.dump}"

if ! command -v docker >/dev/null 2>&1; then
    echo "ERROR: Docker no está instalado o no está en PATH." >&2
    exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
    echo "ERROR: falta $ENV_FILE." >&2
    exit 1
fi

if [[ ! -f "$COMPOSE_FILE" ]]; then
    echo "ERROR: falta el archivo Compose: $COMPOSE_FILE" >&2
    exit 1
fi

if [[ -e "$BACKUP_FILE" ]]; then
    echo "ERROR: el archivo de backup ya existe: $BACKUP_FILE" >&2
    exit 1
fi

umask 077
mkdir -p "$(dirname -- "$BACKUP_FILE")"
cd "$ROOT_DIR"
compose=(docker compose --env-file "$ENV_FILE" --file "$COMPOSE_FILE")

"${compose[@]}" config --quiet
"${compose[@]}" up -d --wait db

echo "Creando backup PostgreSQL en $BACKUP_FILE..."
"${compose[@]}" exec -T db sh -c \
    'pg_dump --format=custom --no-owner --no-acl --dbname="$POSTGRES_DB" --username="$POSTGRES_USER"' \
    > "$BACKUP_FILE"

if [[ ! -s "$BACKUP_FILE" ]]; then
    rm -f -- "$BACKUP_FILE"
    echo "ERROR: el backup quedó vacío." >&2
    exit 1
fi

chmod 600 "$BACKUP_FILE"
echo "Backup completado: $BACKUP_FILE"
