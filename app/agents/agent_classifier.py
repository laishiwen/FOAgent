"""Unified file classifier agent — LangChain structured output.

All files go through LLM (bucketed). Pydantic models enforce JSON schema.
The agent dynamically determines categories based on file names/extensions.
"""

from typing import Callable

from pydantic import BaseModel, Field

from agents.llm_client import call_llm
from core import config
from core.logging import get_logger
from utils.bucket import split_files

logger = get_logger(__name__)

ProgressCallback = Callable[[str, int, int, str], None]


# ---- Pydantic output models ----

class ClassifyItem(BaseModel):
    file_id: str = Field(description="must be the exact file identifier from input, e.g. '0-1'")
    category: str = Field(description="category name in Chinese, 2-8 chars, semantic")


class ClassifyOutput(BaseModel):
    items: list[ClassifyItem] = Field(description="list of ALL files, each with their category")


class MergeOutput(BaseModel):
    mapping: dict[str, str] = Field(description="old category name -> unified name")


# ---- System prompts ----

# v2: semantic-first, no length cap, generic fallback
# v1: '分组名简洁(2-8字中文),不使用通用大类.'
CLASSIFY_SYSTEM = (
    '根据文件名和扩展名,将每个文件归类到语义化分组.'
    '优先使用具体语义命名(如CNN课程作业、财务数据),不确定时可用通用大类兜底(如文档、图片、代码).'
    'file_id必须原样使用输入中提供的标识符,不得修改.'
)

MERGE_SYSTEM = '合并语义相同的类别名为统一名称.'


# ---- Internal helpers ----

def _classify_bucket(bucket: list) -> dict:
    """Send one bucket to LLM, return {id: category}."""
    valid_ids = {f["id"] for f in bucket}
    names = ", ".join(f"{f['id']}:{f['name']}" for f in bucket)
    user_prompt = f"文件: {names} (每个文件使用上述标识符作为file_id)"
    result = call_llm(ClassifyOutput, CLASSIFY_SYSTEM, user_prompt)
    return {
        item.file_id: item.category.strip() or "其他"
        for item in result.items
        if item.file_id in valid_ids  # reject hallucinated IDs
    }


def _merge_categories(all_categories: set[str]) -> dict:
    """Use LLM to merge equivalent category names. Returns {old: unified}."""
    if len(all_categories) <= 1:
        return {}
    cat_list = ", ".join(sorted(all_categories))
    user_prompt = f"合并: {cat_list}"
    result = call_llm(MergeOutput, MERGE_SYSTEM, user_prompt)
    return result.mapping


# ---- Public API ----

def run_classifier(files: list, on_progress: ProgressCallback = None) -> dict:
    """Classify files into dynamically-discovered categories.

    Args:
        files: List of {id, name, extension} dicts
        on_progress: Optional callback(phase, current, total, message)

    Returns:
        {categories: [{category_name, member_ids, member_names, count}],
         category_order: [...], total_files: N}
    """

    def _progress(phase, current, total, msg):
        if on_progress:
            on_progress(phase, current, total, msg)

    if not files:
        _progress("done", 0, 0, "no files")
        return {"categories": [], "category_order": [], "total_files": 0}

    # Phase 1: Sort by extension then bucket (same-type files cluster together)
    files = sorted(files, key=lambda f: (f.get("extension", ""), f["name"].lower()))
    buckets = split_files(files, config.CLASSIFIER_CHAR_LIMIT,
                          config.CLASSIFIER_CHARS_PER_FILE)
    total_buckets = len(buckets)
    logger.info("Classifier: %d files -> %d buckets", len(files), total_buckets)
    _progress("classifying", 0, total_buckets,
              f"{len(files)} files, {total_buckets} buckets")

    all_classified: dict[str, str] = {}
    for bi, bucket in enumerate(buckets):
        bucket_result = _classify_bucket(bucket)
        all_classified.update(bucket_result)
        logger.info("Classifier: bucket %d -> %d classified", bi, len(bucket_result))
        _progress("classifying", bi + 1, total_buckets,
                  f"bucket {bi + 1}/{total_buckets} done, {len(bucket_result)} files")

    # Phase 2: Fill unclassified
    id_to_name = {f["id"]: f["name"] for f in files}
    for f in files:
        if f["id"] not in all_classified:
            all_classified[f["id"]] = "其他"

    # Phase 3: Merge synonyms (multi-bucket only)
    raw_categories = set(all_classified.values())
    if len(buckets) > 1 and len(raw_categories) > 1:
        _progress("merging", 0, 1, f"merging {len(raw_categories)} categories...")
        merge_map = _merge_categories(raw_categories)
        if merge_map:
            logger.info("Classifier: merge map %s", merge_map)
            for fid, cat in all_classified.items():
                if cat in merge_map:
                    all_classified[fid] = merge_map[cat]
        _progress("merging", 1, 1, "merge done")

    _progress("done", total_buckets, total_buckets, "classification complete")

    # Phase 4: Group by category
    cat_map: dict[str, list] = {}
    for fid, cat in all_classified.items():
        cat_map.setdefault(cat, []).append({
            "id": fid, "name": id_to_name.get(fid, "?"),
        })

    # Phase 5: Build ordered output (by count desc, "其他" last)
    categories = []
    for cat_name, members in sorted(cat_map.items(),
                                    key=lambda x: (-len(x[1]), x[0])):
        if cat_name == "其他":
            continue
        categories.append({
            "category_name": cat_name,
            "member_ids": [m["id"] for m in members],
            "member_names": [m["name"] for m in members],
            "count": len(members),
        })

    if "其他" in cat_map:
        m = cat_map["其他"]
        categories.append({
            "category_name": "其他",
            "member_ids": [x["id"] for x in m],
            "member_names": [x["name"] for x in m],
            "count": len(m),
        })

    logger.info("Classifier: %d categories for %d files",
                len(categories), len(files))
    return {
        "categories": categories,
        "category_order": [c["category_name"] for c in categories],
        "total_files": len(files),
    }
