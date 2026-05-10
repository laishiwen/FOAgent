"""Unified tool runner - reads stdin JSON, dispatches to tool, writes stdout JSON.

Each tool uses subprocess to call actual bash commands (find, stat, mkdir, mv, file)
for the底层 operations. The runner handles JSON I/O and error formatting.
"""

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone


def _ok(**kwargs):
    return json.dumps({"success": True, "error": None, **kwargs}, ensure_ascii=False)


def _err(msg):
    return json.dumps({"success": False, "error": msg})


# ---- Tool implementations ----

def scan_parent_dir(data: dict) -> str:
    root_path = os.path.abspath(data["root_path"])
    if not os.path.isdir(root_path):
        return _err("root_path not found or not a directory")

    files = []
    subdirs = []
    by_extension = {}

    try:
        for entry in os.scandir(root_path):
            if entry.name.startswith("."):
                continue
            if entry.is_symlink():
                files.append({
                    "name": entry.name,
                    "path": entry.path,
                    "extension": os.path.splitext(entry.name)[1].lower(),
                    "size_bytes": entry.stat().st_size,
                    "modified_at": datetime.fromtimestamp(
                        entry.stat().st_mtime, tz=timezone.utc
                    ).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "is_hidden": False,
                    "is_symlink": True,
                })
            elif entry.is_file():
                ext = os.path.splitext(entry.name)[1].lower()
                st = entry.stat()
                files.append({
                    "name": entry.name,
                    "path": entry.path,
                    "extension": ext,
                    "size_bytes": st.st_size,
                    "modified_at": datetime.fromtimestamp(
                        st.st_mtime, tz=timezone.utc
                    ).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "is_hidden": False,
                    "is_symlink": False,
                })
                by_extension[ext] = by_extension.get(ext, 0) + 1
            elif entry.is_dir():
                subdirs.append(entry.name)
    except OSError as e:
        return _err(f"scan failed: {e}")

    return _ok(
        root_path=root_path,
        files=sorted(files, key=lambda f: f["name"].lower()),
        subdirs=sorted(subdirs, key=lambda d: d.lower()),
        stats={
            "file_count": len(files),
            "subdir_count": len(subdirs),
            "by_extension": by_extension,
        },
    )


def get_file_info(data: dict) -> str:
    file_path = data["file_path"]
    if not os.path.isfile(file_path):
        return _err("file not found")

    name = os.path.basename(file_path)
    _, ext_raw = os.path.splitext(name)
    ext = ext_raw.lower()

    # Use 'file' command for MIME type (bash)
    try:
        result = subprocess.run(
            ["file", "--mime-type", "-b", file_path],
            capture_output=True, text=True, timeout=5,
        )
        mime = result.stdout.strip()
    except Exception:
        mime = "unknown"

    # Map MIME to kind
    kind = "other"
    if mime.startswith("text/") or mime in (
        "application/json", "application/xml",
        "application/javascript", "application/pdf",
    ):
        kind = "document"
    elif mime.startswith("image/"):
        kind = "image"
    elif mime.startswith("video/"):
        kind = "video"
    elif mime.startswith("audio/"):
        kind = "audio"
    elif mime in (
        "application/zip", "application/gzip",
        "application/x-tar", "application/x-7z-compressed",
        "application/x-rar-compressed",
    ):
        kind = "archive"
    elif "openxmlformats-officedocument" in mime:
        kind = "document"

    st = os.stat(file_path)
    mtime = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )

    return _ok(
        file_path=file_path,
        name=name,
        extension=ext,
        mime_type=mime,
        kind=kind,
        size_bytes=st.st_size,
        modified_at=mtime,
    )


def bash_create_dirs(data: dict) -> str:
    root_path = os.path.abspath(data["root_path"])
    dry_run = data.get("dry_run", True)
    directories = data.get("directories", [])

    canon_root = os.path.realpath(root_path)
    steps = []

    for i, d in enumerate(directories):
        target = os.path.join(root_path, d)
        step_id = f"mkdir-{i + 1:03d}"
        cmd = f"mkdir -p -- '{target}'"

        # Path escape check
        canon_target = os.path.realpath(target) if os.path.exists(
            os.path.dirname(target)
        ) else os.path.realpath(os.path.dirname(target)) + "/" + os.path.basename(target)
        if not canon_target.startswith(canon_root + os.sep) and canon_target != canon_root:
            steps.append({
                "step_id": step_id, "status": "failed",
                "command": cmd, "target_path": target,
                "error": "target outside root_path",
            })
            return json.dumps({"success": False, "error": None, "steps": steps}, ensure_ascii=False)

        if dry_run:
            steps.append({
                "step_id": step_id, "status": "planned",
                "command": cmd, "target_path": target,
            })
        else:
            try:
                os.makedirs(target, exist_ok=True)
                steps.append({
                    "step_id": step_id, "status": "completed",
                    "command": cmd, "target_path": target,
                })
            except OSError as e:
                steps.append({
                    "step_id": step_id, "status": "failed",
                    "command": cmd, "target_path": target,
                    "error": str(e),
                })
                return json.dumps({"success": False, "error": None, "steps": steps}, ensure_ascii=False)

    return json.dumps({"success": True, "error": None, "steps": steps}, ensure_ascii=False)


def bash_dry_run_moves(data: dict) -> str:
    root_path = data["root_path"]
    moves = data.get("moves", [])

    canon_root = os.path.realpath(root_path)
    checks = []
    conflicts = []
    all_ok = True

    for move in moves:
        src = move["source_path"]
        tgt = move["target_path"]

        src_exists = os.path.isfile(src)
        tgt_absent = not os.path.exists(tgt)

        try:
            tgt_dir = os.path.dirname(tgt)
            base = os.path.basename(tgt)
            canon_tgt_dir = os.path.realpath(tgt_dir) if os.path.exists(tgt_dir) else tgt_dir
            canon_tgt = os.path.join(canon_tgt_dir, base)
        except Exception:
            canon_tgt = ""
        within_root = canon_tgt.startswith(canon_root + os.sep) if canon_tgt else False

        check = {
            "source_path": src, "target_path": tgt,
            "source_exists": src_exists,
            "target_absent": tgt_absent,
            "within_root": within_root,
        }
        checks.append(check)

        if not src_exists or not tgt_absent or not within_root:
            all_ok = False
            conflicts.append({
                "source": src, "target": tgt,
                "source_exists": src_exists,
                "target_absent": tgt_absent,
                "within_root": within_root,
            })

    return _ok(can_execute=all_ok, conflicts=conflicts, checks=checks)


def bash_move_files(data: dict) -> str:
    root_path = data["root_path"]
    moves = data.get("moves", [])

    canon_root = os.path.realpath(root_path)
    steps = []
    completed = 0
    failed = 0

    for i, move in enumerate(moves):
        src = move["source_path"]
        tgt = move["target_path"]
        step_id = f"move-{i + 1:03d}"
        cmd = f"mv -- '{src}' '{tgt}'"

        if not os.path.isfile(src):
            steps.append({
                "step_id": step_id, "status": "failed",
                "command": cmd, "source_path": src, "target_path": tgt,
                "error": "source not found",
            })
            failed += 1
            break

        try:
            tgt_dir = os.path.dirname(tgt)
            canon_tgt_dir = os.path.realpath(tgt_dir) if os.path.exists(tgt_dir) else tgt_dir
            canon_tgt = os.path.join(canon_tgt_dir, os.path.basename(tgt))
        except Exception:
            canon_tgt = ""
        if not canon_tgt.startswith(canon_root + os.sep):
            steps.append({
                "step_id": step_id, "status": "failed",
                "command": cmd, "source_path": src, "target_path": tgt,
                "error": "target outside root_path",
            })
            failed += 1
            break

        try:
            os.makedirs(os.path.dirname(tgt), exist_ok=True)
            shutil.move(src, tgt)  # Uses OS-level move (same as mv)
            steps.append({
                "step_id": step_id, "status": "completed",
                "command": cmd, "source_path": src, "target_path": tgt,
            })
            completed += 1
        except OSError as e:
            steps.append({
                "step_id": step_id, "status": "failed",
                "command": cmd, "source_path": src, "target_path": tgt,
                "error": str(e),
            })
            failed += 1
            break

    success = failed == 0
    return json.dumps({
        "success": success, "error": None,
        "steps": steps,
        "summary": {"total": len(moves), "completed": completed, "failed": failed},
    }, ensure_ascii=False)


def bash_rollback(data: dict) -> str:
    log_path = data["execution_log_path"]

    if not os.path.isfile(log_path):
        return _err("execution_log not found")

    with open(log_path, "r", encoding="utf-8") as f:
        log = json.load(f)

    move_steps = [
        s for s in log.get("steps", [])
        if s["step_type"] == "move_file" and s["status"] == "completed"
    ]
    move_steps.reverse()

    rollback_steps = []
    cleaned_dirs = set()

    for i, step in enumerate(move_steps):
        src = step["source_path"]
        tgt = step["target_path"]
        rb_id = f"rollback-{i + 1:03d}"
        cmd = f"mv -- '{tgt}' '{src}'"

        try:
            os.makedirs(os.path.dirname(src), exist_ok=True)
            if os.path.exists(tgt):
                shutil.move(tgt, src)
            status = "completed"
            cleaned_dirs.add(os.path.dirname(tgt))
        except OSError:
            status = "failed"

        rollback_steps.append({
            "step_id": rb_id,
            "original_step_id": step["step_id"],
            "step_type": "rollback_move_file",
            "status": status,
            "command": cmd,
            "source_path": tgt,
            "target_path": src,
        })

    cleaned = []
    for d in sorted(cleaned_dirs):
        if os.path.isdir(d) and not os.listdir(d):
            try:
                os.rmdir(d)
                cleaned.append(d)
            except OSError:
                pass

    return _ok(steps=rollback_steps, cleaned_dirs=cleaned)


# ---- Tool dispatch ----

TOOLS = {
    "scan_parent_dir": scan_parent_dir,
    "get_file_info": get_file_info,
    "bash_create_dirs": bash_create_dirs,
    "bash_dry_run_moves": bash_dry_run_moves,
    "bash_move_files": bash_move_files,
    "bash_rollback": bash_rollback,
}


def run_tool(tool_name: str, stdin_data: str) -> str:
    if tool_name not in TOOLS:
        return _err(f"unknown tool: {tool_name}")
    try:
        data = json.loads(stdin_data)
    except json.JSONDecodeError as e:
        return _err(f"invalid JSON input: {e}")
    try:
        return TOOLS[tool_name](data)
    except Exception as e:
        return _err(f"tool error: {e}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(_err("usage: tool_runner.py <tool_name>"), file=sys.stderr)
        sys.exit(1)
    tool_name = sys.argv[1]
    stdin_data = sys.stdin.read()
    result = run_tool(tool_name, stdin_data)
    print(result)
