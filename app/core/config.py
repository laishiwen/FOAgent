import os

MODEL_NAME = os.getenv("AGENT_MODEL_NAME", "qwen3.5:9b")
BASE_URL = os.getenv("AGENT_BASE_URL", "http://localhost:11434/v1")
API_KEY = os.getenv("AGENT_API_KEY", "11111")
TEMPERATURE = 0.0
MAX_TOKENS = 0  # 0 = no limit

PROMPT_CHAR_LIMIT = 80
CHARS_PER_FILE = 35

# Classifier uses larger windows since it processes more files at once
CLASSIFIER_CHAR_LIMIT = 500
CLASSIFIER_CHARS_PER_FILE = 50

STORE_DIR = os.path.join(os.path.expanduser("~"), ".agent-file-organizer")
APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS_DIR = os.path.join(APP_DIR, "tools")
