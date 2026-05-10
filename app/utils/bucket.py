"""Bucket splitter for qwen3.5:9b prompt size limits."""

from core.config import PROMPT_CHAR_LIMIT, CHARS_PER_FILE


def build_file_entry(file_id: str, name: str) -> str:
    """Single file entry: 'name(id)' — qwen3.5:9b-friendly format"""
    return f"{name}({file_id})"


def estimate_chars(file_count: int, chars_per_file: int = None) -> int:
    """Estimate total chars for N files."""
    cpf = chars_per_file if chars_per_file is not None else CHARS_PER_FILE
    return file_count * cpf


def bucket_count(file_count: int, char_limit: int = None, chars_per_file: int = None) -> int:
    """Number of buckets needed for N files."""
    limit = char_limit if char_limit is not None else PROMPT_CHAR_LIMIT
    est = estimate_chars(file_count, chars_per_file)
    if est <= limit:
        return 1
    return (est + limit - 1) // limit


def split_files(files: list, char_limit: int = None, chars_per_file: int = None) -> list[list]:
    """Split file list into buckets, each under char_limit.

    Args:
        files: List of dicts with 'id' (str) and 'name' (str)
        char_limit: Max chars per bucket (default: PROMPT_CHAR_LIMIT)
        chars_per_file: Estimated chars per file entry (default: CHARS_PER_FILE)

    Returns:
        List of buckets, each bucket is a list of file dicts
    """
    limit = char_limit if char_limit is not None else PROMPT_CHAR_LIMIT
    buckets = []
    current_bucket = []
    current_chars = 0

    for f in files:
        entry_chars = len(build_file_entry(f["id"], f["name"])) + 2  # ", " separator
        if current_bucket and current_chars + entry_chars > limit:
            buckets.append(current_bucket)
            current_bucket = []
            current_chars = 0
        current_bucket.append(f)
        current_chars += entry_chars

    if current_bucket:
        buckets.append(current_bucket)

    return buckets


def format_bucket_prompt(bucket: list) -> str:
    """Format a bucket of files as a compact text prompt.

    Returns: "1:a.docx, 2:b.xlsx, 3:c.jpg"
    """
    return ", ".join(build_file_entry(f["id"], f["name"]) for f in bucket)
