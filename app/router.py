from __future__ import annotations

from .config import CMI_THRESHOLD, TOP_K
from .ingest import search
from .models import Embedder
from .utils import compute_cmi, language_profile, transliterate_roman_hindi, transliterate_roman_tamil

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
    retrieved = sorted(merged.values(), key=lambda r: r["score"], reverse=True)[:top_k]
    return {"query": query, "cmi": cmi, "matrix_language": profile["matrix_language"], "views": [{"name": n, "text": t} for n, t in views], "results": retrieved}

def build_context(results: list[dict]) -> str:
    return "\n\n".join(f"[{r['filename']} · chunk {r['chunk_id']}] {r['text']}" for r in results)
