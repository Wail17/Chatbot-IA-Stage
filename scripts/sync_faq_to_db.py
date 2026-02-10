"""
Sync existing FAQ from FAQAI.jsonl to PostgreSQL qa_knowledge_base.

Reads the JSONL file, checks for duplicates by exact question + language,
and inserts only new entries. Run this once to populate the knowledge base
with the initial 161 Q&A pairs so they appear in the admin dashboard.

Usage:
    python scripts/sync_faq_to_db.py
"""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.models.database import QAKnowledgeBase

FAQ_FILE = Path("data/faq/FAQAI.jsonl")


def get_async_database_url() -> str:
    """Convert the sync database URL to an async one for asyncpg.

    Returns:
        Async-compatible database URL string.
    """
    url = settings.database_url
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    return url


def load_faq_entries() -> list[dict[str, str]]:
    """Load FAQ entries from the JSONL file.

    Each line is a JSON object with keys: Vraag, Antwoord, Categorie.
    Lines that are empty or missing question/answer are skipped.

    Returns:
        List of parsed FAQ entry dictionaries.

    Raises:
        FileNotFoundError: If the FAQ file does not exist.
    """
    if not FAQ_FILE.exists():
        raise FileNotFoundError(f"FAQ file not found: {FAQ_FILE}")

    entries: list[dict[str, str]] = []
    skipped = 0

    with open(FAQ_FILE, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError as exc:
                print(f"  Warning: Invalid JSON at line {line_num}: {exc}")
                skipped += 1
                continue

            question = entry.get("Vraag", entry.get("vraag", "")).strip()
            answer = entry.get("Antwoord", entry.get("antwoord", "")).strip()

            if not question or not answer:
                print(f"  Warning: Missing question/answer at line {line_num}, skipping")
                skipped += 1
                continue

            entries.append(entry)

    if skipped > 0:
        print(f"  Skipped {skipped} invalid/incomplete lines from file")

    return entries


async def sync_faq_to_db() -> None:
    """Sync FAQ entries from JSONL file to PostgreSQL qa_knowledge_base.

    Reads FAQAI.jsonl, checks for existing entries by exact question + language,
    and inserts only new entries. Commits once at the end for efficiency.
    """
    print("=" * 60)
    print("FAQ Sync to PostgreSQL")
    print("=" * 60)

    # --- Load FAQ from file ---
    print(f"\nLoading FAQ from {FAQ_FILE}...")
    try:
        entries = load_faq_entries()
    except FileNotFoundError as exc:
        print(f"\nERROR: {exc}")
        return

    print(f"Loaded {len(entries)} entries from {FAQ_FILE}")

    if not entries:
        print("No entries to sync. Exiting.")
        return

    # --- Connect to database ---
    database_url = get_async_database_url()
    engine = create_async_engine(database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    added = 0
    skipped = 0

    try:
        async with async_session() as session:
            # --- Fetch all existing questions for fast duplicate check ---
            result = await session.execute(
                select(QAKnowledgeBase.question, QAKnowledgeBase.language)
            )
            existing_pairs: set[tuple[str, str]] = {
                (row[0], row[1]) for row in result.all()
            }
            print(f"Found {len(existing_pairs)} existing Q&A entries in database")

            # --- Process each entry ---
            print("Processing entries...")
            for entry in entries:
                question = entry.get("Vraag", entry.get("vraag", "")).strip()
                answer = entry.get("Antwoord", entry.get("antwoord", "")).strip()
                category = entry.get("Categorie", entry.get("categorie", "General")).strip()
                language = "nl"

                if (question, language) in existing_pairs:
                    skipped += 1
                    continue

                new_qa = QAKnowledgeBase(
                    question=question,
                    answer=answer,
                    category=category,
                    language=language,
                    source="initial_import",
                    is_active=True,
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                )
                session.add(new_qa)
                existing_pairs.add((question, language))
                added += 1

            # --- Commit all at once ---
            await session.commit()

            # --- Get final count ---
            count_result = await session.execute(
                select(func.count(QAKnowledgeBase.id))
            )
            total_in_db = count_result.scalar()

    except Exception as exc:
        print(f"\nERROR during database operation: {exc}")
        raise
    finally:
        await engine.dispose()

    # --- Display stats ---
    print(f"  Added: {added}")
    print(f"  Skipped: {skipped} (already exist)")
    print(f"\n{'=' * 60}")
    print(f"Sync complete!")
    print(f"Total Q&A in database: {total_in_db}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(sync_faq_to_db())
