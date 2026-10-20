from __future__ import annotations

from .config import CMI_THRESHOLD, TOP_K
from .ingest import search
from .models import Embedder
from .utils import compute_cmi, language_profile, transliterate_roman_hindi

def query_views(query: str, matrix: str, cmi: float) -> list[tuple[str, str]]:
    views = [("surface", query)]
    if cmi >= CMI_THRESHOLD or any(ord(c) < 128 for c in query):
        native = transliterate_roman_hindi(query)
        if native != query:
            views.append(("native-script", native))
    if cmi >= CMI_THRESHOLD:
        # Offline-safe canonical/pivot views. Translation models can be plugged in later.
        views.append(("matrix-canonical", query if matrix == "en" else transliterate_roman_hindi(query)))
        views.append(("english-pivot", query))
    return views[:4]

def route_query(query: str, top_k: int = TOP_K) -> dict:
    query = query.strip()
    if not query:
        raise ValueError("Query cannot be empty")
    cmi = compute_cmi(query)
    profile = language_profile(query)
    views = query_views(query, profile["matrix_language"], cmi)
    embedder = Embedder()
    embeddings = embedder.encode([text for _, text in views])
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
