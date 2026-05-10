"""Harness Agent: 终检器 - ID-based compact review."""

from agents.llm_client import call_llm
from core.logging import get_logger

logger = get_logger(__name__)

SYSTEM_PROMPT = """你是文件分类终检器。只输出JSON，不要输出任何其他文本。输出格式：{"verdict":"pass","overall_assessment":"评估","checks":{"completeness":{"passed":true,"total_files":0,"classified_files":0,"unclassified_files":0,"detail":""},"association_spot_check":{"passed":true,"samples_checked":0,"issues_found":0,"detail":""},"naming_spot_check":{"passed":true,"samples_checked":0,"issues_found":0,"detail":""},"execution_consistency":{"passed":true,"planned_moves":0,"actual_moves":0,"mismatches":0,"detail":""}},"issues":[],"suggestions":[]}"""


def run_harness_agent(files: list, associations: dict, plan: dict,
                      execution_log: dict) -> dict:
    if not files:
        return {
            "verdict": "pass", "overall_assessment": "无文件",
            "checks": {
                "completeness": {"passed": True, "total_files": 0, "classified_files": 0, "unclassified_files": 0, "detail": "无文件"},
                "association_spot_check": {"passed": True, "samples_checked": 0, "issues_found": 0, "detail": "无"},
                "naming_spot_check": {"passed": True, "samples_checked": 0, "issues_found": 0, "detail": "无"},
                "execution_consistency": {"passed": True, "planned_moves": 0, "actual_moves": 0, "mismatches": 0, "detail": "无"},
            },
            "issues": [], "suggestions": [],
        }

    id_to_name = {f["id"]: f["name"] for f in files}
    total = len(files)

    # Compact summaries using IDs
    group_summary = "; ".join(
        f"{g['group_id']}({len(g.get('members',[]))}f,{g.get('confidence',0):.0%})"
        for g in associations.get("groups", [])
    )
    cat_summary = "; ".join(
        f"{c.get('category_name','?')}({len(c.get('member_ids',c.get('members',[])))}f)"
        for c in plan.get("categories", [])
    )
    planned = len(plan.get("moves", []))
    executed = len([s for s in execution_log.get("steps", [])
                    if s.get("status") == "completed"])

    # List unclassified files
    classified_ids = set()
    for c in plan.get("categories", []):
        classified_ids.update(c.get("member_ids", c.get("members", [])))
    unclassified = [f"{fid}:{id_to_name[fid]}" for fid in id_to_name if fid not in classified_ids]

    user_prompt = (f"""复查: 文件{total}个 | 组: {group_summary} | 分类: {cat_summary}"""
                   f""" | 移动: {planned}计划/{executed}实际"""
                   + (f" | 未分类: {', '.join(unclassified[:10])}" if unclassified else "")
                   + """。只输出JSON。""")

    # Truncate if too long
    if len(user_prompt) > 400:
        user_prompt = f"""复查: 文件{total}个 | {len(associations.get('groups',[]))}组 | {len(plan.get('categories',[]))}分类 | 移动{planned}计划/{executed}实际。只输出JSON。"""

    logger.info("Harness: reviewing %d files", total)
    result = call_llm(SYSTEM_PROMPT, user_prompt)
    result.setdefault("verdict", "warn")
    result.setdefault("checks", {})
    result.setdefault("issues", [])
    result.setdefault("suggestions", [])
    return result
