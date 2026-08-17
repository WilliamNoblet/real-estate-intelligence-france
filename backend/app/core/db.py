"""Moteur SQLAlchemy et fabrique de sessions (synchrone, psycopg 3)."""
from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.core.config import settings

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,  # évite les connexions mortes après une coupure DB
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_session() -> Iterator[Session]:
    """Dépendance FastAPI : fournit une session et la referme proprement."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
