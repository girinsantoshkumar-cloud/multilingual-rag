# Multilingual Code-Switching RAG

A multilingual code-switching Retrieval-Augmented Generation chatbot with Hindi-English and Tamil-English support. The primary deployment target is a Kaggle GPU notebook running the embedding model, Ollama, and Flask locally, with one ngrok tunnel exposing the Flask web interface.

## Models

- **Embeddings:** `intfloat/multilingual-e5-large`
- **LLM:** Ollama `qwen2.5:14b`
- **Fallbacks:** deterministic hashing embeddings and grounded extractive answers when a model is unavailable

E5 requires `passage:` prefixes for document chunks and `query:` prefixes for user queries. The application applies those prefixes automatically when the E5 model is loaded.

If the Kaggle GPU cannot comfortably run both high-quality models, use:

```bash
OLLAMA_MODEL=qwen2.5:7b
```

or:

```bash
EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
```

## Primary setup: Kaggle GPU + local Ollama + one ngrok tunnel

Kaggle sessions are ephemeral. Install and start everything directly in the active Kaggle Python environment; do not create a virtual environment. Keep the notebook session running while the app is in use.

### 1. Enable Kaggle Internet and GPU

In the Kaggle notebook settings, enable **Internet** and select a **GPU accelerator**. Verify the GPU:

```python
!nvidia-smi

import torch
print("CUDA available:", torch.cuda.is_available())
print("GPU:", torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU")
```

### 2. Clone and install directly into Kaggle Python

```python
!git clone https://github.com/kamalesh-codes/multilingual-rag.git /kaggle/working/multilingual-rag
%cd /kaggle/working/multilingual-rag
!python -m pip install -q --upgrade pip wrapt
!python -m pip install -q -r requirements.txt pyngrok requests
!python -m compileall -q app evaluate.py
```

Do not run `python -m venv` in Kaggle. If a previous attempt created a broken `.venv`, remove it or simply use the system `python` commands above:

```python
!rm -rf /kaggle/working/multilingual-rag/.venv
```

### 3. Install and start Ollama inside Kaggle

```python
!curl -fsSL https://ollama.com/install.sh | sh
```

Start Ollama as a background process:

```python
import subprocess
import time

ollama_process = subprocess.Popen(
    ["ollama", "serve"],
    stdout=open("/kaggle/working/ollama.log", "w"),
    stderr=subprocess.STDOUT,
)
time.sleep(5)
print("Ollama PID:", ollama_process.pid)
```

Pull the higher-quality model:

```python
!ollama pull qwen2.5:14b
!ollama list
```

If the 14B model exceeds the available Kaggle GPU memory, use:

```python
!ollama pull qwen2.5:7b
```

and configure `OLLAMA_MODEL=qwen2.5:7b` below.

Verify Ollama locally:

```python
import requests
print(requests.get("http://127.0.0.1:11434/api/tags", timeout=30).json())
```

### 4. Configure and start the Flask app locally

Because Ollama runs inside the same Kaggle session, the expected endpoint is:

```text
http://127.0.0.1:11434
```

Start Flask on all interfaces so ngrok can reach it:

```python
import os
import subprocess
import sys

repo = "/kaggle/working/multilingual-rag"
env = os.environ.copy()
env.update({
    "HOST": "0.0.0.0",
    "PORT": "5000",
    "OLLAMA_BASE_URL": "http://127.0.0.1:11434",
    "OLLAMA_MODEL": "qwen2.5:14b",
    "EMBEDDING_MODEL": "intfloat/multilingual-e5-large",
})

app_log = open("/kaggle/working/rag-app.log", "w")
app_process = subprocess.Popen(
    [sys.executable, "-m", "app.web"],
    cwd=repo,
    env=env,
    stdout=app_log,
    stderr=subprocess.STDOUT,
)
print("RAG PID:", app_process.pid)
```

Check the local health endpoint:

```python
import requests
print(requests.get("http://127.0.0.1:5000/health", timeout=30).json())
```

Expected:

```text
{'ok': True, 'documents': 0}
```

### 5. Expose only Flask through ngrok

Add an `NGROK_AUTHTOKEN` secret through Kaggle **Add-ons → Secrets**, then run:

```python
from kaggle_secrets import UserSecretsClient
from pyngrok import ngrok

secrets = UserSecretsClient()
ngrok_token = secrets.get_secret("NGROK_AUTHTOKEN")
ngrok.set_auth_token(ngrok_token)

tunnel = ngrok.connect(5000, "http")
print("Public app URL:", tunnel.public_url)
print("Chat URL:", tunnel.public_url + "/chat")
```

Only the Flask application needs an ngrok tunnel. Ollama stays private inside Kaggle at `http://127.0.0.1:11434`.

The resulting network layout is:

```text
Browser -> ngrok -> Kaggle Flask app -> local Ollama -> Kaggle GPU
```

### 6. Upload documents and use chat

Open the printed ngrok URL, upload PDF/DOCX/TXT documents, and use the Chat page. To ingest documents from a notebook cell instead:

```python
!python -m app.ingest --input data/raw_docs/
```

After changing the embedding model, re-index documents:

```python
!python -m app.ingest --input data/raw_docs/
```

## One-command direct Linux launcher

For a normal Linux host, the launcher uses the active system Python directly. It does not create a virtual environment or use Docker:

```bash
chmod +x run_local.sh
./run_local.sh
```

The script installs `requirements.txt`, runs tests, and starts Flask. For a faster restart after dependencies are installed:

```bash
SKIP_INSTALL=1 SKIP_TESTS=1 ./run_local.sh
```

Set the Ollama model and endpoint if needed:

```bash
OLLAMA_BASE_URL=http://127.0.0.1:11434 \
OLLAMA_MODEL=qwen2.5:14b \
HOST=0.0.0.0 PORT=5000 \
./run_local.sh
```

## CLI and evaluation

```bash
python -m app.chat --query "enakku refund eppo varum?"
python -m app.ingest --input data/raw_docs/
python evaluate.py --testset tests/fixtures/sample_dataset.json --output results/metrics.csv
python -m pytest -q
```

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `EMBEDDING_MODEL` | `intfloat/multilingual-e5-large` | Document/query embedding model |
| `OLLAMA_MODEL` | `qwen2.5:14b` | Local Ollama generation model |
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Ollama endpoint inside Kaggle/Linux host |
| `OLLAMA_TIMEOUT` | `120` | Ollama request timeout in seconds |
| `HOST` | `127.0.0.1` | Flask bind address; use `0.0.0.0` for ngrok |
| `PORT` | `5000` | Flask port |
| `TOP_K` | `5` | Retrieved chunks |
| `CMI_THRESHOLD` | `0.20` | Mixed-query routing threshold |
| `MAX_UPLOAD_BYTES` | `26214400` | Maximum upload request size |

## Supported code-switching pairs

- **Hindi-English:** Devanagari and common Roman Hindi, such as `mera refund kab aayega?`.
- **Tamil-English:** Tamil script and common Roman Tamil, such as `என் refund எப்போது வரும்?` or `enakku refund eppo varum?`.

Other languages can use the general multilingual embedding path, but do not yet have pair-specific CMI and transliteration rules.

## Architecture

- `app/ingest.py`: secure document handling, extraction, chunking, E5 passage embeddings, and persistence.
- `app/router.py`: CMI detection, language routing, transliteration views, E5 query embeddings, retrieval fan-out, and result merging.
- `app/models.py`: Sentence Transformer embeddings and Ollama generation with safe fallbacks.
- `app/web.py`: Flask upload, document status, chat, and health endpoints.
- `app/templates/` and `app/static/`: accessible white-and-blue web UI.
- `evaluate.py`: retrieval, grounding, language consistency, CMI, and transliteration metrics.

## Kaggle troubleshooting

### `No module named pip` or `wrapt` sitecustomize errors

Use Kaggle's system Python directly:

```python
!python -m pip install -q --upgrade pip wrapt
!python -m pip install -q -r requirements.txt pyngrok requests
```

Do not use the broken `.venv` created by an earlier run.

### Ollama connection failure

Check the Ollama process and endpoint:

```python
!tail -100 /kaggle/working/ollama.log
!curl http://127.0.0.1:11434/api/tags
```

### App connection failure

```python
!tail -100 /kaggle/working/rag-app.log
!curl http://127.0.0.1:5000/health
```

### Kaggle session stops

Kaggle sessions are not persistent. The Flask process, Ollama process, model cache, uploaded documents, and ngrok tunnel stop when the session ends. Re-run the setup cells in a new session. Keep important documents and metrics in Kaggle Datasets or download them before the session expires.

### Security

The ngrok URL makes the app publicly reachable. The app has CSRF protection for uploads but no user authentication. Do not expose confidential documents without adding authentication or ngrok access controls.
