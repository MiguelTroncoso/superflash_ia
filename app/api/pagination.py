"""Paginación por cursor para los históricos de métricas.

El cursor es opaco: base64 URL-safe de ``<collected_at ISO>|<id>``. El
orden estable es ``(collected_at DESC, id DESC)``; una página se pide
con ``?cursor=...`` y el cursor de la siguiente llega en la cabecera de
respuesta ``X-Next-Cursor`` (ausente en la última página). El cuerpo
sigue siendo la lista de siempre, por lo que ``limit`` y los clientes
existentes funcionan sin cambios durante la transición.
"""

import base64
import binascii
from datetime import datetime

from fastapi import HTTPException, status

NEXT_CURSOR_HEADER = "X-Next-Cursor"

MetricCursor = tuple[datetime, int]


def encode_cursor(collected_at: datetime, item_id: int) -> str:
    """Codifica la posición (collected_at, id) como cursor opaco."""
    raw = f"{collected_at.isoformat()}|{item_id}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def decode_cursor(value: str) -> MetricCursor:
    """Decodifica un cursor; 400 si está malformado."""
    try:
        raw = base64.urlsafe_b64decode(value.encode()).decode()
        collected_at_raw, _, item_id_raw = raw.partition("|")
        return datetime.fromisoformat(collected_at_raw), int(item_id_raw)
    except (ValueError, binascii.Error, UnicodeDecodeError) as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Cursor de paginación inválido"
        ) from error
