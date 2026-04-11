FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y curl --no-install-recommends && rm -rf /var/lib/apt/lists/*

# Install Python dependencies (cached layer)
COPY claude_test/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY claude_test/ ./claude_test/

# Copy pre-computed signal cache (avoids running precompute at container start)
COPY claude_test/cache/ ./claude_test/cache/

# Copy FAERS parquet data
COPY data/parquet_recent/ ./data/parquet_recent/

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s \
    CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# Streamlit config lives in claude_test/.streamlit/config.toml
CMD ["streamlit", "run", "claude_test/app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true"]
