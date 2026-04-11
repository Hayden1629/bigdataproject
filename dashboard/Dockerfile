FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y curl --no-install-recommends && rm -rf /var/lib/apt/lists/*

COPY dashboard/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Application source
COPY dashboard/ ./dashboard/

# Pre-computed signal cache (avoids running precompute at container start)
COPY dashboard/cache/ ./dashboard/cache/

# FAERS parquet data (override via FAERS_PARQUET_DIR env var for cloud storage)
COPY data/parquet_recent/ ./data/parquet_recent/

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s \
    CMD curl --fail http://localhost:8501/_stcore/health || exit 1

CMD ["streamlit", "run", "dashboard/app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true"]
