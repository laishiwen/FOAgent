#!/bin/bash
TOOLS_DIR="$(cd "$(dirname "$0")" && pwd)"
python3 "$TOOLS_DIR/tool_runner.py" bash_move_files
