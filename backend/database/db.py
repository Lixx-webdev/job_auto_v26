from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from backend.config import get_settings
from backend.database.models import Base

# ---------------------------------------------------------------------------
# Engine & session factory
# ---------------------------------------------------------------------------

def _build_async_url(db_url: str) -> str:
    """Convert a plain sqlite URL to the aiosqlite variant."""
    if db_url.startswith("sqlite:///") and "+aiosqlite" not in db_url:
        return db_url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
    return db_url


settings = get_settings()
_async_url = _build_async_url(settings.DB_URL)

engine = create_async_engine(
    _async_url,
    echo=settings.LOG_LEVEL == "DEBUG",
    future=True,
)

AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

async def init_db() -> None:
    """Create all tables (safe to call multiple times — uses CREATE IF NOT EXISTS)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Async context manager that yields a transactional session.

    Usage::

        async with get_session() as session:
            result = await session.execute(select(Job))
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
