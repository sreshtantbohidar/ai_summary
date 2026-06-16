"""
Report Generator — connection constants & config.
Reads from constants.py in the parent directory (shared ES/Ollama config).
"""

import os
import sys
import logging

# ── Shared constants from parent project ──────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import constants as _shared

# ── Elasticsearch ─────────────────────────────────────────────────────
ES_HOST        = _shared.ELASTIC_HOST          # 192.168.1.125
ES_PORT        = _shared.ELASTIC_PORT          # 9200
ES_SCHEME      = _shared.ELASTIC_CLIENT_SCHEME # https
ES_USER        = _shared.ELASTICSEARCH_USERNAME
ES_PASS        = _shared.ELASTICSEARCH_PASSWORD
ES_VERIFY      = False

VECTOR_INDEX   = "vec_fatboy_data"
SOURCE_INDEX   = "fatboy_data"
EMBED_DIM      = 768

# ── Ollama ────────────────────────────────────────────────────────────
OLLAMA_HOST    = _shared.ollama_api_host       # 192.168.1.125
OLLAMA_PORT    = _shared.ollama_api_port       # 11434
OLLAMA_URL     = f"http://{OLLAMA_HOST}:{OLLAMA_PORT}"
EMBED_MODEL    = "nomic-embed-text"
LLM_MODEL      = _shared.LLM_MODEL             # gemma2:9b-instruct-q8_0

# ── Report settings ───────────────────────────────────────────────────
REPORT_DIR     = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports")
MAX_CONTEXT_CHARS = 8000
TOP_K_RESULTS  = 10
MAX_SOURCES_IN_REPORT = 8

# ── Mode definitions ──────────────────────────────────────────────────
MODES = {
    "answer":    {"label": "Answer",    "icon": "💬", "color": "#4CAF50",
                 "description": "Factual, grounded Q&A with source citations"},
    "analyze":   {"label": "Analyze",   "icon": "🔍", "color": "#2196F3",
                 "description": "Deep thematic analysis, patterns, relationships"},
    "predict":   {"label": "Predict",   "icon": "🔮", "color": "#9C27B0",
                 "description": "Strategic predictions, scenarios, implications"},
    "summarize": {"label": "Summarize", "icon": "📝", "color": "#FF9800",
                 "description": "Comprehensive summary of key points and themes"},
}

# ── Logging ───────────────────────────────────────────────────────────
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(REPORT_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, "app.log")),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)
