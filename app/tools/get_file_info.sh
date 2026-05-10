#!/bin/bash
TOOLS_DIR="$(cd "$(dirname "$0")" && pwd)"
python3 "$TOOLS_DIR/tool_runner.py" get_file_info
