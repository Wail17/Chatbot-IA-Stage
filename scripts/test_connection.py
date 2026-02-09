"""Test API connections for Anthropic and OpenAI.

Run this script to verify that all API keys are correctly configured
and that the services are reachable.

Usage:
    python -m scripts.test_connection
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

from app.config import settings


async def test_anthropic() -> bool:
    """Test the Anthropic API connection.

    Returns:
        True if the connection is successful.
    """
    from anthropic import AsyncAnthropic

    print("Testing Anthropic API...")

    if not settings.anthropic_api_key:
        print("  FAIL: ANTHROPIC_API_KEY not set")
        return False

    try:
        client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        response = await client.messages.create(
            model=settings.claude_model_fast,
            max_tokens=50,
            messages=[{"role": "user", "content": "Say 'connection test OK' in 3 words."}],
        )
        print(f"  OK: {response.content[0].text}")
        return True
    except Exception as exc:
        print(f"  FAIL: {exc}")
        return False


async def test_openai() -> bool:
    """Test the OpenAI API connection.

    Returns:
        True if the connection is successful.
    """
    from openai import AsyncOpenAI

    print("Testing OpenAI API...")

    if not settings.openai_api_key:
        print("  FAIL: OPENAI_API_KEY not set")
        return False

    try:
        client = AsyncOpenAI(api_key=settings.openai_api_key)
        response = await client.embeddings.create(
            input="test connection",
            model=settings.embedding_model,
        )
        dim = len(response.data[0].embedding)
        print(f"  OK: Embedding dimension = {dim}")
        return True
    except Exception as exc:
        print(f"  FAIL: {exc}")
        return False


async def test_database() -> bool:
    """Test the PostgreSQL database connection.

    Returns:
        True if the connection is successful.
    """
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    print("Testing PostgreSQL connection...")

    if not settings.database_url:
        print("  FAIL: DATABASE_URL not set")
        return False

    try:
        url = settings.database_url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)

        engine = create_async_engine(url)
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            result.scalar()
        await engine.dispose()
        print("  OK: Database connection successful")
        return True
    except Exception as exc:
        print(f"  FAIL: {exc}")
        return False


async def main() -> None:
    """Run all connection tests."""
    print("=" * 50)
    print("Connection Tests for Chatbot IA")
    print("=" * 50)
    print(f"Environment: {settings.environment}")
    print()

    results = {
        "Anthropic": await test_anthropic(),
        "OpenAI": await test_openai(),
        "PostgreSQL": await test_database(),
    }

    print()
    print("=" * 50)
    print("Summary:")
    for service, ok in results.items():
        status = "PASS" if ok else "FAIL"
        print(f"  {service}: {status}")

    all_ok = all(results.values())
    print()
    if all_ok:
        print("All connections successful!")
    else:
        print("Some connections failed. Check your .env file.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
