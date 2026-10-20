from __future__ import annotations

import hashlib
import re
import unicodedata
from pathlib import Path
from typing import Iterable

ALLOWED_EXTENSIONS = {".pdf", ".txt", ".docx"}
DEVANAGARI = re.compile(r"[\u0900-\u097F]")
TAMIL = re.compile(r"[\u0B80-\u0BFF]")
LATIN = re.compile(r"[A-Za-z]")
WORD_RE = re.compile(r"[\w\u0900-\u097F\u0B80-\u0BFF]+", re.UNICODE)
ENGLISH_HINTS = {"the", "is", "are", "what", "when", "where", "how", "can", "please", "refund", "status", "order", "account", "payment", "return", "help", "and", "or", "for", "with", "from", "to"}
ROMAN_HINDI_HINTS = {"mera", "meri", "mere", "kab", "tak", "aayega", "aayegi", "ka", "ki", "ke", "hai", "hain", "kya", "kyun", "chahiye", "mujhe", "batao", "kitna", "kitne", "din", "mein", "se", "ko", "aap", "kaise", "karu", "karen"}
ROMAN_TAMIL_HINTS = {"naan", "en", "enakku", "ennoda", "enna", "eppo", "eppothu", "eppozhudhu", "varum", "varuthu", "vandhadhu", "irukku", "irukkum", "ungal", "unga", "kudunga", "venum", "aagum", "naal", "naatkal", "ulla", "thiruppi", "thirumba", "epdi", "yennaku"}

def words(text: str) -> list[str]:
    return WORD_RE.findall(text)

def token_language(token: str) -> str:
    if DEVANAGARI.search(token):
        return "hi"
    if TAMIL.search(token):
        return "ta"
    if LATIN.search(token):
        lowered = token.lower()
        if lowered in ROMAN_HINDI_HINTS:
            return "hi_roman"
        if lowered in ROMAN_TAMIL_HINTS:
            return "ta_roman"
        return "en" if lowered in ENGLISH_HINTS or token.isascii() else "roman"
    return "other"

def language_profile(text: str) -> dict:
    toks = words(text)
    counts = {"hi": 0, "hi_roman": 0, "ta": 0, "ta_roman": 0, "en": 0, "roman": 0, "other": 0}
    for token in toks:
        counts[token_language(token)] += 1
    hindi_tokens = counts["hi"] + counts["hi_roman"]
    tamil_tokens = counts["ta"] + counts["ta_roman"]
    english_tokens = counts["en"] + counts["roman"]
    script_tokens = hindi_tokens + tamil_tokens + english_tokens
    if not script_tokens:
        matrix = "unknown"
    elif hindi_tokens > tamil_tokens and hindi_tokens > english_tokens:
        matrix = "hi"
    elif tamil_tokens > hindi_tokens and tamil_tokens > english_tokens:
        matrix = "ta"
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
    indic_tokens = counts["hi"] + counts["hi_roman"] + counts["ta"] + counts["ta_roman"]
    english_tokens = counts["en"] + counts["roman"]
    if indic_tokens and english_tokens:
        total = indic_tokens + english_tokens
        return round(1 - max(indic_tokens, english_tokens) / total, 4)
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

def transliterate_roman_tamil(text: str) -> str:
    """Best-effort offline transliteration for common Roman Tamil words."""
    mapping = {
        "naan": "நான்", "en": "என்", "enakku": "எனக்கு", "ennoda": "என்னோட", "enna": "என்ன",
        "eppo": "எப்போது", "eppothu": "எப்போது", "eppozhudhu": "எப்போது", "varum": "வரும்",
        "varuthu": "வருது", "vandhadhu": "வந்தது", "irukku": "இருக்கு", "irukkum": "இருக்கும்",
        "ungal": "உங்கள்", "unga": "உங்க", "kudunga": "கொடுங்க", "venum": "வேண்டும்",
        "aagum": "ஆகும்", "naal": "நாள்", "naatkal": "நாட்கள்", "ulla": "உள்ள",
        "thiruppi": "திருப்பி", "thirumba": "திரும்ப", "epdi": "எப்படி", "yennaku": "எனக்கு",
    }
    return re.sub(r"[A-Za-z]+", lambda m: mapping.get(m.group(0).lower(), m.group(0)), text)

def sanitize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()
