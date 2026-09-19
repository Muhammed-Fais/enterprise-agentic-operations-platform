from collections.abc import AsyncIterator

from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from agentic_ai.auth import AuthContext, get_auth_context
from agentic_ai.config import get_settings


def _async_database_url(url: str) -> str:
    if url.startswith("postgresql+psycopg://"):
        return url.replace("postgresql+psycopg://", "postgresql+psycopg_async://", 1)
    return url


settings = get_settings()
engine = create_async_engine(_async_database_url(settings.database_url), pool_pre_ping=True)
session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def set_tenant_context(session: AsyncSession, tenant_id: str) -> None:
    await session.execute(
        text("SELECT set_config('app.tenant_id', :tenant_id, true)"),
        {"tenant_id": tenant_id},
    )


async def get_session(
    auth: AuthContext = Depends(get_auth_context),
) -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        await set_tenant_context(session, auth.tenant_id)
        yield session
