from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings


@lru_cache
def get_engine() -> AsyncEngine:
    return create_async_engine(get_settings().DATABASE_URL, pool_pre_ping=True)


@lru_cache
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    # expire_on_commit=False: los objetos ORM (p.ej. el id recien asignado al
    # document) siguen siendo legibles despues del commit.
    return async_sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    """Dependencia FastAPI: entrega una AsyncSession y la cierra al terminar."""
    async with get_session_factory()() as session:
        yield session
