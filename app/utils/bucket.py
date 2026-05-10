"""Bucket splitter for qwen3.5:9b prompt size limits."""

from core.config import PROMPT_CHAR_LIMIT, CHARS_PER_FILE


def build_file_entry(file_id: str, name: str) -> str:
    """Single file entry: 'name(id)' — qwen3.5:9b-friendly format"""
    return f"{name}({file_id})"


def estimate_chars(file_count: int) -> int:
    """Estimate total chars for N files."""
    return file_count * CHARS_PER_FILE


def bucket_count(file_count: int) -> int:
    """Number of buckets needed for N files."""
    est = estimate_chars(file_count)
    if est <= PROMPT_CHAR_LIMIT:
        return 1
    return (est + PROMPT_CHAR_LIMIT - 1) // PROMPT_CHAR_LIMIT


def split_files(files: list) -> list[list]:
    """Split file list into buckets, each under PROMPT_CHAR_LIMIT.

    Args:
        files: List of dicts with 'id' (str) and 'name' (str)

    Returns:
        List of buckets, each bucket is a list of file dicts
    """
    buckets = []
    current_bucket = []
    current_chars = 0

    for f in files:
        entry_chars = len(build_file_entry(f["id"], f["name"])) + 2  # ", " separator
        if current_bucket and current_chars + entry_chars > PROMPT_CHAR_LIMIT:
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
