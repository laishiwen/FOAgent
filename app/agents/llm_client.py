"""Shared LLM client for all 3 agents.

qwen3.5:9b on Ollama specifics:
- Always generates ~2k tokens of internal reasoning regardless of think:false
- response_format: json_object often yields empty content on this model
- Solution: large enough max_tokens (4096) + prompt-level JSON enforcement
"""

import json

import requests

from app.core import config
from app.core.logging import get_logger

logger = get_logger(__name__)


def call_llm(system_prompt: str, user_prompt: str) -> dict:
    """Call the configured model, return parsed JSON dict."""
    url = f"{config.BASE_URL}/chat/completions"

    body = {
        "model": config.MODEL_NAME,
        "temperature": config.TEMPERATURE,
        "max_tokens": config.MAX_TOKENS,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
        "think": False,
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config.API_KEY}",
    }

    try:
        resp = requests.post(url, json=body, headers=headers, timeout=600)
        resp.raise_for_status()
        result = resp.json()
    except requests.exceptions.RequestException as e:
        logger.error("LLM request failed: %s", e)
        raise RuntimeError(f"LLM connection error: {e}")

    if "choices" not in result or not result["choices"]:
        logger.error("LLM returned no choices: %s", json.dumps(result)[:500])
        raise RuntimeError("LLM returned no choices")

    content = result["choices"][0]["message"]["content"]
    reason_len = len(result["choices"][0]["message"].get("reasoning", ""))
    logger.info(
        "LLM response: content=%d chars, reasoning=%d chars, finish=%s",
        len(content), reason_len,
        result["choices"][0].get("finish_reason", "?"),
    )

    if not content or not content.strip():
        logger.error(
            "Empty response (all %d tokens consumed by reasoning). "
            "Try increasing MAX_TOKENS in config.",
            result.get("usage", {}).get("completion_tokens", 0),
        )
        raise RuntimeError("Model returned empty response — all tokens consumed by reasoning")

    # Parse JSON — handle markdown fences
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    if "```json" in content:
        return json.loads(content.split("```json")[1].split("```")[0])
    if "```" in content:
        return json.loads(content.split("```")[1].split("```")[0])

    raise RuntimeError(f"Could not parse LLM output as JSON: {content[:500]}")
