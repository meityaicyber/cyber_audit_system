"""Integration tests for PostgreSQL pgvector storage and chunk retrieval."""

import asyncio
import os
import uuid
import pytest
asyncpg = pytest.importorskip("asyncpg")
import numpy as np

DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:supersecretpassword@localhost:5432/cyber_audit"
).replace("postgresql+asyncpg://", "postgresql://")

try:
    asyncio.run(asyncio.wait_for(asyncpg.connect(DB_URL), 3)).terminate()
except Exception:
    pytest.skip("PostgreSQL not reachable", allow_module_level=True)


def test_postgres_connection():
    """Verify direct connection to PostgreSQL cyber_audit database."""
    async def _test():
        conn = await asyncpg.connect(DB_URL)
        try:
            val = await conn.fetchval("SELECT 1;")
            assert val == 1
        finally:
            await conn.close()
    asyncio.run(_test())


def test_report_chunks_table_schema():
    """Verify that report_chunks table exists and carries expected pgvector columns."""
    async def _test():
        conn = await asyncpg.connect(DB_URL)
        try:
            # Check table existence
            table_exists = await conn.fetchval(
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'report_chunks');"
            )
            assert table_exists is True, "Table 'report_chunks' must exist in PostgreSQL"

            # Check column types
            cols = await conn.fetch(
                "SELECT column_name, data_type, udt_name FROM information_schema.columns WHERE table_name = 'report_chunks';"
            )
            col_map = {r["column_name"]: r["udt_name"] for r in cols}
            assert "chunk_id" in col_map
            assert "report_id" in col_map
            assert "section_id" in col_map
            assert "chunk" in col_map
            assert "embedding" in col_map
            assert col_map["embedding"] == "vector", f"embedding column must have udt_name 'vector', got {col_map['embedding']}"

            # Check HNSW index
            index_exists = await conn.fetchval(
                "SELECT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'ix_report_chunks_embedding');"
            )
            assert index_exists is True, "HNSW index 'ix_report_chunks_embedding' must exist"
        finally:
            await conn.close()
    asyncio.run(_test())


def test_insert_and_pgvector_cosine_search():
    """Verify inserting a 1024-dim vector and querying via pgvector cosine distance operator (<=>)."""
    async def _test():
        conn = await asyncpg.connect(DB_URL)
        try:
            # Fetch an existing report_id to satisfy foreign key
            sample_report_id = await conn.fetchval("SELECT report_id FROM reports LIMIT 1;")
            if not sample_report_id:
                pytest.skip("No reports available in database to attach test chunk")

            test_chunk_id = uuid.uuid4()
            vec1 = np.random.randn(1024).astype("float32")
            vec1 /= np.linalg.norm(vec1)
            vec1_str = "[" + ",".join(f"{x:.6f}" for x in vec1) + "]"

            # Insert test chunk
            await conn.execute(
                """
                INSERT INTO report_chunks (
                    chunk_id, report_id, section_id, chunk, embedding, context_prefix, chunk_index
                ) VALUES ($1, $2, $3, $4, $5, $6, $7);
                """,
                test_chunk_id,
                sample_report_id,
                "test_section",
                "Test cybersecurity finding: SQL injection detected on user login endpoint.",
                vec1_str,
                "Finding TEST-01",
                9999,
            )

            # Query using the exact same vector -> distance should be ~0.0
            row = await conn.fetchrow(
                """
                SELECT chunk_id, (embedding <=> ($1)::vector) AS distance
                FROM report_chunks
                WHERE chunk_id = $2;
                """,
                vec1_str,
                test_chunk_id,
            )
            assert row is not None
            distance = float(row["distance"])
            assert distance < 1e-4, f"Cosine distance to identical vector should be ~0, got {distance}"

            # Cleanup test chunk
            await conn.execute("DELETE FROM report_chunks WHERE chunk_id = $1;", test_chunk_id)

        finally:
            await conn.close()
    asyncio.run(_test())
