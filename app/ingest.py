from __future__ import annotations

import argparse
import json
import mimetypes
import re
import shutil
from pathlib import Path

import numpy as np

from .config import CHUNK_OVERLAP, CHUNK_SIZE, CHUNKS_DIR, RAW_DIR, VECTOR_DIR
from .models import Embedder
from .utils import ALLOWED_EXTENSIONS, file_id, safe_filename, sanitize_text

STORE_FILE = VECTOR_DIR / "store.json"

def extract_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".txt":
        return path.read_text(encoding="utf-8", errors="replace")
    if suffix == ".pdf":
        import fitz
        with fitz.open(path) as doc:
            return "\n".join(page.get_text() for page in doc)
    if suffix == ".docx":
        from docx import Document
        doc = Document(path)
        return "\n".join(p.text for p in doc.paragraphs)
    raise ValueError(f"Unsupported extension: {suffix}")

def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    text = sanitize_text(text)
    if not text:
        return []
    sentences = re.split(r"(?<=[.!?।])\s+", text)
    chunks, current = [], ""
    for sentence in sentences:
        if current and len(current) + len(sentence) + 1 > size:
            chunks.append(current.strip())
            current = current[-overlap:] + " " if overlap else ""
        current += sentence + " "
    if current.strip():
        chunks.append(current.strip())
    return chunks

def _load_store() -> dict:
    if STORE_FILE.exists():
        return json.loads(STORE_FILE.read_text(encoding="utf-8"))
    return {"embedding_model": "", "dimension": 0, "items": []}

def _save_store(store: dict) -> None:
    tmp = STORE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(store, ensure_ascii=False), encoding="utf-8")
    tmp.replace(STORE_FILE)

def _validate_signature(path: Path, extension: str | None = None) -> None:
    ext = (extension or path.suffix).lower()
    header = path.read_bytes()[:8]
    if ext == ".pdf" and not header.startswith(b"%PDF"):
        raise ValueError("File signature does not match PDF")
    if ext == ".docx" and not header.startswith(b"PK"):
        raise ValueError("File signature does not match DOCX")

def ingest_file(source: str | Path, original_name: str | None = None) -> dict:
    source = Path(source)
    original_name = original_name or source.name
    filename = safe_filename(original_name)
    if Path(filename).suffix.lower() not in ALLOWED_EXTENSIONS:
        raise ValueError("Only PDF, DOCX, and TXT files are allowed")
    _validate_signature(source, Path(filename).suffix)
    stored = RAW_DIR / filename
    shutil.copyfile(source, stored) if source.resolve() != stored.resolve() else None
    text = extract_text(stored)
    chunks = chunk_text(text)
    if not chunks:
        raise ValueError("No readable text found in document")
    embedder = Embedder()
    vectors = embedder.encode(chunks)
    store = _load_store()
    store["items"] = [item for item in store["items"] if item["filename"] != filename]
    for idx, (chunk, vector) in enumerate(zip(chunks, vectors)):
        store["items"].append({"id": f"{file_id(filename)}-{idx}", "filename": filename, "chunk_id": idx, "language": "auto", "text": chunk, "embedding": vector.tolist()})
    store["embedding_model"] = embedder.name
    store["dimension"] = embedder.dimension
    _save_store(store)
    (CHUNKS_DIR / f"{Path(filename).stem}.json").write_text(json.dumps({"filename": filename, "chunks": chunks}, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"filename": filename, "chunks": len(chunks), "embedding_model": embedder.name}

def ingest_path(path: str | Path) -> list[dict]:
    path = Path(path)
    files = [path] if path.is_file() else sorted(p for p in path.iterdir() if p.suffix.lower() in ALLOWED_EXTENSIONS)
    return [ingest_file(p) for p in files]

def list_documents() -> list[dict]:
    store = _load_store()
    docs = {}
    for item in store["items"]:
        docs.setdefault(item["filename"], 0)
        docs[item["filename"]] += 1
    return [{"filename": name, "chunks": count} for name, count in sorted(docs.items())]

def search(query_vectors: np.ndarray, top_k: int = 5) -> list[dict]:
    store = _load_store()
    items = store.get("items", [])
    if not items:
        return []
    matrix = np.asarray([item["embedding"] for item in items], dtype="float32")
    scores = matrix @ query_vectors.T
    best = scores.max(axis=1)
    order = np.argsort(-best)[:top_k]
    results = []
    for index in order:
        result = dict(items[int(index)])
        result["score"] = round(float(best[index]), 4)
        result.pop("embedding", None)
        results.append(result)
    return results

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest PDF, DOCX, and TXT files")
    parser.add_argument("--input", required=True)
    args = parser.parse_args()
    for result in ingest_path(args.input):
        print(json.dumps(result, ensure_ascii=False))
