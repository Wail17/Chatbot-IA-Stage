"""Vectorize FAQAI.jsonl into ChromaDB.

Reads the FAQ data from data/faq/FAQAI.jsonl, generates embeddings
via OpenAI, and stores them in ChromaDB for semantic search.

Usage:
    python -m scripts.vectorize_faq
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

from app.services.embeddings import generate_embeddings_batch
from app.services.vectorstore import add_to_vectorstore, get_collection
from app.utils.helpers import generate_chromadb_id

FAQ_FILE = Path("data/faq/FAQAI.jsonl")


def load_faq_entries() -> list[dict]:
    """Load FAQ entries from the JSONL file.

    Returns:
        List of FAQ entry dictionaries.

    Raises:
        FileNotFoundError: If the FAQ file does not exist.
    """
    if not FAQ_FILE.exists():
        raise FileNotFoundError(f"FAQ file not found: {FAQ_FILE}")

    entries = []
    with open(FAQ_FILE, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                entries.append(entry)
            except json.JSONDecodeError as exc:
                print(f"  Warning: Skipping invalid JSON at line {line_num}: {exc}")

    return entries


async def vectorize_faq() -> None:
    """Main vectorization pipeline."""
    print("=" * 50)
    print("FAQ Vectorization Pipeline")
    print("=" * 50)

    print(f"\nLoading FAQ from {FAQ_FILE}...")
    entries = load_faq_entries()
    print(f"Loaded {len(entries)} FAQ entries")

    if not entries:
        print("No entries to vectorize. Exiting.")
        return

    print(f"\nSample entry keys: {list(entries[0].keys())}")

    texts_to_embed = []
    metadata_list = []
    doc_ids = []

    for entry in entries:
        category = entry.get("Categorie", entry.get("categorie", "General"))
        question = entry.get("Vraag", entry.get("vraag", ""))
        answer = entry.get("Antwoord", entry.get("antwoord", ""))

        if not question or not answer:
            continue

        embedding_text = f"{question} {answer}"
        texts_to_embed.append(embedding_text)

        doc_id = generate_chromadb_id(category, question)
        doc_ids.append(doc_id)

        metadata_list.append({
            "category": category,
            "question": question,
            "language": entry.get("Taal", entry.get("taal", "nl")),
            "source": "faq_import",
        })

    print(f"\nGenerating embeddings for {len(texts_to_embed)} entries...")
    embeddings = await generate_embeddings_batch(texts_to_embed)
    print(f"Generated {len(embeddings)} embeddings")

    print("\nStoring in ChromaDB...")
    collection = get_collection()

    batch_size = 100
    for i in range(0, len(doc_ids), batch_size):
        batch_end = min(i + batch_size, len(doc_ids))
        batch_ids = doc_ids[i:batch_end]
        batch_embeddings = embeddings[i:batch_end]
        batch_documents = [
            entries[j].get("Antwoord", entries[j].get("antwoord", ""))
            for j in range(i, batch_end)
        ]
        batch_metadatas = metadata_list[i:batch_end]

        collection.upsert(
            ids=batch_ids,
            embeddings=batch_embeddings,
            documents=batch_documents,
            metadatas=batch_metadatas,
        )
        print(f"  Stored batch {i}-{batch_end}")

    print(f"\nVectorization complete!")
    print(f"Total documents in collection: {collection.count()}")


if __name__ == "__main__":
    asyncio.run(vectorize_faq())
