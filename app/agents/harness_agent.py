"""Harness Agent: 终检器 - ID-based compact review."""

from pydantic import BaseModel, Field

from agents.llm_client import call_llm
from core.logging import get_logger

logger = get_logger(__name__)


class CompletenessCheck(BaseModel):
    passed: bool = True
    total_files: int = 0
    classified_files: int = 0
    unclassified_files: int = 0
    detail: str = ""


class SpotCheck(BaseModel):
    passed: bool = True
    samples_checked: int = 0
    issues_found: int = 0
    detail: str = ""


class ConsistencyCheck(BaseModel):
    passed: bool = True
    planned_moves: int = 0
    actual_moves: int = 0
    mismatches: int = 0
    detail: str = ""


class Checks(BaseModel):
    completeness: CompletenessCheck = Field(default_factory=CompletenessCheck)
    association_spot_check: SpotCheck = Field(default_factory=SpotCheck)
    naming_spot_check: SpotCheck = Field(default_factory=SpotCheck)
    execution_consistency: ConsistencyCheck = Field(default_factory=ConsistencyCheck)


class HarnessOutput(BaseModel):
    verdict: str = Field(default="warn", description="pass, warn, or fail")
    overall_assessment: str = ""
    checks: Checks = Field(default_factory=Checks)
    issues: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)


SYSTEM_PROMPT = '你是文件分类终检器.独立复查分类结果.输出pass/warn/fail评估.'


def _make_default(files_count: int = 0) -> dict:
    return {
        "verdict": "pass", "overall_assessment": "no files",
        "checks": {
            "completeness": {"passed": True, "total_files": files_count,
                             "classified_files": files_count, "unclassified_files": 0,
                             "detail": "no files" if files_count == 0 else ""},
            "association_spot_check": {"passed": True, "samples_checked": 0,
                                       "issues_found": 0, "detail": ""},
            "naming_spot_check": {"passed": True, "samples_checked": 0,
                                  "issues_found": 0, "detail": ""},
            "execution_consistency": {"passed": True, "planned_moves": 0,
                                      "actual_moves": 0, "mismatches": 0, "detail": ""},
        },
        "issues": [], "suggestions": [],
    }


def run_harness_agent(files: list, associations: dict, plan: dict,
                      execution_log: dict) -> dict:
    if not files:
        return _make_default(0)

    id_to_name = {f["id"]: f["name"] for f in files}
    total = len(files)

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

    classified_ids = set()
    for c in plan.get("categories", []):
        classified_ids.update(c.get("member_ids", c.get("members", [])))
    unclassified = [f"{fid}:{id_to_name[fid]}" for fid in id_to_name
                    if fid not in classified_ids]

    user_prompt = (
        f"review: {total} files | groups: {group_summary} | categories: {cat_summary}"
        f" | moves: {planned} planned/{executed} actual"
        + (f" | unclassified: {', '.join(unclassified[:10])}" if unclassified else "")
        + "."
    )

    if len(user_prompt) > 400:
        user_prompt = (
            f"review: {total} files | {len(associations.get('groups',[]))} groups"
            f" | {len(plan.get('categories',[]))} categories"
            f" | moves {planned} planned/{executed} actual."
        )

    logger.info("Harness: reviewing %d files", total)
    result = call_llm(HarnessOutput, SYSTEM_PROMPT, user_prompt)

    return {
        "verdict": result.verdict,
        "overall_assessment": result.overall_assessment,
        "checks": result.checks.model_dump(),
        "issues": result.issues,
        "suggestions": result.suggestions,
    }
