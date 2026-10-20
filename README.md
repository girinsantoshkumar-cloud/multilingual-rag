# Multilingual Code-Switching RAG

An end-to-end multilingual code-switching Retrieval-Augmented Generation chatbot with Hindi-English and Tamil-English support. It provides a document upload page, persistent local vector retrieval, CMI-based query routing, transliteration-aware multi-view retrieval, grounded answer generation, CLI commands, and evaluation metrics.

## Supported code-switching pairs

The current language-aware baseline supports:

- **Hindi-English:** Devanagari and common Roman Hindi queries such as `mera refund kab aayega?`.
- **Tamil-English:** Tamil script and common Roman Tamil queries such as `என் refund எப்போது வரும்?` or `enakku refund eppo varum?`.

Documents and multilingual embeddings remain language-independent. Other languages can still use the general retrieval path, but they do not yet have pair-specific CMI or transliteration rules.

## Fastest Linux setup

The repository includes a self-contained launcher for Ubuntu/Debian and other Linux distributions with Python 3.10+:

```bash
git clone https://github.com/kamalesh-codes/multilingual-rag.git
cd multilingual-rag
chmod +x run_local.sh
./run_local.sh
```

`run_local.sh` will:

1. Verify Python and virtual-environment support.
2. Create `.venv` if it does not exist.
3. Install or update all dependencies from `requirements.txt`.
4. Run the test suite.
5. Start the Flask server.

Open `http://127.0.0.1:5000` in a browser. Use the Upload page to index PDF, DOCX, or TXT files, then open Chat to query them.

For a server without a browser or for a quick restart after dependencies are installed:

```bash
SKIP_TESTS=1 ./run_local.sh
```

To bind to another interface or port:

```bash
HOST=0.0.0.0 PORT=8000 ./run_local.sh
```

If Debian/Ubuntu reports that `venv` is unavailable, install the system package once:

```bash
sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-pip
```

## Manual setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
python -m pytest -q
python -m app.web
```

## CLI commands

Ingest one document or a directory:

```bash
.venv/bin/python -m app.ingest --input path/to/document.pdf
.venv/bin/python -m app.ingest --input data/raw_docs/
```

Ask a question without the browser:

```bash
.venv/bin/python -m app.chat --query "mera refund kab tak aayega?"
```

Run the evaluation fixture and write CSV metrics:

```bash
.venv/bin/python evaluate.py \
  --testset tests/fixtures/sample_dataset.json \
  --output results/metrics.csv
```

## Ollama LLM configuration

The application uses **Ollama**, not a proprietary hosted LLM API, for answer generation. No API key is required. The default model is:

```text
qwen2.5:14b
```

Install Ollama on the Linux host, start its service, and pull the model:

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama serve
ollama pull qwen2.5:14b
```

For the native Linux launcher, the app expects Ollama at this host endpoint:

```text
OLLAMA_BASE_URL=http://127.0.0.1:11434
```

That is the default, so after `ollama serve` and `ollama pull qwen2.5:14b`, start the app normally:

```bash
./run_local.sh
```

To select another model or endpoint:

```bash
export OLLAMA_MODEL="qwen2.5:14b"
export OLLAMA_BASE_URL="http://127.0.0.1:11434"
./run_local.sh
```

The application calls Ollama's native chat endpoint:

```text
POST ${OLLAMA_BASE_URL}/api/chat
```

For Docker Compose, Ollama still runs on the Linux host and the container uses:

```text
OLLAMA_BASE_URL=http://host.docker.internal:11434
```

The Compose file adds the Linux `host-gateway` mapping automatically. Start Ollama and pull the model on the host first, then run:

```bash
ollama serve
ollama pull qwen2.5:14b
DOCKER_UID="$(id -u)" DOCKER_GID="$(id -g)" docker compose up --build
```

If Ollama is unavailable, the app uses its grounded extractive fallback instead of failing. `OLLAMA_TIMEOUT` controls the request timeout in seconds.

Useful configuration variables include:

| Variable | Default | Purpose |
|---|---:|---|
| `HOST` | `127.0.0.1` | Flask bind address |
| `PORT` | `5000` | Flask port |
| `MAX_UPLOAD_BYTES` | `26214400` | Maximum request size |
| `TOP_K` | `5` | Retrieved chunks |
| `CMI_THRESHOLD` | `0.20` | Mixed-query routing threshold |
| `EMBEDDING_MODEL` | `intfloat/multilingual-e5-large` | Embedding model |
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` native / `http://host.docker.internal:11434` Compose | Ollama host endpoint |
| `OLLAMA_MODEL` | `qwen2.5:14b` | Ollama generation model |
| `OLLAMA_TIMEOUT` | `120` | Ollama request timeout in seconds |
| `SKIP_TESTS` | `0` | Set to `1` to skip startup tests |

The first run may download the multilingual E5 embedding model. E5 receives `passage:` prefixes during indexing and `query:` prefixes during retrieval. If the model cannot be downloaded, the app automatically uses a deterministic hashing embedder so the application and tests remain runnable offline.

The higher-quality defaults require more memory than the original lightweight setup. `qwen2.5:14b` is an Ollama quantized model, but it still needs substantially more VRAM/RAM than `qwen2.5:7b`. If the Kaggle GPU cannot load both models comfortably, use `OLLAMA_MODEL=qwen2.5:7b` or set `EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`.

After changing `EMBEDDING_MODEL`, re-ingest your documents so the persisted vectors are created by the same model used for query embeddings:

```bash
.venv/bin/python -m app.ingest --input data/raw_docs/
```

## Architecture

- `app/ingest.py`: secure file handling, PDF/DOCX/TXT extraction, chunking, embeddings, and idempotent indexing.
- `app/router.py`: CMI detection, matrix-language routing, transliteration/native-script views, retrieval fan-out, and result merging.
- `app/models.py`: optional Sentence Transformer embeddings and Ollama generation with an offline fallback.
- `app/web.py`: Flask upload, document status, chat, and health endpoints.
- `app/templates/` and `app/static/`: accessible white-and-blue web UI.
- `evaluate.py`: retrieval, grounding, language-consistency, CMI, and transliteration metrics.
- `data/raw_docs/`: uploaded source documents.
- `data/chunks/`: extracted chunk files.
- `data/vector_db/`: persistent local vector store.

## Running in the background on Linux

For a simple session-owned background process:

```bash
nohup env HOST=127.0.0.1 PORT=5000 SKIP_TESTS=1 ./run_local.sh > rag.log 2>&1 &
echo $! > rag.pid
```

Stop it later with:

```bash
kill "$(cat rag.pid)"
```

For production, run behind a reverse proxy with HTTPS and a process manager such as systemd or supervisord. The development Flask server is intentionally not a production WSGI server.

## Security notes

Uploads are size-limited, extension/signature checked, path-sanitized, stored under `data/raw_docs`, and not served directly. Browser upload POSTs require a session CSRF token. For production, set a strong `FLASK_SECRET_KEY`, add authentication, antivirus scanning, rate limiting, HTTPS, and a production vector database.

## Tests

```bash
.venv/bin/python -m pytest -q
```

## Docker deployment

Docker Compose is the easiest Linux deployment path. Install Docker Engine and the Compose plugin, then run:

```bash
git clone https://github.com/kamalesh-codes/multilingual-rag.git
cd multilingual-rag
docker compose up --build
```

The service will be available at `http://127.0.0.1:5000`. The first image build installs the Python dependencies; the first request that uses embeddings may also download the configured multilingual embedding model.

Run it in the background:

```bash
docker compose up --build -d
docker compose ps
docker compose logs -f multilingual-rag
```

Stop the service without deleting uploaded documents:

```bash
docker compose down
```

Uploaded documents, chunks, vector data, and evaluation results persist in the repository's `data/` and `results/` directories through bind mounts. On Linux, Compose defaults to UID/GID `1000:1000`; if your host user uses another ID, set it before starting:

```bash
DOCKER_UID="$(id -u)" DOCKER_GID="$(id -g)" docker compose up --build -d
```

Set a real secret before exposing the service beyond localhost:

```bash
export FLASK_SECRET_KEY="$(openssl rand -hex 32)"
export PORT=8000
docker compose up --build -d
```

The Compose service has an HTTP health check at `/health` and restarts automatically unless stopped. To rebuild after changing dependencies or source code:

```bash
docker compose build --no-cache
docker compose up -d
```

### Docker without Compose

If the Compose plugin is unavailable, the same image can be run directly:

```bash
docker build -t multilingual-rag:local .
docker run --rm -it \
  -p 5000:5000 \
  -e FLASK_SECRET_KEY="change-this-in-production" \
  -v "$(pwd)/data:/app/data" \
  -v "$(pwd)/results:/app/results" \
  multilingual-rag:local
```

If the container cannot write to the bind-mounted directories, use the host UID/GID with Compose or prepare the directories with matching ownership:

```bash
mkdir -p data/raw_docs data/chunks data/vector_db results
sudo chown -R "$(id -u):$(id -g)" data results
```
