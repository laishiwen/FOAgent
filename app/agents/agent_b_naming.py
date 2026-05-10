"""Agent B: 分类命名器 - ID-based, with bucket support."""

from agents.llm_client import call_llm
from core.logging import get_logger

logger = get_logger(__name__)

SYSTEM_PROMPT = """你是文件分类命名器。只输出JSON，不要输出任何其他文本。输出格式：{"categories":[{"category_name":"名称","group_id":"g1","member_ids":["1","2"]}],"category_order":["名称"],"notes":[]}"""


def run_agent_b(associations: dict, files: list) -> dict:
    """Generate category names for each association group.

    Args:
        associations: {groups: [{group_id, members: [id,...], reason, confidence}],
                       ungrouped: [id,...]}
        files: List of enriched file dicts with 'id' keys

    Returns:
        {categories: [{category_name, group_id, member_ids, reason, confidence}],
         category_order: [...], notes: [...]}
    """
    groups = associations.get("groups", [])
    ungrouped = associations.get("ungrouped", [])

    if not groups:
        logger.info("Agent B: no groups to classify")
        cats = []
        if ungrouped:
            cats.append({
                "category_name": "未分类",
                "group_id": "ungrouped",
                "member_ids": ungrouped,
                "reason": "无关联文件",
                "confidence": 0.5,
            })
        return {"categories": cats, "category_order": ["未分类"], "notes": []}

    # Build ID→name lookup
    id_to_name = {f["id"]: f["name"] for f in files}

    # Compact group summary
    group_lines = []
    for g in groups:
        names = [f"{mid}:{id_to_name.get(mid, '?')}" for mid in g.get("members", [])]
        group_lines.append(f"{g['group_id']}:[{', '.join(names)}] (置信度:{g.get('confidence',0):.0%})")

    group_text = "; ".join(group_lines)
    ungrouped_text = ", ".join(f"{uid}:{id_to_name.get(uid,'?')}" for uid in ungrouped) if ungrouped else "无"

    user_prompt = f"""分组: {group_text}。独立: {ungrouped_text}。输出分类JSON。只输出JSON。"""

    # If prompt is too long, truncate group details
    if len(user_prompt) > 400:
        short_lines = []
        for g in groups:
            short_lines.append(f"{g['group_id']}:{len(g.get('members',[]))}个文件")
        group_text = "; ".join(short_lines)
        user_prompt = f"""分组: {group_text}。独立({len(ungrouped)}个)。只输出JSON。"""

    logger.info("Agent B: %d groups + %d ungrouped", len(groups), len(ungrouped))
    result = call_llm(SYSTEM_PROMPT, user_prompt)

    result.setdefault("categories", [])
    result.setdefault("category_order", [c["category_name"] for c in result["categories"]])
    result.setdefault("notes", [])

    # Add ungrouped as "未分类" if not already covered
    if ungrouped:
        covered_ids = set()
        for c in result["categories"]:
            covered_ids.update(c.get("member_ids", []))
        still_ungrouped = [uid for uid in ungrouped if uid not in covered_ids]
        if still_ungrouped:
            result["categories"].append({
                "category_name": "未分类",
                "group_id": "ungrouped",
                "member_ids": still_ungrouped,
                "reason": "无关联文件",
                "confidence": 0.5,
            })
            if "未分类" not in result["category_order"]:
                result["category_order"].append("未分类")

    logger.info("Agent B: %d categories", len(result["categories"]))
    return result
