"""Agent B: 分类命名器 - Generates category names from association groups."""

import json
import os

from app.agents.llm_client import call_llm
from app.core.logging import get_logger

logger = get_logger(__name__)

SYSTEM_PROMPT = """为文件组起中文名。主题>类型>泛称。只输出JSON：{"categories":[{"category_name":"名称","group_id":"g1","members":["a.docx"],"reason":"原因","confidence":0.9}],"category_order":["名称"],"notes":[]}"""


def run_agent_b(associations: dict, files: list) -> dict:
    """Run Agent B to generate category names and final classification.

    Args:
        associations: Agent A output dict with groups and ungrouped_files
        files: Original file info list for reference

    Returns:
        Classification plan dict with categories and category_order
    """
    groups = associations.get("groups", [])
    ungrouped = associations.get("ungrouped_files", [])

    if not groups and not ungrouped:
        logger.info("Agent B: nothing to classify, returning empty result")
        return {"categories": [], "category_order": [], "notes": []}

    # Ultra-compact text summary
    group_text = "; ".join(
        f"{g['group_id']}:[{', '.join(os.path.basename(m) for m in g.get('members',[]))}]"
        for g in groups
    )
    ungrouped_text = ", ".join(os.path.basename(u['path']) for u in ungrouped)

    user_prompt = f"""分组: {group_text}。独立: {ungrouped_text}。只输出JSON。"""

    logger.info(
        "Agent B: generating categories for %d groups + %d ungrouped",
        len(groups), len(ungrouped),
    )
    result = call_llm(SYSTEM_PROMPT, user_prompt)

    if "categories" not in result:
        result["categories"] = []
    if "category_order" not in result:
        result["category_order"] = [c["category_name"] for c in result["categories"]]
    if "notes" not in result:
        result["notes"] = []

    logger.info("Agent B: generated %d categories", len(result["categories"]))
    return result
