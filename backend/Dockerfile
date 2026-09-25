# SatQuery backend (FastAPI) for Railway or any container host.
# CPU only: the VLM runs on the Hugging Face Inference Endpoint (model_mode=hf); ChangeFormer
# and the router's MiniLM run here on CPU.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    SATQUERY_DATA_DIR=/data \
    SATQUERY_DATABASE_PATH=/data/satquery.db \
    # Memory: few malloc arenas and two compute threads keep PyTorch's resident set small on
    # 1 GB hosts. Results are unchanged; only parallelism is limited.
    MALLOC_ARENA_MAX=2 \
    OMP_NUM_THREADS=2

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 libexpat1 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# CPU wheels for torch/torchvision first, from one index, so they match each other.
RUN pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu \
 && pip install -r requirements.txt

# Bake the router's sentence-transformer into the image so startup needs no download.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

COPY app ./app
COPY scripts ./scripts

EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
