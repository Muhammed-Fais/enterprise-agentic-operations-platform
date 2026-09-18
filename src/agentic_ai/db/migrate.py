import asyncio
from pathlib import Path

import psycopg

from agentic_ai.config import get_settings


def _database_url(url: str) -> str:
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


async def apply_migrations() -> None:
    workspace_migrations = Path.cwd() / "infra" / "migrations"
    source_migrations = Path(__file__).resolve().parents[3] / "infra" / "migrations"
    migration_dir = workspace_migrations if workspace_migrations.exists() else source_migrations
    migrations = sorted(migration_dir.glob("*.sql"))
    if not migrations:
        raise RuntimeError(f"no migrations found in {migration_dir}")

    async with await psycopg.AsyncConnection.connect(
        _database_url(get_settings().database_url)
    ) as connection:
        for migration in migrations:
            await connection.execute(migration.read_text(encoding="utf-8"))
        await connection.commit()


def main() -> None:
    asyncio.run(apply_migrations())


if __name__ == "__main__":
    main()
