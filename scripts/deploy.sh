#!/usr/bin/env bash

set -Eeuo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="${COMPOSE_FILE:-$ROOT_DIR/docker-compose.prod.yml}"
ENV_FILE="${ENV_FILE:-$ROOT_DIR/.env.production}"

if ! command -v docker >/dev/null 2>&1; then
    echo "ERROR: Docker no está instalado o no está en PATH." >&2
    exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
    echo "ERROR: el plugin Docker Compose no está disponible." >&2
    exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
    echo "ERROR: falta $ENV_FILE. Copia .env.production.example y completa sus valores." >&2
    exit 1
fi

if [[ ! -f "$COMPOSE_FILE" ]]; then
    echo "ERROR: falta el archivo Compose: $COMPOSE_FILE" >&2
    exit 1
fi

if grep -Eq '^(POSTGRES_PASSWORD|API_KEY)=REPLACE_WITH_' "$ENV_FILE"; then
    echo "ERROR: reemplaza los valores REPLACE_WITH_ de $ENV_FILE antes de desplegar." >&2
    exit 1
fi

cd "$ROOT_DIR"
compose=(docker compose --env-file "$ENV_FILE" --file "$COMPOSE_FILE")

echo "Validando configuración de producción..."
"${compose[@]}" config --quiet

echo "Construyendo las imágenes de API y migraciones..."
"${compose[@]}" build api migrations

echo "Iniciando PostgreSQL y esperando su healthcheck..."
"${compose[@]}" up -d --wait db

echo "Aplicando migraciones Alembic..."
"${compose[@]}" run --rm --no-deps migrations

echo "Iniciando API y Nginx..."
# Recrear ambos mantiene vigente la resolución DNS de `api` en el upstream de
# Nginx cuando la actualización reemplaza el contenedor de FastAPI.
"${compose[@]}" up -d --wait --force-recreate api nginx

echo "Estado final de la stack:"
"${compose[@]}" ps

echo "Validando healthcheck a través de Nginx..."
"${compose[@]}" exec -T nginx sh -c \
    "wget -q -O - http://127.0.0.1/health | grep -q '\"status\":\"ok\"'"

echo "Despliegue completado."
