"""Harness Agent: 终检器 - Independent semantic review after execution."""

import json
import os

from app.agents.llm_client import call_llm
from app.core.logging import get_logger

logger = get_logger(__name__)

SYSTEM_PROMPT = """复查分类结果。查完整性、关联、命名、一致性。verdict: pass/warn/fail。只输出JSON：{"verdict":"pass","overall_assessment":"评估","checks":{"completeness":{"passed":true,"total_files":0,"classified_files":0,"unclassified_files":0,"detail":""},"association_spot_check":{"passed":true,"samples_checked":0,"issues_found":0,"detail":""},"naming_spot_check":{"passed":true,"samples_checked":0,"issues_found":0,"detail":""},"execution_consistency":{"passed":true,"planned_moves":0,"actual_moves":0,"mismatches":0,"detail":""}},"issues":[],"suggestions":[]}"""


def run_harness_agent(
    files: list,
    associations: dict,
    plan: dict,
    execution_log: dict,
) -> dict:
    """Run Harness Agent to independently review the completed classification.

    Args:
        files: Original file list from scan
        associations: Agent A output
        plan: Agent B output + generated move plan
        execution_log: Execution log from bash tools
    """
    if not files:
        logger.info("Harness: no files to check, returning pass")
        return {
            "verdict": "pass",
            "overall_assessment": "无文件需要检查",
            "checks": {
                "completeness": {
                    "passed": True, "total_files": 0, "classified_files": 0,
                    "unclassified_files": 0, "detail": "无文件"
                },
                "association_spot_check": {
                    "passed": True, "samples_checked": 0,
                    "issues_found": 0, "detail": "无关联组可查"
                },
                "naming_spot_check": {
                    "passed": True, "samples_checked": 0,
                    "issues_found": 0, "detail": "无分类可查"
                },
                "execution_consistency": {
                    "passed": True, "planned_moves": 0,
                    "actual_moves": 0, "mismatches": 0, "detail": "无移动操作"
                },
            },
            "issues": [],
            "suggestions": [],
        }

    # Build a compact summary for the LLM
    file_names = [f["name"] for f in files]
    total_files = len(files)

    groups_summary = []
    for g in associations.get("groups", []):
        groups_summary.append({
            "group_id": g["group_id"],
            "member_count": len(g.get("members", [])),
            "sample_members": [os.path.basename(m) for m in g.get("members", [])[:3]],
            "confidence": g.get("confidence", 0),
        })

    categories_summary = []
    for c in plan.get("categories", []):
        categories_summary.append({
            "name": c.get("category_name", "unknown"),
            "member_count": len(c.get("members", [])),
            "confidence": c.get("confidence", 0),
        })

    moves_summary = {
        "planned": len(plan.get("moves", [])),
        "executed": len([
            s for s in execution_log.get("steps", [])
            if s.get("step_type") == "move_file" and s.get("status") == "completed"
        ]),
    }

    # Compact text — avoids JSON bloat that triggers excessive reasoning
    file_list = ", ".join(file_names[:20])
    group_list = "; ".join(
        f"{g['group_id']}({g['member_count']}文件,{g['confidence']:.0%})"
        for g in groups_summary
    )
    cat_list = "; ".join(
        f"{c['name']}({c['member_count']}文件)"
        for c in categories_summary
    )

    user_prompt = f"""复查: 文件({total_files}): {file_list} | 关联组: {group_list} | 分类: {cat_list} | 移动: {moves_summary['planned']}计划/{moves_summary['executed']}实际。只输出JSON。"""

    logger.info("Harness: running final review for %d files", total_files)
    result = call_llm(SYSTEM_PROMPT, user_prompt)

    if "verdict" not in result:
        result["verdict"] = "warn"
    if "checks" not in result:
        result["checks"] = {}
    if "issues" not in result:
        result["issues"] = []
    if "suggestions" not in result:
        result["suggestions"] = []

    logger.info("Harness: verdict = %s", result["verdict"])
    return result


