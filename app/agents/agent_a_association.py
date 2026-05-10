"""Agent A: 关联分析器 - Detects file associations."""

import json

from app.agents.llm_client import call_llm
from app.core.logging import get_logger

logger = get_logger(__name__)

SYSTEM_PROMPT = """找出有关联的文件归入groups，无关的放ungrouped_files。同名不同后缀>共同前缀>共同关键词>时间相近。只输出JSON：{"groups":[{"group_id":"1","members":["a.docx","a.xlsx"],"reason":"原因","confidence":0.9}],"ungrouped_files":[{"path":"b.txt","reason":"原因","confidence":0.7}]}"""


def run_agent_a(files: list, root_path: str) -> dict:
    """Run Agent A to detect file associations.

    Args:
        files: List of file info dicts from scan_parent_dir + get_file_info
        root_path: Root directory path

    Returns:
        Association results dict with groups and ungrouped_files
    """
    if not files:
        logger.info("Agent A: no files to analyze, returning empty result")
        return {"groups": [], "ungrouped_files": []}

    # Ultra-compact: filenames only, avoid structured metadata
    file_text = ", ".join(f["name"] for f in files)
    user_prompt = f"""分析文件: {file_text}。只输出JSON。"""

    logger.info("Agent A: analyzing associations for %d files", len(files))
    result = call_llm(SYSTEM_PROMPT, user_prompt)

    # Validate and normalize
    if "groups" not in result:
        result["groups"] = []
    if "ungrouped_files" not in result:
        result["ungrouped_files"] = []

    logger.info(
        "Agent A: found %d groups, %d ungrouped files",
        len(result["groups"]), len(result["ungrouped_files"]),
    )
    return result
