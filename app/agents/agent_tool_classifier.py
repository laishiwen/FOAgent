"""Tool-based classifier — one tool call per file.

Uses LangChain tool binding: LLM sees all files + a classify_file tool,
and calls the tool once per file. Multiple calls per LLM turn.

Compare with agent_classifier.py (batch structured output).
"""

from collections.abc import Callable

from langchain_core.tools import tool as langchain_tool

from agents.llm_client import _get_llm
from agents.agent_classifier import _merge_categories
from core.logging import get_logger

logger = get_logger(__name__)

ProgressCallback = Callable[[str, int, int, str], None]


# ---- Shared state for tool to record results ----

_results: dict[str, str] = {}


def _reset_results():
    global _results
    _results = {}


# ---- Tool definition ----

@langchain_tool
def classify_file(file_id: str, file_name: str, category: str) -> str:
    """将单个文件归类到语义化分组.
    Args:
        file_id: 文件标识符,必须使用输入中提供的原始id
        file_name: 文件名
        category: 语义化分类名,2-8字中文,不使用通用大类
    """
    _results[file_id] = category
    return f"ok: {file_name} -> {category}"


# ---- System prompt ----

SYSTEM_PROMPT = """你是文件分类器.根据文件名和扩展名将每个文件归类到语义化分组.

规则:
- 分组名为2-8字中文,不使用通用大类(如'文档''图片')
- file_id使用原始标识符,不得修改
- 对每个文件必须调用classify_file工具"""


# ---- Public API ----

def run_tool_classifier(files: list, on_progress: ProgressCallback = None) -> dict:
    """Classify files using tool calls (one tool call per file).

    Args:
        files: List of {id, name, extension} dicts
        on_progress: Optional callback(phase, current, total, message)

    Returns:
        {categories: [...], category_order: [...], total_files: N}
    """

    def _progress(phase, current, total, msg):
        if on_progress:
            on_progress(phase, current, total, msg)

    if not files:
        _progress("done", 0, 0, "no files")
        return {"categories": [], "category_order": [], "total_files": 0}

    _reset_results()
    total = len(files)
    _progress("classifying", 0, total, f"{total} files, tool-based")

    llm = _get_llm()
    llm_with_tools = llm.bind_tools([classify_file])

    classified_count = 0

    for fi, f in enumerate(files):
        fid = f["id"]
        fname = f["name"]
        fext = f.get("extension", "")

        logger.info("=== File %d/%d: %s (%s) [%s] ===", fi + 1, total, fid, fname, fext)
        _progress("classifying", fi, total,
                  f"file {fi + 1}/{total}: {fname}")

        user_prompt = f"分类文件: {fid}:{fname} [{fext}]"
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        response = llm_with_tools.invoke(messages)
        tool_calls = getattr(response, "tool_calls", None) or []

        if not tool_calls:
            logger.warning("  no tool call for %s, marking as 其他", fid)
            _results[fid] = "其他"
            continue

        # Execute tool calls, force-correct file_id to the one we sent
        for tc in tool_calls:
            args = tc.get("args", {})
            cat = args.get("category", "其他")
            # Override file_id with the correct one (LLM may hallucinate)
            args["file_id"] = fid
            args["file_name"] = fname
            classify_file.invoke(args)
            classified_count += 1
            logger.info("  -> %s", cat)

    turns = total  # one turn per file

    # Build output from results
    id_to_name = {f["id"]: f["name"] for f in files}

    # Fill unclassified
    for f in files:
        if f["id"] not in _results:
            _results[f["id"]] = "其他"

    # Merge synonyms (LLM may use different names across turns)
    raw_categories = set(_results.values())
    if len(raw_categories) > 1:
        _progress("merging", 0, 1, f"merging {len(raw_categories)} categories...")
        merge_map = _merge_categories(raw_categories)
        if merge_map:
            logger.info("Tool classifier: merge map %s", merge_map)
            for fid, cat in _results.items():
                if cat in merge_map:
                    _results[fid] = merge_map[cat]
        _progress("merging", 1, 1, "merge done")

    # Group by category
    cat_map: dict[str, list] = {}
    for fid, cat in _results.items():
        cat_map.setdefault(cat, []).append({
            "id": fid, "name": id_to_name.get(fid, "?"),
        })

    # Build ordered output
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

    _progress("done", total, total,
              f"tool-based done: {len(categories)} categories, {turns} LLM turns")

    logger.info("Tool classifier: %d files, %d categories, %d turns",
                total, len(categories), turns)
    return {
        "categories": categories,
        "category_order": [c["category_name"] for c in categories],
        "total_files": total,
        "llm_turns": turns,
    }
