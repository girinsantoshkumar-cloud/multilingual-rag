from __future__ import annotations

import hashlib
import os
import re
from typing import Sequence

import numpy as np

from .config import EMBEDDING_MODEL, OPENAI_BASE_URL, OPENAI_MODEL

class Embedder:
    def __init__(self):
        self.model = None
        self.name = "hashing-fallback"
        try:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(EMBEDDING_MODEL)
            self.name = EMBEDDING_MODEL
        except Exception:
            pass

    @property
    def dimension(self) -> int:
        return int(self.model.get_sentence_embedding_dimension()) if self.model else 384

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        if self.model:
            return np.asarray(self.model.encode(list(texts), normalize_embeddings=True, show_progress_bar=False), dtype="float32")
        vectors = np.zeros((len(texts), self.dimension), dtype="float32")
        for row, text in enumerate(texts):
            for token in re.findall(r"\w+", text.lower()):
                digest = hashlib.sha256(token.encode()).digest()
                index = int.from_bytes(digest[:4], "big") % self.dimension
                vectors[row, index] += 1.0 if digest[4] % 2 else -1.0
            norm = np.linalg.norm(vectors[row])
            if norm:
                vectors[row] /= norm
        return vectors

class Generator:
    def __init__(self):
        self.client = None
        self.model_name = "extractive-fallback"
        if os.getenv("OPENAI_API_KEY") and OPENAI_BASE_URL:
            try:
                from openai import OpenAI
                self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"), base_url=OPENAI_BASE_URL)
                self.model_name = OPENAI_MODEL
            except Exception:
                pass

    def answer(self, query: str, context: str, matrix_language: str, cmi: float) -> str:
        if self.client:
            try:
                prompt = ("Answer only from the supplied context. Mirror the user's language mix and be concise. "
                          f"Matrix language: {matrix_language}; CMI: {cmi:.2f}.\n\nContext:\n{context}\n\nQuestion: {query}")
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[{"role": "system", "content": "You are a grounded code-switching RAG assistant."}, {"role": "user", "content": prompt}],
                    temperature=0.1,
                    max_tokens=300,
                )
                content = response.choices[0].message.content if response.choices else None
                if content:
                    return content.strip()
            except Exception:
                # The app remains usable when an API endpoint is unavailable.
                pass
        passages = [p.strip() for p in context.split("\n\n") if p.strip()]
        if not passages:
            return "I could not find supporting information in the indexed documents."
        lead = passages[0]
        if lead.startswith("[") and "] " in lead:
            lead = lead.split("] ", 1)[1]
        if matrix_language == "hi":
            return f"Available documents ke according: {lead}"
        if matrix_language == "ta":
            return f"Indexed documents படி: {lead}"
        if cmi >= 0.2:
            return f"According to the indexed documents: {lead}"
        return f"According to the indexed documents: {lead}"
