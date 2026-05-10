#!/bin/bash
TOOLS_DIR="$(cd "$(dirname "$0")" && pwd)"
python3 "$TOOLS_DIR/tool_runner.py" scan_parent_dir
