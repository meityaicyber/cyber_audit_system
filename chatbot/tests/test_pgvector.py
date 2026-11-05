"""PgVectorIndex against a real PostgreSQL. Set RAGAUDIT_TEST_PG_DSN to run.

Each test wipes the ``rag`` schema, so never point this at a live database.
"""

from __future__ import annotations

import json
import os

import numpy as np
import pytest
from conftest import make_app

from ragaudit.store.vectors import NumpyVectorIndex, drop_pg_index, open_index

DSN = os.environ.get("RAGAUDIT_TEST_PG_DSN", "")
pytestmark = pytest.mark.skipif(not DSN, reason="RAGAUDIT_TEST_PG_DSN not set")
DIM = 8


@pytest.fixture
def index(tmp_path):
    drop_pg_index(DSN)
    yield open_index(tmp_path, DIM, "pgvector", pg_dsn=DSN, fingerprint="model-a")
    drop_pg_index(DSN)


def _vectors(n, seed=0, dim=DIM):
    return np.random.default_rng(seed).normal(size=(n, dim)).astype("float32")


def test_search_matches_the_exact_index(index):
    ids = [f"c{i}" for i in range(50)]
    reports = [f"r{i % 5}" for i in range(50)]
    vectors = _vectors(50)
    index.add(ids, vectors, reports)
    exact = NumpyVectorIndex(DIM)
    exact.add(ids, vectors, reports)

    query = _vectors(1, seed=1)
    assert [i for i, _ in index.search(query, 5)] == [i for i, _ in exact.search(query, 5)]
    got = index.search(query, 5, allowed_report_ids=["r1", "r2"])
    want = exact.search(query, 5, allowed_report_ids=["r1", "r2"])
    assert [i for i, _ in got] == [i for i, _ in want]
    assert got[0][1] == pytest.approx(want[0][1], abs=1e-4)


def test_scope_is_a_prefilter_that_still_fills_top_k(index):
    """HNSW alone filters after the scan: a small report next to a large one
    would come back short or empty."""
    index.add([f"big{i}" for i in range(2000)], _vectors(2000), ["big"] * 2000)
    index.add([f"small{i}" for i in range(6)], -_vectors(6, seed=2), ["small"] * 6)
    hits = index.search(_vectors(1, seed=3), 6, allowed_report_ids=["small"])
    assert len(hits) == 6 and all(i.startswith("small") for i, _ in hits)
    assert index.search(_vectors(1), 6, allowed_report_ids=[]) == []


def test_unscoped_search_returns_more_than_the_default_ef_search(index):
    index.add([f"c{i}" for i in range(300)], _vectors(300), ["r"] * 300)
    assert len(index.search(_vectors(1, seed=1), 120)) == 120


def test_counts_remove_and_replace(index):
    index.add(["a", "b"], _vectors(2), ["r1", "r1"])
    index.add(["c"], _vectors(1), ["r2"])
    assert (len(index), index.vector_count("r1"), index.vector_count("none")) == (3, 2, 0)
    index.add(["a"], _vectors(1, seed=9), ["r1"])              # same chunk again: no duplicate
    assert len(index) == 3
    index.remove_report("r1")
    assert (len(index), index.vector_count("r1")) == (1, 0)


def test_other_embedding_setups_are_refused(index, tmp_path):
    index.add(["a"], _vectors(1), ["r"])
    with pytest.raises(RuntimeError, match="different models"):
        open_index(tmp_path, DIM, "pgvector", pg_dsn=DSN, fingerprint="model-b")
    with pytest.raises(RuntimeError, match="dimension"):
        open_index(tmp_path, DIM * 2, "pgvector", pg_dsn=DSN, fingerprint="model-a")


def test_drop_leaves_other_schemas_alone(index):
    import psycopg

    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS report_chunks_probe (id int)")
        drop_pg_index(DSN)
        assert conn.execute("SELECT to_regclass('public.report_chunks_probe')").fetchone()[0]
        assert conn.execute("SELECT to_regclass('rag.vectors')").fetchone()[0] is None
        conn.execute("DROP TABLE report_chunks_probe")


def test_full_ingest_and_chat_retrieval(tmp_path, corpus):
    drop_pg_index(DSN)
    app = make_app(tmp_path, retrieval={"backend": "pgvector", "pg_dsn": DSN})
    paths = sorted(corpus.glob("*.json"))
    first = app.build_ingest().ingest_paths(paths)
    assert first.summary()["indexed"] == 2 and len(app.index) > 0
    before = len(app.index)

    # A second run skips everything: vectors in Postgres count as present.
    second = app.build_ingest().ingest_paths(paths)
    assert second.summary()["indexed"] == 0 and len(app.index) == before

    hits = app.build_retriever().retrieve("broken access control token", report_ids=["SAMPLE-API-002"], top_k=5)
    assert hits and all(h.chunk.report_id == "SAMPLE-API-002" for h in hits)
    app.close()
    drop_pg_index(DSN)


def test_ingest_json_queues_and_waits(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from ragaudit.api import server

    drop_pg_index(DSN)
    app = make_app(tmp_path, retrieval={"backend": "pgvector", "pg_dsn": DSN})
    client = TestClient(server.create_app(app))
    queued = []
    monkeypatch.setattr(server, "_queue_ingest", queued.append)
    body = {"report_id": "ACME-1", "data": {"detailed_observations": [
        {"finding_id": "OBS-1", "title": "SQL injection", "severity": "High",
         "observation_description": "Input reaches a SQL query."}]}}

    assert client.post("/api/ingest-json", json=body).json()["status"] == "queued"
    assert queued and json.loads((queued[0] / "ACME-1.json").read_text(encoding="utf-8"))
    assert app.catalog.count_findings() == 0                    # nothing done in-process

    done = client.post("/api/ingest-json", json={**body, "wait": True}).json()
    assert done["outcomes"][0]["status"] == "indexed"
    app.close()
    drop_pg_index(DSN)


