"""OpenAI embeddings wrapper.

Handles text vectorization using OpenAI's embedding models.
Supports batched embedding generation for efficiency.
"""

from openai import AsyncOpenAI

from app.config import settings
from app.utils.logger import logger

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    """Get or create the OpenAI async client singleton.

    Returns:
        AsyncOpenAI client instance.
    """
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=settings.openai_api_key)
    return _client


async def generate_embedding(text: str) -> list[float]:
    """Generate an embedding vector for a single text.

    Args:
        text: The text to embed.

    Returns:
        List of floats representing the embedding vector.

    Raises:
        Exception: If the OpenAI API call fails.
    """
    client = _get_client()

    text = text.replace("\n", " ").strip()
    if not text:
        logger.warning("Empty text passed to generate_embedding")
        return []

    response = await client.embeddings.create(
        input=text,
        model=settings.embedding_model,
    )

    return response.data[0].embedding


async def generate_embeddings_batch(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for a batch of texts.

    OpenAI supports up to 2048 texts per batch request.
    This function handles chunking for larger batches.

    Args:
        texts: List of texts to embed.

    Returns:
        List of embedding vectors, one per input text.

    Raises:
        Exception: If the OpenAI API call fails.
    """
    client = _get_client()

    cleaned_texts = [t.replace("\n", " ").strip() for t in texts]
    cleaned_texts = [t if t else " " for t in cleaned_texts]

    all_embeddings: list[list[float]] = []
    batch_size = 2000

    for i in range(0, len(cleaned_texts), batch_size):
        batch = cleaned_texts[i : i + batch_size]

        logger.info("Generating embeddings for batch %d-%d of %d", i, i + len(batch), len(texts))

        response = await client.embeddings.create(
            input=batch,
            model=settings.embedding_model,
        )

        batch_embeddings = [item.embedding for item in response.data]
        all_embeddings.extend(batch_embeddings)

    return all_embeddings
