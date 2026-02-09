"""ChromaDB vector store operations.

Manages the vector database for semantic search, including
document storage, retrieval, and knowledge base management.
"""

import chromadb
from chromadb.config import Settings as ChromaSettings
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.config import settings
from app.models.database import Base, QAKnowledgeBase, WeeklyPerformance
from app.models.schemas import KnowledgeBaseEntry, PerformanceStats
from app.utils.logger import logger

CHROMA_COLLECTION_NAME = "zwembad_faq"

_chroma_client: chromadb.ClientAPI | None = None
_async_engine = None
_async_session_factory = None


def get_chroma_client() -> chromadb.ClientAPI:
    """Get or create the ChromaDB persistent client.

    Returns:
        ChromaDB client instance.
    """
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = chromadb.Client(ChromaSettings(
            chroma_db_impl="duckdb+parquet",
            persist_directory="data/chroma_db",
            anonymized_telemetry=False,
        ))
        logger.info("ChromaDB client initialized at data/chroma_db")
    return _chroma_client


def get_collection() -> chromadb.Collection:
    """Get the FAQ collection from ChromaDB.

    Returns:
        The ChromaDB collection for FAQ embeddings.
    """
    client = get_chroma_client()
    return client.get_or_create_collection(
        name=CHROMA_COLLECTION_NAME,
        metadata={"description": "Zwembad.eu FAQ knowledge base"},
    )


def _get_async_database_url() -> str:
    """Convert sync database URL to async format.

    Returns:
        Async-compatible database URL.
    """
    url = settings.database_url
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


async def get_async_session() -> AsyncSession:
    """Create an async database session.

    Returns:
        AsyncSession instance.
    """
    global _async_engine, _async_session_factory

    if _async_engine is None:
        _async_engine = create_async_engine(_get_async_database_url(), echo=False)
        _async_session_factory = async_sessionmaker(_async_engine, expire_on_commit=False)

    return _async_session_factory()


async def add_to_vectorstore(
    doc_id: str,
    text: str,
    embedding: list[float],
    metadata: dict,
) -> None:
    """Add a document with its embedding to ChromaDB.

    Args:
        doc_id: Unique document identifier.
        text: The document text content.
        embedding: Pre-computed embedding vector.
        metadata: Additional metadata (category, language, etc.).
    """
    collection = get_collection()
    collection.upsert(
        ids=[doc_id],
        documents=[text],
        embeddings=[embedding],
        metadatas=[metadata],
    )
    logger.debug("Added/updated document %s in ChromaDB", doc_id)


async def search_similar(
    query_embedding: list[float],
    n_results: int = 5,
    language_filter: str | None = None,
) -> list[dict]:
    """Search ChromaDB for similar documents.

    Args:
        query_embedding: The query embedding vector.
        n_results: Maximum number of results to return.
        language_filter: Optional language filter.

    Returns:
        List of result dictionaries with id, document, metadata, and distance.
    """
    collection = get_collection()

    where_filter = None
    if language_filter:
        where_filter = {"language": language_filter}

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
        where=where_filter,
        include=["documents", "metadatas", "distances"],
    )

    formatted_results = []
    if results and results["ids"] and results["ids"][0]:
        for i, doc_id in enumerate(results["ids"][0]):
            formatted_results.append({
                "id": doc_id,
                "document": results["documents"][0][i] if results["documents"] else "",
                "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                "distance": results["distances"][0][i] if results["distances"] else 1.0,
            })

    return formatted_results


async def get_knowledge_base_entries(
    category: str | None = None,
    language: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[KnowledgeBaseEntry]:
    """Retrieve knowledge base entries from PostgreSQL.

    Args:
        category: Optional category filter.
        language: Optional language filter.
        limit: Maximum results.
        offset: Pagination offset.

    Returns:
        List of KnowledgeBaseEntry schema objects.
    """
    async with await get_async_session() as session:
        query = select(QAKnowledgeBase).where(QAKnowledgeBase.is_active.is_(True))

        if category:
            query = query.where(QAKnowledgeBase.category == category)
        if language:
            query = query.where(QAKnowledgeBase.language == language)

        query = query.order_by(desc(QAKnowledgeBase.created_at)).offset(offset).limit(limit)
        result = await session.execute(query)
        entries = result.scalars().all()

        return [KnowledgeBaseEntry.model_validate(entry) for entry in entries]


async def get_performance_stats(weeks: int = 4) -> list[PerformanceStats]:
    """Retrieve weekly performance statistics from PostgreSQL.

    Args:
        weeks: Number of recent weeks to retrieve.

    Returns:
        List of PerformanceStats schema objects.
    """
    async with await get_async_session() as session:
        query = (
            select(WeeklyPerformance)
            .order_by(desc(WeeklyPerformance.week_start))
            .limit(weeks)
        )
        result = await session.execute(query)
        stats = result.scalars().all()

        return [PerformanceStats.model_validate(s) for s in stats]
