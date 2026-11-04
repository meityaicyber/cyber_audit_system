FROM python:3.11-slim

WORKDIR /app

# Install system dependencies if required for ML packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY backend/ai_pipeline/requirements.txt ./req_api.txt
COPY document-standardization/requirements.txt ./req_ml.txt

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r req_api.txt -r req_ml.txt

# Copy application and ML code
COPY backend/ai_pipeline .
COPY document-standardization /document-standardization

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
