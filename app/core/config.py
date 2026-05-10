import os

MODEL_NAME = os.getenv("AGENT_MODEL_NAME", "qwen3.5:9b")
BASE_URL = os.getenv("AGENT_BASE_URL", "http://localhost:11434/v1")
API_KEY = os.getenv("AGENT_API_KEY", "11111")
TEMPERATURE = 0.0
# qwen3.5:9b needs tight limit — too high = all consumed by reasoning.
# 1024 is the sweet spot: model stops naturally (finish=stop).
MAX_TOKENS = 1024

STORE_DIR = os.path.join(
    os.path.expanduser("~"),
    ".agent-file-organizer"
)

TOOLS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "tools"
)
