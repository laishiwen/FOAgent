"""Agent A: 关联分析器 - ID-based, bucketed, with cross-bucket merge."""

from agents.llm_client import call_llm
from core.logging import get_logger
from utils.bucket import split_files, format_bucket_prompt

logger = get_logger(__name__)

SYSTEM_PROMPT = """你是文件关联分析器。只输出JSON，不要输出任何其他文本。输出格式：{"groups":[{"group_id":"1","members":["1","2"]}],"ungrouped_files":[{"path":"3"}]}"""

MERGE_SYSTEM_PROMPT = """你是文件关联合并器。只输出JSON，不要输出任何其他文本。输出格式：{"groups":[{"group_id":"mg1","members":["1","2"]}],"ungrouped_files":[{"path":"3"}]}"""


def _normalize(result: dict) -> dict:
    """Normalize model output to internal format: {groups: [...], ungrouped: [id,...]}"""
    groups = result.get("groups", [])
    ungrouped = []
    for item in result.get("ungrouped_files", result.get("ungrouped", [])):
        if isinstance(item, dict):
            ungrouped.append(item.get("path", item.get("id", str(item))))
        else:
            ungrouped.append(str(item))
    return {"groups": groups, "ungrouped": ungrouped}


def run_agent_a_single(files: list) -> dict:
    """Single-bucket association detection."""
    prompt = format_bucket_prompt(files)
    user_prompt = f"""分析文件: {prompt}。输出分组JSON。只输出JSON。"""
    logger.info("Agent A: single bucket with %d files", len(files))
    result = call_llm(SYSTEM_PROMPT, user_prompt)
    return _normalize(result)


def run_agent_a_bucketed(files: list) -> dict:
    """Multi-bucket: split, analyze each, then cross-bucket merge."""
    buckets = split_files(files)
    logger.info("Agent A: %d files split into %d buckets", len(files), len(buckets))

    if len(buckets) == 1:
        return run_agent_a_single(buckets[0])

    # Phase 1: per-bucket analysis
    all_groups = []
    all_ungrouped = []
    group_offset = 0

    for bi, bucket in enumerate(buckets):
        result = run_agent_a_single(bucket)
        for g in result.get("groups", []):
            group_offset += 1
            all_groups.append({**g, "group_id": f"g{group_offset}", "bucket": bi})
        all_ungrouped.extend(result.get("ungrouped", []))
        logger.info("Agent A: bucket %d → %d groups, %d ungrouped",
                     bi, len(result.get("groups", [])), len(result.get("ungrouped", [])))

    if len(buckets) == 1 or len(all_groups) <= 1:
        return {"groups": all_groups, "ungrouped": all_ungrouped}

    # Phase 2: cross-bucket merge
    logger.info("Agent A: cross-bucket merge for %d groups", len(all_groups))
    merge_prompt_parts = []
    for g in all_groups:
        merge_prompt_parts.append(
            f"{g['group_id']}:[{','.join(g['members'])}]"
        )
    merge_text = "; ".join(merge_prompt_parts)
    ungrouped_text = ", ".join(all_ungrouped) if all_ungrouped else "无"

    merge_user_prompt = f"""合并关联组: {merge_text}。独立文件: {ungrouped_text}。只输出JSON。"""
    merge_result = _normalize(call_llm(MERGE_SYSTEM_PROMPT, merge_user_prompt))

    if merge_result.get("groups"):
        merged_groups = []
        merged_ids = set()
        for g in merge_result["groups"]:
            merged_groups.append(g)
            merged_ids.update(g.get("members", []))
        for g in all_groups:
            if not any(m in merged_ids for m in g.get("members", [])):
                merged_groups.append(g)
        all_groups = merged_groups

    if merge_result.get("ungrouped"):
        all_ungrouped = merge_result["ungrouped"]

    logger.info("Agent A: merge result → %d groups, %d ungrouped",
                 len(all_groups), len(all_ungrouped))
    return {"groups": all_groups, "ungrouped": all_ungrouped}


def run_agent_a(files: list, root_path: str) -> dict:
    """Entry point. Auto-selects single or bucketed mode."""
    if not files:
        return {"groups": [], "ungrouped": []}

    file_count = len(files)
    if file_count <= 4:
        logger.info("Agent A: single mode for %d files", file_count)
        return run_agent_a_single(files)
    else:
        return run_agent_a_bucketed(files)
