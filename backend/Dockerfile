FROM python:3.15-slim

# opencv needs these system libs even in "headless" mode for video decoding
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    ffmpeg \
    fonts-noto-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Build with --build-arg INSTALL_ML=false for a small image without the ML models (pixel-heuristic fallback).
ARG INSTALL_ML=true
# Content Credentials (C2PA) signature validation. Without it the app only detects that credentials exist and says "not validated".
ARG INSTALL_C2PA=true
COPY requirements.txt requirements-ml.txt requirements-c2pa.txt ./
RUN pip install --no-cache-dir -r requirements.txt && \
    if [ "$INSTALL_ML" = "true" ]; then pip install --no-cache-dir -r requirements.txt -r requirements-ml.txt; fi && \
    if [ "$INSTALL_C2PA" = "true" ]; then pip install --no-cache-dir -r requirements-c2pa.txt; fi

COPY . .

RUN mkdir -p /app/data/uploads

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
