"""Configuración de logging consistente para API y tareas de línea de comandos.

Formato clave=valor sencillo y estable, pensado para ser legible y fácil
de ingerir por agregadores de logs. Nunca se registran tokens ni
credenciales: los adaptadores y servicios solo loguean identificadores
externos y mensajes de error.
"""

import logging
import sys

_FORMAT = "%(asctime)s level=%(levelname)s logger=%(name)s %(message)s"


def setup_logging(level: str = "INFO") -> None:
    """Inicializa el logging raíz de la aplicación.

    Args:
        level: Nivel de logging (``DEBUG``, ``INFO``, ``WARNING``...).
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_FORMAT))

    root = logging.getLogger()
    root.setLevel(level.upper())
    # Evita handlers duplicados si se llama más de una vez (tests, reload).
    root.handlers.clear()
    root.addHandler(handler)

    # Reduce ruido de librerías de terceros en niveles bajos.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
