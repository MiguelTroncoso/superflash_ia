#!/usr/bin/env bash

set -Eeuo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="${COMPOSE_FILE:-$ROOT_DIR/docker-compose.prod.yml}"
ENV_FILE="${ENV_FILE:-$ROOT_DIR/.env.production}"
BACKUP_FILE="${1:-}"
SERVICES_STOPPED=0

if [[ -z "$BACKUP_FILE" || ! -f "$BACKUP_FILE" ]]; then
    echo "Uso: CONFIRM_RESTORE=YES $0 /ruta/al/backup.dump" >&2
    exit 2
fi

if [[ "${CONFIRM_RESTORE:-}" != "YES" ]]; then
    echo "ERROR: restaurar reemplazará los datos actuales de PostgreSQL." >&2
    echo "Para continuar, vuelve a ejecutar con CONFIRM_RESTORE=YES." >&2
    exit 1
fi

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

cd "$ROOT_DIR"
compose=(docker compose --env-file "$ENV_FILE" --file "$COMPOSE_FILE")

cleanup() {
    if [[ "$SERVICES_STOPPED" -eq 1 ]]; then
        echo "Iniciando nuevamente API y Nginx..."
        "${compose[@]}" up -d --wait --force-recreate api nginx || true
    fi
}
trap cleanup EXIT

"${compose[@]}" config --quiet
"${compose[@]}" up -d --wait db

echo "Validando el formato del backup..."
"${compose[@]}" exec -T db sh -c 'pg_restore --list - >/dev/null' < "$BACKUP_FILE"

echo "Deteniendo API y Nginx para mantener la base consistente..."
"${compose[@]}" stop nginx api
SERVICES_STOPPED=1

echo "Restaurando $BACKUP_FILE..."
"${compose[@]}" exec -T db sh -c \
    'pg_restore --clean --if-exists --no-owner --no-acl --exit-on-error --dbname="$POSTGRES_DB" --username="$POSTGRES_USER"' \
    < "$BACKUP_FILE"

echo "Aplicando migraciones posteriores al restore..."
"${compose[@]}" run --rm --no-deps migrations

echo "Restore completado."
