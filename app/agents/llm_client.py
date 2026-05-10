"""Shared LLM client — LangChain ChatOllama with structured output.

Replaces raw requests.post + manual JSON parsing with Pydantic models.
Uses tool calling under the hood for reliable structured output.
"""

from typing import Type, TypeVar

from langchain_ollama import ChatOllama
from pydantic import BaseModel

from core import config
from core.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)

_llm: ChatOllama | None = None


def _get_llm() -> ChatOllama:
    global _llm
    if _llm is None:
        base_url = config.BASE_URL.rstrip("/v1").rstrip("/")
        _llm = ChatOllama(
            model=config.MODEL_NAME,
            base_url=base_url,
            temperature=config.TEMPERATURE,
            num_predict=config.MAX_TOKENS if config.MAX_TOKENS > 0 else None,
        )
    return _llm


def call_llm(output_model: Type[T], system_prompt: str, user_prompt: str) -> T:
    """Call LLM with structured output parsed into a Pydantic model.

    Args:
        output_model: Pydantic model class for the expected output
        system_prompt: System message
        user_prompt: User message

    Returns:
        Instance of output_model, validated and parsed by Pydantic.

    Raises:
        RuntimeError: on repeated failures after retries.
    """
    llm = _get_llm()
    structured = llm.with_structured_output(output_model, method="function_calling")

    prompt = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    last_error = None
    for attempt in range(3):
        try:
            result = structured.invoke(prompt)
            if result is not None:
                logger.info("LLM: parsed %s (attempt %d)",
                            type(result).__name__, attempt + 1)
                return result
        except Exception as e:
            last_error = str(e)
            logger.warning("LLM attempt %d failed: %s", attempt + 1, last_error)

    raise RuntimeError(f"LLM failed after 3 attempts: {last_error}")
