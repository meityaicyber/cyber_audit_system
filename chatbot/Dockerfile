FROM python:3.12-slim

WORKDIR /app

# Install system utilities
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir pgvector httpx

# Copy source code and locally staged weights
COPY . .

EXPOSE 8077

ENV PYTHONUNBUFFERED=1
ENV HOST=0.0.0.0
ENV PORT=8077

# Start ragengine API server
CMD ["python", "start_rag.py", "--host", "0.0.0.0", "--port", "8077"]

