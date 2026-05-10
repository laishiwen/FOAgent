"""Agent A: 关联分析器 - ID-based, bucketed, with cross-bucket merge."""

from pydantic import BaseModel, Field

from agents.llm_client import call_llm
from core.logging import get_logger
from utils.bucket import split_files, format_bucket_prompt

logger = get_logger(__name__)


class GroupMember(BaseModel):
    group_id: str
    members: list[str]
    association_type: str = ""
    reason: str = ""
    confidence: float = 0.0
    needs_review: bool = False


class UngroupedFile(BaseModel):
    path: str
    reason: str = ""
    confidence: float = 0.0
    needs_review: bool = True


class AssociationOutput(BaseModel):
    groups: list[GroupMember] = Field(default_factory=list)
    ungrouped_files: list[UngroupedFile] = Field(default_factory=list)


SYSTEM_PROMPT = '你是文件关联分析器.根据文件名和扩展名识别文件关联关系.输出关联分组和无关联文件.'

MERGE_SYSTEM_PROMPT = '你是文件关联合并器.合并不同桶的关联组,统一为一个输出.'


def _normalize(result: AssociationOutput) -> dict:
    groups = [g.model_dump() for g in result.groups]
    ungrouped = [u.path for u in result.ungrouped_files]
    return {"groups": groups, "ungrouped": ungrouped}


def run_agent_a_single(files: list) -> dict:
    prompt = format_bucket_prompt(files)
    user_prompt = f"分析文件: {prompt}."
    logger.info("Agent A: single bucket with %d files", len(files))
    result = call_llm(AssociationOutput, SYSTEM_PROMPT, user_prompt)
    return _normalize(result)


def run_agent_a_bucketed(files: list) -> dict:
    buckets = split_files(files)
    logger.info("Agent A: %d files split into %d buckets", len(files), len(buckets))

    if len(buckets) == 1:
        return run_agent_a_single(buckets[0])

    all_groups = []
    all_ungrouped = []
    group_offset = 0

    for bi, bucket in enumerate(buckets):
        result = run_agent_a_single(bucket)
        for g in result.get("groups", []):
            group_offset += 1
            all_groups.append({**g, "group_id": f"g{group_offset}", "bucket": bi})
        all_ungrouped.extend(result.get("ungrouped", []))
        logger.info("Agent A: bucket %d -> %d groups, %d ungrouped",
                     bi, len(result.get("groups", [])), len(result.get("ungrouped", [])))

    if len(buckets) == 1 or len(all_groups) <= 1:
        return {"groups": all_groups, "ungrouped": all_ungrouped}

    # Cross-bucket merge
    logger.info("Agent A: cross-bucket merge for %d groups", len(all_groups))
    merge_parts = [f"{g['group_id']}:[{','.join(g['members'])}]" for g in all_groups]
    ungrouped_text = ", ".join(all_ungrouped) if all_ungrouped else "none"
    user_prompt = f"合并关联组: {'; '.join(merge_parts)}. 独立文件: {ungrouped_text}."

    merge_result = _normalize(call_llm(AssociationOutput, MERGE_SYSTEM_PROMPT, user_prompt))

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

    logger.info("Agent A: merge result -> %d groups, %d ungrouped",
                 len(all_groups), len(all_ungrouped))
    return {"groups": all_groups, "ungrouped": all_ungrouped}


def run_agent_a(files: list, root_path: str = "") -> dict:
    if not files:
        return {"groups": [], "ungrouped": []}
    file_count = len(files)
    if file_count <= 4:
        logger.info("Agent A: single mode for %d files", file_count)
        return run_agent_a_single(files)
    else:
        return run_agent_a_bucketed(files)
