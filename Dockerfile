FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app/src \
    LLM_PROVIDER=none

WORKDIR /app

# Unprivileged user: the agent only reads scan files and writes to /app/output.
RUN groupadd --system --gid 10001 recon \
    && useradd --system --uid 10001 --gid recon --no-create-home --shell /usr/sbin/nologin recon

COPY requirements.txt .
RUN pip install -r requirements.txt

# Code, contract, and sample data are owned by root and read-only for the agent.
COPY src/ src/
COPY schemas/ schemas/
COPY data/ data/
RUN mkdir -p /app/output && chown recon:recon /app/output

USER recon

ENTRYPOINT ["python", "-m", "recon_agent"]
CMD ["--input", "data/scans/sample_scan_01.json"]
