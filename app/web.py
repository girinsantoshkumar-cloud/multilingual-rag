from __future__ import annotations

import secrets
from pathlib import Path

from flask import Flask, jsonify, render_template, request, session

from .config import MAX_UPLOAD_BYTES, SECRET_KEY
from .ingest import ingest_file, list_documents
from .models import Generator
from .router import build_context, route_query

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config.update(SECRET_KEY=SECRET_KEY, MAX_CONTENT_LENGTH=MAX_UPLOAD_BYTES)
generator = Generator()

def csrf_token() -> str:
    session.setdefault("csrf_token", secrets.token_urlsafe(24))
    return session["csrf_token"]

def check_csrf() -> bool:
    return secrets.compare_digest(request.form.get("csrf_token", request.headers.get("X-CSRF-Token", "")), session.get("csrf_token", ""))

@app.context_processor
def inject_csrf():
    return {"csrf_token": csrf_token()}

@app.get("/")
def upload_page():
    return render_template("upload.html", documents=list_documents())

@app.get("/chat")
def chat_page():
    return render_template("chat.html")

@app.get("/api/documents")
def documents():
    return jsonify({"documents": list_documents()})

@app.post("/api/upload")
def upload():
    if not check_csrf():
        return jsonify({"error": "Invalid CSRF token"}), 403
    files = request.files.getlist("files")
    if not files:
        return jsonify({"error": "Select at least one file"}), 400
    results, errors = [], []
    for uploaded in files:
        if not uploaded.filename:
            continue
        temp = Path(app.instance_path) / "uploads"
        temp.mkdir(parents=True, exist_ok=True)
        path = temp / secrets.token_hex(12)
        uploaded.save(path)
        try:
            results.append(ingest_file(path, uploaded.filename))
        except Exception as exc:
            errors.append({"filename": uploaded.filename, "error": str(exc)})
        finally:
            path.unlink(missing_ok=True)
    status = 207 if errors and results else (400 if errors else 200)
    return jsonify({"indexed": results, "errors": errors}), status

@app.post("/api/chat")
def chat():
    payload = request.get_json(silent=True) or {}
    query = str(payload.get("query", "")).strip()
    if not query:
        return jsonify({"error": "Query cannot be empty"}), 400
    try:
        routed = route_query(query)
        context = build_context(routed["results"])
        answer = generator.answer(query, context, routed["matrix_language"], routed["cmi"])
        return jsonify({**routed, "answer": answer})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

@app.get("/health")
def health():
    return jsonify({"ok": True, "documents": len(list_documents())})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
