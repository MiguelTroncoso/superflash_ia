#!/bin/sh
set -eu

secret_file=/run/secrets/superflash_api_key
template=/etc/nginx/templates/default.conf.template
target=/etc/nginx/conf.d/default.conf

if [ ! -r "$secret_file" ]; then
    echo "Nginx secret is missing: $secret_file" >&2
    exit 1
fi

api_key=$(tr -d '\r\n' < "$secret_file")
if [ -z "$api_key" ]; then
    echo "Nginx secret is empty: $secret_file" >&2
    exit 1
fi

# Escape the replacement characters used by sed. The API key remains only in
# the generated Nginx configuration inside this container.
escaped_api_key=$(printf '%s' "$api_key" | sed 's/[\\&|]/\\&/g')
sed "s|__SUPERFLASH_API_KEY__|$escaped_api_key|g" "$template" > "$target"
unset api_key escaped_api_key
