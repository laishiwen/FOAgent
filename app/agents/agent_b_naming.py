"""Agent B: 分类命名器 - ID-based, with bucket support."""

from pydantic import BaseModel, Field

from agents.llm_client import call_llm
from core.logging import get_logger

logger = get_logger(__name__)


class CategoryEntry(BaseModel):
    category_name: str = Field(description="Chinese category name")
    group_id: str = ""
    member_ids: list[str] = Field(default_factory=list)
    reason: str = ""
    confidence: float = 0.5
    needs_review: bool = False


class NamingOutput(BaseModel):
    categories: list[CategoryEntry] = Field(default_factory=list)
    category_order: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


SYSTEM_PROMPT = '你是文件分类命名器.根据关联分组为每组生成中文分类名称(2-8字).'


def run_agent_b(associations: dict, files: list) -> dict:
    groups = associations.get("groups", [])
    ungrouped = associations.get("ungrouped", [])

    if not groups:
        logger.info("Agent B: no groups to classify")
        cats = []
        if ungrouped:
            cats.append({
                "category_name": "未分类", "group_id": "ungrouped",
                "member_ids": ungrouped, "reason": "无关联文件", "confidence": 0.5,
            })
        return {"categories": cats, "category_order": ["未分类"], "notes": []}

    id_to_name = {f["id"]: f["name"] for f in files}

    group_lines = []
    for g in groups:
        names = [f"{mid}:{id_to_name.get(mid, '?')}" for mid in g.get("members", [])]
        group_lines.append(f"{g['group_id']}:[{', '.join(names)}] (conf:{g.get('confidence',0):.0%})")

    group_text = "; ".join(group_lines)
    ungrouped_text = ", ".join(f"{uid}:{id_to_name.get(uid,'?')}" for uid in ungrouped) if ungrouped else "none"

    user_prompt = f"分组: {group_text}. 独立: {ungrouped_text}."

    if len(user_prompt) > 400:
        short_lines = [f"{g['group_id']}:{len(g.get('members',[]))} files" for g in groups]
        user_prompt = f"分组: {'; '.join(short_lines)}. 独立({len(ungrouped)})."

    logger.info("Agent B: %d groups + %d ungrouped", len(groups), len(ungrouped))
    result = call_llm(NamingOutput, SYSTEM_PROMPT, user_prompt)

    output = {
        "categories": [c.model_dump() for c in result.categories],
        "category_order": result.category_order or [c.category_name for c in result.categories],
        "notes": result.notes,
    }

    if ungrouped:
        covered_ids = set()
        for c in output["categories"]:
            covered_ids.update(c.get("member_ids", []))
        still_ungrouped = [uid for uid in ungrouped if uid not in covered_ids]
        if still_ungrouped:
            output["categories"].append({
                "category_name": "未分类", "group_id": "ungrouped",
                "member_ids": still_ungrouped,
                "reason": "无关联文件", "confidence": 0.5,
            })
            if "未分类" not in output["category_order"]:
                output["category_order"].append("未分类")

    logger.info("Agent B: %d categories", len(output["categories"]))
    return output
