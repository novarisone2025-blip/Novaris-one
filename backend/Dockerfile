FROM python:3.12-slim AS dependencias

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


FROM python:3.12-slim AS producao

ENV PATH="/opt/venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    WEB_CONCURRENCY=1 \
    RUN_DATABASE_SETUP_ON_STARTUP=true

RUN groupadd --system novaris \
    && useradd --system --gid novaris --home /app novaris

WORKDIR /app
COPY --from=dependencias /opt/venv /opt/venv
COPY app ./app
COPY scripts ./scripts
COPY docker-entrypoint.sh /usr/local/bin/novaris-entrypoint
RUN chmod +x /usr/local/bin/novaris-entrypoint \
    && chown -R novaris:novaris /app

USER novaris
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:' + __import__('os').getenv('PORT', '8000') + '/health', timeout=4)"

ENTRYPOINT ["novaris-entrypoint"]
