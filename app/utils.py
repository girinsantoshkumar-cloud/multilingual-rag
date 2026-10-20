from __future__ import annotations

import hashlib
import re
import unicodedata
from pathlib import Path
from typing import Iterable

ALLOWED_EXTENSIONS = {".pdf", ".txt", ".docx"}
DEVANAGARI = re.compile(r"[\u0900-\u097F]")
LATIN = re.compile(r"[A-Za-z]")
WORD_RE = re.compile(r"[\w\u0900-\u097F]+", re.UNICODE)
ENGLISH_HINTS = {"the", "is", "are", "what", "when", "where", "how", "can", "please", "refund", "status", "order", "account", "payment", "return", "help", "and", "or", "for", "with", "from", "to"}

def words(text: str) -> list[str]:
    return WORD_RE.findall(text)

def token_language(token: str) -> str:
    if DEVANAGARI.search(token):
        return "hi"
    if LATIN.search(token):
        return "en" if token.lower() in ENGLISH_HINTS or token.isascii() else "roman"
    return "other"

def language_profile(text: str) -> dict:
    toks = words(text)
    counts = {"hi": 0, "en": 0, "roman": 0, "other": 0}
    for token in toks:
        counts[token_language(token)] += 1
    script_tokens = counts["hi"] + counts["en"] + counts["roman"]
    if not script_tokens:
        matrix = "unknown"
    elif counts["hi"] > counts["en"] + counts["roman"]:
        matrix = "hi"
    else:
        matrix = "en"
    return {"counts": counts, "tokens": len(toks), "matrix_language": matrix}

def compute_cmi(text: str) -> float:
    """Approximate CMI as minority-language share among meaningful tokens.

    The implementation is intentionally dependency-free. Devanagari is Hindi;
    Latin tokens are English/Roman Hindi and are counted as a second variety
    when a Devanagari variety is present. A monolingual Roman-English query is 0.
    """
    profile = language_profile(text)
    counts = profile["counts"]
    if counts["hi"] and (counts["en"] + counts["roman"]):
        total = counts["hi"] + counts["en"] + counts["roman"]
        return round(1 - max(counts["hi"], counts["en"] + counts["roman"]) / total, 4)
    if counts["en"] and counts["roman"]:
        total = counts["en"] + counts["roman"]
        return round(min(counts["en"], counts["roman"]) / total, 4)
    return 0.0

def safe_filename(filename: str) -> str:
    name = Path(filename or "upload").name
    name = unicodedata.normalize("NFKC", name)
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._") or "upload"
    return name[:180]

def file_id(filename: str) -> str:
    return hashlib.sha256(filename.encode("utf-8")).hexdigest()[:16]

def transliterate_roman_hindi(text: str) -> str:
    """Best-effort offline transliteration for common Roman Hindi words."""
    mapping = {
        "mera": "मेरा", "meri": "मेरी", "mere": "मेरे", "kab": "कब", "tak": "तक",
        "aayega": "आएगा", "aayegi": "आएगी", "refund": "रिफंड", "ka": "का", "ki": "की",
        "ke": "के", "hai": "है", "hain": "हैं", "kya": "क्या", "kyun": "क्यों",
        "chahiye": "चाहिए", "mujhe": "मुझे", "batao": "बताओ", "kitna": "कितना",
        "kitne": "कितने", "din": "दिन", "mein": "में", "se": "से", "ko": "को",
        "aap": "आप", "kaise": "कैसे", "karu": "करूं", "karen": "करें", "please": "कृपया",
    }
    return re.sub(r"[A-Za-z]+", lambda m: mapping.get(m.group(0).lower(), m.group(0)), text)

def sanitize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()
