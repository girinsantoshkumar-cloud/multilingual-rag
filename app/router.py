from __future__ import annotations

from .config import CMI_THRESHOLD, RETRIEVAL_MIN_SCORE, TOP_K
from .ingest import search
from .models import Embedder
from .utils import compute_cmi, language_profile, transliterate_roman_hindi, transliterate_roman_tamil

PERSONAL_PATTERNS = (
    "my name", "what is my name", "remember", "i am ", "i'm ", "call me", "my favorite", "my preference",
    "mera naam", "मेरा नाम", "என் பெயர்", "என்னை நினைவில்", "who am i",
)
CASUAL_PATTERNS = ("hello", "hi", "hey", "thanks", "thank you", "good morning", "good evening", "bye", "okay", "ok")
DOCUMENT_PATTERNS = (
    "document", "file", "report", "policy", "policies", "uploaded", "according to", "source", "pdf", "docx",
    "refund", "delivery", "payment", "invoice", "procedure", "process", "methodology", "chapter", "section",
    "report", "பணம்", "திரும்ப", "रिफंड", "नीति",
)
FOLLOW_UP_PATTERNS = ("that", "this", "it", "they", "them", "those", "what about", "how about", "when does it", "why does it")

def retrieval_decision(query: str, history: list[dict] | None = None) -> dict:
    """Decide whether this turn needs document retrieval before embedding/search."""
    normalized = " ".join(query.lower().split())
    history = history or []
    if any(pattern in normalized for pattern in PERSONAL_PATTERNS):
        return {"retrieve": False, "mode": "conversation-memory", "reason": "personal or memory request"}
    if any(normalized == phrase or normalized.startswith(phrase + " ") for phrase in CASUAL_PATTERNS):
        return {"retrieve": False, "mode": "conversation", "reason": "casual conversation"}
    has_document_context = any(message.get("citations") for message in history if message.get("role") == "assistant")
    has_follow_up = any(pattern in normalized for pattern in FOLLOW_UP_PATTERNS)
    if has_follow_up and has_document_context:
        return {"retrieve": True, "mode": "document-follow-up", "reason": "follow-up to a cited document answer"}
    if any(pattern in normalized for pattern in DOCUMENT_PATTERNS):
        return {"retrieve": True, "mode": "document-rag", "reason": "document-related terms detected"}
    if has_follow_up:
        return {"retrieve": False, "mode": "conversation", "reason": "ambiguous follow-up without document context"}
    # General factual questions are eligible for RAG; explicit personal/casual turns above are not.
    if normalized.endswith("?") or normalized.startswith(("what ", "how ", "when ", "where ", "why ", "explain ")):
        return {"retrieve": True, "mode": "document-rag", "reason": "factual question"}
    return {"retrieve": False, "mode": "conversation", "reason": "no document intent detected"}

def query_views(query: str, matrix: str, cmi: float) -> list[tuple[str, str]]:
    views = [("surface", query)]
    transliterator = transliterate_roman_tamil if matrix == "ta" else transliterate_roman_hindi
    if cmi >= CMI_THRESHOLD or any(ord(c) < 128 for c in query):
        native = transliterator(query)
        if native != query:
            views.append(("native-script", native))
    if cmi >= CMI_THRESHOLD:
        # Offline-safe canonical/pivot views. Translation models can be plugged in later.
        views.append(("matrix-canonical", query if matrix == "en" else transliterator(query)))
        views.append(("english-pivot", query))
    return views[:4]

def route_query(query: str, top_k: int = TOP_K, retrieval_query: str | None = None) -> dict:
    query = query.strip()
    if not query:
        raise ValueError("Query cannot be empty")
    retrieval_query = (retrieval_query or query).strip()
    cmi = compute_cmi(query)
    profile = language_profile(query)
    views = query_views(retrieval_query, profile["matrix_language"], compute_cmi(retrieval_query))
    embedder = Embedder()
    embeddings = embedder.encode([text for _, text in views], is_query=True)
    merged = {}
    for (view_name, _), vector in zip(views, embeddings):
        for result in search(vector.reshape(1, -1), top_k=top_k):
            result["view"] = view_name
            previous = merged.get(result["id"])
            if not previous or result["score"] > previous["score"]:
                merged[result["id"]] = result
    retrieved = [result for result in sorted(merged.values(), key=lambda r: r["score"], reverse=True) if result["score"] >= RETRIEVAL_MIN_SCORE][:top_k]
    return {"query": query, "cmi": cmi, "matrix_language": profile["matrix_language"], "views": [{"name": n, "text": t} for n, t in views], "results": retrieved}

def build_context(results: list[dict]) -> str:
    return "\n\n".join(f"[{r['filename']} · chunk {r['chunk_id']}] {r['text']}" for r in results)
