# Imagen de la API de SuperFlash Monitor.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Usuario sin privilegios para ejecutar la aplicación.
RUN groupadd --gid 1000 appuser && useradd --uid 1000 --gid 1000 --create-home appuser

WORKDIR /srv/app

COPY pyproject.toml README.md ./
COPY app ./app
COPY alembic ./alembic
COPY scripts ./scripts
COPY alembic.ini ./

RUN pip install .

USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
