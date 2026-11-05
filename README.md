# Unified Cybersecurity Audit & RAG Engine

Monorepo containing the end-to-end Air-Gapped Cybersecurity Audit Document Standardization and RAG system for CERT-In testing.

## System Architecture

```text
cyber-audit-system/
├── backend/                  # FastAPI Backend API, PostgreSQL pgvector models, multi-threaded worker, Docker Compose
│   ├── ai_pipeline/          # AI pipeline extraction service
│   ├── backend/              # Core API endpoints (/reports, /chunks, /pipeline)
│   └── frontend/             # React Audit Management Web Application
│
├── chatbot/                  # Cybersecurity RAG Service & Retrieval Engine
│   ├── ragaudit/             # RAG engine (dense retrieval, hybrid search, citation tracking)
│   ├── start_rag.py          # Unified one-click RAG launcher (migrations + sync + server)
│   ├── evaluate_rag.py       # Automated CERT-In benchmark test suite (sub-10ms retrieval)
│   └── var/catalog.sqlite3   # Chat catalogue, built by start_rag.py (vectors: PostgreSQL schema `rag`)
│
└── document-standardization/ # Document Standardization Pipeline Core
```

## Quick Start

### 1. Boot the Entire Docker Stack
```bash
cd backend
docker compose up -d
```

### 2. Run the Evaluation Suite
```bash
python evaluate_rag.py
# or double-click evaluate_rag.bat
```

### 3. Launch the RAG Service & Web Console
```bash
python start_rag.py
# Open in browser: http://localhost:8077
```

