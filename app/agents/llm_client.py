"""Shared LLM client for all 3 agents.

qwen3.5:9b on Ollama specifics:
- Always generates ~2k tokens of internal reasoning regardless of think:false
- response_format: json_object often yields empty content on this model
- Solution: large enough max_tokens (4096) + prompt-level JSON enforcement
"""

import json

import requests

from core import config
from core.logging import get_logger

logger = get_logger(__name__)


def _do_call(system_prompt: str, user_prompt: str) -> str:
    """Single LLM call, returns raw content string."""
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
    resp = requests.post(url, json=body, headers=headers, timeout=600)
    resp.raise_for_status()
    result = resp.json()
    if "choices" not in result or not result["choices"]:
        raise RuntimeError("LLM returned no choices")
    content = result["choices"][0]["message"]["content"]
    reason_len = len(result["choices"][0]["message"].get("reasoning", ""))
    finish = result["choices"][0].get("finish_reason", "?")
    logger.info("LLM: content=%d chars, reasoning=%d chars, finish=%s",
                 len(content), reason_len, finish)
    return content


def call_llm(system_prompt: str, user_prompt: str) -> dict:
    """Call LLM with retry on empty response (qwen3.5:9b non-determinism)."""
    last_error = None
    for attempt in range(3):
        try:
            content = _do_call(system_prompt, user_prompt)
        except requests.exceptions.RequestException as e:
            logger.error("LLM request failed: %s", e)
            raise RuntimeError(f"LLM connection error: {e}")

        if content and content.strip():
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                pass
            if "```json" in content:
                return json.loads(content.split("```json")[1].split("```")[0])
            if "```" in content:
                return json.loads(content.split("```")[1].split("```")[0])
            last_error = f"Could not parse JSON: {content[:200]}"
            logger.warning("Attempt %d: %s", attempt + 1, last_error)
        else:
            logger.warning("Attempt %d: empty response, retrying...", attempt + 1)
            last_error = "empty response"

    raise RuntimeError(f"LLM failed after 3 attempts: {last_error}")
