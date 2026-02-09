"""Claude API wrapper with Haiku/Sonnet hybrid strategy.

Uses Claude Haiku for fast, high-confidence responses and
Claude Sonnet for complex questions requiring deeper reasoning.
"""

from anthropic import AsyncAnthropic

from app.config import settings
from app.utils.logger import logger

_client: AsyncAnthropic | None = None

SYSTEM_PROMPT_TEMPLATE = """You are a helpful customer service assistant for zwembad.eu,
a swimming pool company. You help customers with questions about swimming pools,
maintenance, products, pricing, and services.

Language: Respond in {language}.
Tone: Professional, friendly, and knowledgeable.

Important rules:
- Only answer questions related to swimming pools and zwembad.eu services.
- If you don't know the answer, say so honestly and suggest contacting the team.
- Never make up prices or specific product details unless provided in the context.
- Keep answers concise but complete.

{context_section}"""


def _get_client() -> AsyncAnthropic:
    """Get or create the Anthropic async client singleton.

    Returns:
        AsyncAnthropic client instance.
    """
    global _client
    if _client is None:
        _client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    return _client


def _build_system_prompt(language: str, context: str | None = None) -> str:
    """Build the system prompt with language and optional context.

    Args:
        language: Response language code.
        context: Optional knowledge base context to include.

    Returns:
        Formatted system prompt string.
    """
    language_names = {
        "nl": "Dutch (Nederlands)",
        "fr": "French (Français)",
        "en": "English",
        "da": "Danish (Dansk)",
    }

    lang_name = language_names.get(language, "Dutch (Nederlands)")

    context_section = ""
    if context:
        context_section = f"""
Use the following knowledge base context to answer the question.
If the context is relevant, base your answer on it.
If the context doesn't cover the question, use your general knowledge about swimming pools.

Context:
{context}"""

    return SYSTEM_PROMPT_TEMPLATE.format(
        language=lang_name,
        context_section=context_section,
    )


async def generate_answer_fast(
    question: str,
    language: str,
    context: str | None = None,
) -> dict:
    """Generate a fast answer using Claude Haiku.

    Used for high-confidence questions where the knowledge base
    provides a clear match.

    Args:
        question: The user's question.
        language: Response language code.
        context: Optional knowledge base context.

    Returns:
        Dictionary with 'answer' and 'model' keys.
    """
    client = _get_client()
    system_prompt = _build_system_prompt(language, context)

    logger.info("Generating fast answer with %s", settings.claude_model_fast)

    response = await client.messages.create(
        model=settings.claude_model_fast,
        max_tokens=settings.max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": question}],
    )

    answer = response.content[0].text
    return {"answer": answer, "model": settings.claude_model_fast}


async def generate_answer_smart(
    question: str,
    language: str,
    context: str | None = None,
) -> dict:
    """Generate a thorough answer using Claude Sonnet.

    Used for complex or low-confidence questions requiring
    deeper reasoning and more nuanced responses.

    Args:
        question: The user's question.
        language: Response language code.
        context: Optional knowledge base context.

    Returns:
        Dictionary with 'answer' and 'model' keys.
    """
    client = _get_client()
    system_prompt = _build_system_prompt(language, context)

    logger.info("Generating smart answer with %s", settings.claude_model_smart)

    response = await client.messages.create(
        model=settings.claude_model_smart,
        max_tokens=settings.max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": question}],
    )

    answer = response.content[0].text
    return {"answer": answer, "model": settings.claude_model_smart}
