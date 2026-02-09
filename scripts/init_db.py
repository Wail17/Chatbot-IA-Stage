"""Initialize PostgreSQL database tables.

Creates all tables defined in the ORM models. Safe to run multiple
times — existing tables are not dropped.

Usage:
    python -m scripts.init_db
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

from sqlalchemy.ext.asyncio import create_async_engine

from app.config import settings
from app.models.database import Base


async def init_database() -> None:
    """Create all database tables from ORM models."""
    url = settings.database_url
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)

    print(f"Connecting to database...")
    engine = create_async_engine(url, echo=True)

    async with engine.begin() as conn:
        print("Creating tables...")
        await conn.run_sync(Base.metadata.create_all)

    await engine.dispose()
    print("Database initialization complete!")
    print()
    print("Tables created:")
    for table_name in Base.metadata.tables:
        print(f"  - {table_name}")


if __name__ == "__main__":
    asyncio.run(init_database())
