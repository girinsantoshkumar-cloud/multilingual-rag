from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw_docs"
CHUNKS_DIR = DATA_DIR / "chunks"
VECTOR_DIR = DATA_DIR / "vector_db"
RESULTS_DIR = ROOT / "results"

MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", 25 * 1024 * 1024))
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", 1000))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", 200))
TOP_K = int(os.getenv("TOP_K", 5))
RETRIEVAL_MIN_SCORE = float(os.getenv("RETRIEVAL_MIN_SCORE", "0.35"))
CMI_THRESHOLD = float(os.getenv("CMI_THRESHOLD", 0.20))
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "intfloat/multilingual-e5-large")
LLM_MODEL = os.getenv("LLM_MODEL", "")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:14b")
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "120"))
SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-only-change-me")

for directory in (RAW_DIR, CHUNKS_DIR, VECTOR_DIR, RESULTS_DIR):
    directory.mkdir(parents=True, exist_ok=True)
