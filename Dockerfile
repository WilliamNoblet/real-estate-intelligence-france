# Image applicative unique, partagée par les services api / worker / dashboard.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH="/app/.venv/bin:$PATH"

# postgresql-client : utilisé par make backup/restore (pg_dump / pg_restore / pg_isready).
RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# uv : gestionnaire de dépendances rapide + builds reproductibles via uv.lock.
RUN pip install --no-cache-dir uv

WORKDIR /app

# Couche de dépendances (cache tant que pyproject/uv.lock ne changent pas).
# On inclut le groupe dev pour que `make test` / `make lint` tournent dans le conteneur.
COPY pyproject.toml uv.lock* ./
RUN uv sync

# Utilisateur non-privilégié (sécurité, §164).
RUN useradd --create-home --uid 10001 appuser
COPY . .
RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8000 8501
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
