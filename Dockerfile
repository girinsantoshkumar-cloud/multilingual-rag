FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HUB_DISABLE_TELEMETRY=1

WORKDIR /app

RUN groupadd --system --gid 1000 appuser \
    && useradd --system --uid 1000 --gid 1000 --create-home appuser

COPY requirements.txt ./
RUN python -m pip install --upgrade pip setuptools wheel \
    && pip install -r requirements.txt

COPY . .
RUN mkdir -p data/raw_docs data/chunks data/vector_db results \
    && chown -R appuser:appuser /app

USER appuser
EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/health', timeout=3)"

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "4", "--timeout", "120", "app.web:app"]
