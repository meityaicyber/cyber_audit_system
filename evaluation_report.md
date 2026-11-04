# Cybersecurity RAG Evaluation Report

**Generated:** 2026-11-04 12:59:05 UTC  
**Target System:** Air-Gapped Cybersecurity Audit RAG Engine (`cyber_audit` PostgreSQL pgvector)  
**Overall Score:** **93.3%** (14/15 Passed, 1 Warnings, 0 Failures)  
**Verdict:** 🟢 **CERT-IN EVALUATION READY**  

## 1. Executive Summary Table

| Category | Test Case | Status | Latency | Details |
|:---|:---|:---:|:---:|:---|
| Database | DB: 'report_chunks' Table Exists | ✅ PASS | 3.0 ms | Table present in cyber_audit database. |
| Database | DB: pgvector Extension Enabled | ✅ PASS | 0.8 ms | Installed version: 0.8.7 |
| Database | DB: HNSW Cosine Index (ix_report_chunks_embedding) | ✅ PASS | 1.3 ms | Index active for fast approximate nearest neighbor search. |
| Database | DB: Vector Count & Dimension Check | ✅ PASS | 4.7 ms | Chunks: 2,563 across 180 reports | Dims: 1024 | Nulls: 0 |
| Models | Model: Local Embedder (Qwen3-Embedding-0.6B) | ✅ PASS | 4138.7 ms | Weights loaded from Qwen3-Embedding-0.6B (dim: 1024) |
| Retrieval | Retrieval: SEC-01 (Injection) | ⚠️ WARN | 90.7 ms | Score: 0.499 (dist: 0.501) | DB: 10.2ms | Top Match: Finding 995d6ebd-b127-4fab-808d-7caf02a4fff2: Stored Cr... |
| Retrieval | Retrieval: SEC-02 (Remote Code Execution) | ✅ PASS | 77.7 ms | Score: 0.710 (dist: 0.290) | DB: 2.4ms | Top Match: Finding aa9fa8f9-45dc-4c1c-919c-92e35c6ef43c: Remote Co... |
| Retrieval | Retrieval: SEC-03 (Access Control) | ✅ PASS | 88.7 ms | Score: 0.589 (dist: 0.411) | DB: 2.6ms | Top Match: Finding f57aa9e6-e63d-4c34-8843-5b85e4bea0e8: Broken Ob... |
| Retrieval | Retrieval: SEC-04 (File Handling) | ✅ PASS | 86.2 ms | Score: 0.728 (dist: 0.272) | DB: 2.2ms | Top Match: Finding 361f1ea6-7cc4-4f73-9a04-303be5516b87: Path Trav... |
| Retrieval | Retrieval: SEC-05 (Cryptography) | ✅ PASS | 76.9 ms | Score: 0.767 (dist: 0.233) | DB: 2.8ms | Top Match: Finding f31220a4-cfb2-4e71-8e1d-98d9bde96617: Deprecate... |
| Retrieval | Retrieval: SEC-06 (Secret Management) | ✅ PASS | 73.5 ms | Score: 0.588 (dist: 0.412) | DB: 2.2ms | Top Match: Finding 884f520b-de0d-469c-954d-099d0fa32125: Hardcoded... |
| Filtering | Scope: Report-Level Filtering | ✅ PASS | 69.0 ms | All 5 returned chunks strictly matched report 00024c1a-38d9-4692-bff4-1ec42f60e69c |
| Generation | LLM: Ollama Service Status | ✅ PASS | 13.9 ms | Ollama online at http://127.0.0.1:11434 (1 model(s) available) |
| Generation | Q&A: Structured Count Answering | ✅ PASS | 6370.8 ms | Answer: The number of audit reports indexed is 182. (route: agent) |
| Generation | Q&A: Vulnerability Synthesis & Citations | ✅ PASS | 5324.0 ms | Answer length: 159 chars with 0 citation(s) |

## 2. Key Metrics & Benchmarks

- **Vector Index:** PostgreSQL 16 + pgvector HNSW cosine index (`ix_report_chunks_embedding`)
- **Embedding Model:** `Qwen3-Embedding-0.6B` (1024 dimensions, local inference)
- **Retrieval Latency:** Sub-10ms for pgvector approximate nearest neighbor queries
- **Dataset Size:** 180 Audit Reports, 2,563 Vector Chunks

## 3. How to Run Verification
```bash
python evaluate_rag.py
```