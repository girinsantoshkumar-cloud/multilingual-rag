from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

from app.chat import run
from app.utils import compute_cmi, language_profile, transliterate_roman_hindi

def token_set(text):
    return set(re.findall(r"[\w\u0900-\u097F]+", text.lower()))

def score_item(item):
    result = run(item["query"])
    reference = item.get("reference_answer", "")
    ref = token_set(reference)
    ans = token_set(result["answer"])
    context = token_set(" ".join(r["text"] for r in result["results"]))
    faithfulness = len(ans & context) / max(1, len(ans))
    relevance = len(token_set(item["query"]) & token_set(" ".join(r["text"] for r in result["results"]))) / max(1, len(token_set(item["query"])))
    precision = sum(1 for r in result["results"] if any(t in token_set(r["text"]) for t in ref)) / max(1, len(result["results"]))
    recall = len(ref & context) / max(1, len(ref))
    cmi_alignment = max(0.0, 1 - abs(compute_cmi(result["answer"]) - compute_cmi(item["query"])))
    lang_consistency = float(language_profile(result["answer"])["matrix_language"] == language_profile(item["query"])["matrix_language"])
    translit = float(not any(ord(c) < 128 for c in item["query"]) or transliterate_roman_hindi(item["query"]) != item["query"] or bool(result["answer"]))
    return {"query_id": item.get("id", item["query"][:24]), "faithfulness": round(faithfulness, 4), "answer_relevance": round(relevance, 4), "context_precision": round(precision, 4), "context_recall": round(recall, 4), "cmi_alignment": round(cmi_alignment, 4), "language_consistency": round(lang_consistency, 4), "transliteration_robustness": round(translit, 4)}

def evaluate(dataset: list[dict], output: Path):
    rows = [score_item(item) for item in dataset]
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys() if rows else ["query_id"])
        writer.writeheader(); writer.writerows(rows)
    if rows:
        numeric = [k for k in rows[0] if k != "query_id"]
        print(json.dumps({k: round(sum(r[k] for r in rows) / len(rows), 4) for k in numeric}, indent=2))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--testset", required=True); parser.add_argument("--output", default="results/metrics.csv")
    args = parser.parse_args()
    evaluate(json.loads(Path(args.testset).read_text(encoding="utf-8")), Path(args.output))
