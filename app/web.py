from __future__ import annotations

import secrets
import logging
import os
import threading
import uuid
import json
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_from_directory, session

from .config import MAX_UPLOAD_BYTES, SECRET_KEY, DATA_DIR
from .ingest import ingest_file, list_documents
from .models import Generator
from .router import build_context, retrieval_decision, route_query

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config.update(SECRET_KEY=SECRET_KEY, MAX_CONTENT_LENGTH=MAX_UPLOAD_BYTES)
app.logger.setLevel(logging.INFO)
generator = Generator()
STYLE_VERSION = "20261020-1"
LOG_REQUESTS = os.getenv("LOG_REQUESTS", "0") == "1"
LOG_RESPONSE_BODY = os.getenv("LOG_RESPONSE_BODY", "0") == "1"
UPLOAD_JOBS: dict[str, dict] = {}
UPLOAD_JOBS_LOCK = threading.Lock()
CONVERSATIONS_FILE = DATA_DIR / "conversations.json"
CONVERSATIONS_LOCK = threading.Lock()
MAX_HISTORY_MESSAGES = 20

@app.before_request
def log_incoming_request():
    if not LOG_REQUESTS:
        return
    details = ""
    if request.is_json:
        payload = request.get_json(silent=True) or {}
        if "query" in payload:
            details = f" query={payload['query']!r}"
    elif request.files:
        details = f" files={[file.filename for file in request.files.getlist('files')]!r}"
    app.logger.info("IN  %s %s%s", request.method, request.path, details)

@app.after_request
def log_outgoing_response(response):
    if LOG_REQUESTS:
        body = ""
        if LOG_RESPONSE_BODY and not response.direct_passthrough:
            body = f" body={response.get_data(as_text=True)[:2000]!r}"
        elif LOG_RESPONSE_BODY and response.direct_passthrough:
            body = " body=<streamed response>"
        app.logger.info("OUT %s %s status=%s%s", request.method, request.path, response.status_code, body)
    return response

def csrf_token() -> str:
    session.setdefault("csrf_token", secrets.token_urlsafe(24))
    return session["csrf_token"]

def check_csrf() -> bool:
    return secrets.compare_digest(request.form.get("csrf_token", request.headers.get("X-CSRF-Token", "")), session.get("csrf_token", ""))

def _update_upload_job(job_id: str, **updates) -> None:
    with UPLOAD_JOBS_LOCK:
        UPLOAD_JOBS[job_id].update(updates)

def _run_upload_job(job_id: str, files: list[tuple[Path, str]]) -> None:
    indexed, errors = [], []
    total = len(files)
    for index, (path, original_name) in enumerate(files):
        def progress(stage: str, percent: int, index: int = index) -> None:
            overall = int(((index + (percent / 100)) / total) * 100)
            _update_upload_job(job_id, progress=overall, stage=f"{stage} · file {index + 1} of {total}")

        try:
            indexed.append(ingest_file(path, original_name, progress_callback=progress))
        except Exception as exc:
            errors.append({"filename": original_name, "error": str(exc)})
        finally:
            path.unlink(missing_ok=True)
    _update_upload_job(job_id, progress=100, stage="Completed", status="complete", indexed=indexed, errors=errors)

def _load_conversations() -> dict:
    if not CONVERSATIONS_FILE.exists():
        return {}
    try:
        return json.loads(CONVERSATIONS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}

def _save_conversations(conversations: dict) -> None:
    temporary = CONVERSATIONS_FILE.with_suffix(".tmp")
    temporary.write_text(json.dumps(conversations, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(CONVERSATIONS_FILE)

def _conversation(conversation_id: str) -> dict:
    conversations = _load_conversations()
    conversation = conversations.setdefault(conversation_id, {"conversation_id": conversation_id, "messages": [], "updated_at": None})
    return conversation

def _append_messages(conversation_id: str, messages: list[dict]) -> dict:
    with CONVERSATIONS_LOCK:
        conversations = _load_conversations()
        conversation = conversations.setdefault(conversation_id, {"conversation_id": conversation_id, "messages": [], "updated_at": None})
        conversation["messages"].extend(messages)
        conversation["messages"] = conversation["messages"][-MAX_HISTORY_MESSAGES:]
        conversation["updated_at"] = datetime.now(timezone.utc).isoformat()
        _save_conversations(conversations)
        return conversation

@app.context_processor
def inject_csrf():
    return {"csrf_token": csrf_token(), "style_version": STYLE_VERSION}

@app.get("/")
def upload_page():
    return render_template("upload.html", documents=list_documents())

@app.get("/chat")
def chat_page():
    return render_template("chat.html")

@app.get("/assets/style.css")
def style_asset():
    response = send_from_directory(app.static_folder, "style.css", max_age=0)
    response.headers["Cache-Control"] = "no-store, max-age=0"
    return response

@app.get("/api/documents")
def documents():
    return jsonify({"documents": list_documents()})

@app.get("/api/conversations/<conversation_id>")
def get_conversation(conversation_id: str):
    if not conversation_id or len(conversation_id) > 100:
        return jsonify({"error": "Invalid conversation ID"}), 400
    return jsonify(_conversation(conversation_id))

@app.post("/api/upload")
def upload():
    if not check_csrf():
        return jsonify({"error": "Invalid CSRF token"}), 403
    files = request.files.getlist("files")
    if not files:
        return jsonify({"error": "Select at least one file"}), 400
    staged_files = []
    for uploaded in files:
        if not uploaded.filename:
            continue
        temp = Path(app.instance_path) / "uploads"
        temp.mkdir(parents=True, exist_ok=True)
        path = temp / secrets.token_hex(12)
        uploaded.save(path)
        staged_files.append((path, uploaded.filename))
    if not staged_files:
        return jsonify({"error": "Select at least one file"}), 400
    job_id = uuid.uuid4().hex
    with UPLOAD_JOBS_LOCK:
        UPLOAD_JOBS[job_id] = {"job_id": job_id, "status": "running", "progress": 0, "stage": "Starting", "indexed": [], "errors": []}
    threading.Thread(target=_run_upload_job, args=(job_id, staged_files), daemon=True).start()
    return jsonify({"job_id": job_id}), 202

@app.get("/api/upload/status/<job_id>")
def upload_status(job_id: str):
    with UPLOAD_JOBS_LOCK:
        job = UPLOAD_JOBS.get(job_id)
    if not job:
        return jsonify({"error": "Upload job not found"}), 404
    return jsonify(job)

@app.post("/api/chat")
def chat():
    payload = request.get_json(silent=True) or {}
    query = str(payload.get("query", "")).strip()
    if not query:
        return jsonify({"error": "Query cannot be empty"}), 400
    conversation_id = str(payload.get("conversation_id", "")).strip() or uuid.uuid4().hex
    with CONVERSATIONS_LOCK:
        conversation = _conversation(conversation_id)
    history = [message for message in conversation.get("messages", []) if message.get("role") in ("user", "assistant")][-MAX_HISTORY_MESSAGES:]
    try:
        decision = retrieval_decision(query, history)
        if decision["retrieve"]:
            retrieval_query = "\n".join(f"{message['role']}: {message['content']}" for message in history[-6:] + [{"role": "user", "content": query}])
            routed = route_query(query, retrieval_query=retrieval_query)
        else:
            routed = {"query": query, "cmi": 0.0, "matrix_language": "en", "views": [], "results": []}
        context = build_context(routed["results"])
        answer = generator.answer(query, context, routed["matrix_language"], routed["cmi"], history=history, citations=routed["results"])
        citations = [{"filename": result["filename"], "chunk_id": result["chunk_id"], "score": result.get("score")} for result in routed["results"]]
        if citations:
            citation_text = "Sources: " + ", ".join(f"[{citation['filename']} · chunk {citation['chunk_id']}]" for citation in citations)
            if "Sources:" not in answer:
                answer = f"{answer.rstrip()}\n\n{citation_text}"
        _append_messages(conversation_id, [{"role": "user", "content": query}, {"role": "assistant", "content": answer, "citations": citations}])
        return jsonify({**routed, "answer": answer, "conversation_id": conversation_id, "history": _conversation(conversation_id)["messages"], "citations": citations, "retrieval": decision})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

@app.get("/health")
def health():
    return jsonify({"ok": True, "documents": len(list_documents())})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
