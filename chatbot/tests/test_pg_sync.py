"""Reports rebuilt from Postgres rows must behave like any other ingested report."""

from __future__ import annotations

import json

from conftest import make_app

from ragaudit.corpus_tools import postgres_report_document

DB_ID = "00024c1a-38d9-4692-bff4-1ec42f60e69c"
ROWS = [{
    "finding_id": "995d6ebd-b127-4fab-808d-7caf02a4fff2", "title": "SQL injection in login",
    "severity": "High", "status": "Open", "cwe": ["CWE-89"], "cve_id": ["CVE-2024-1234"],
    "affected_asset": ["https://portal.example/login"],
    "observation_description": "The login form concatenates input into a SQL query.",
    "recommendation": "Use parameterised queries.",
}]


def _ingest(app, tmp_path, doc, name=f"{DB_ID}.json"):
    path = tmp_path / "pg_sync" / name
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(doc), encoding="utf-8")
    return app.build_ingest().ingest_paths([path], force=True)


def test_id_follows_the_backend_pipeline_order():
    assert postgres_report_document({"report_meta": {"report_id": "R-1"}}, [], DB_ID)["report_meta"]["report_id"] == "R-1"
    assert postgres_report_document({"document_control": {"document_id": "D-1"}}, [], DB_ID)["report_meta"]["report_id"] == "D-1"
    assert postgres_report_document({"report_meta": {"report_id": "N/A"}}, [], DB_ID)["report_meta"]["report_id"] == DB_ID


def test_findings_in_the_json_keep_their_real_ids():
    data = {"detailed_observations": [{"finding_id": "OBS-01", "title": "x"}]}
    doc = postgres_report_document(data, ROWS, DB_ID)
    assert doc["detailed_observations"][0]["finding_id"] == "OBS-01"


def test_postgres_report_is_fully_searchable(tmp_path):
    app = make_app(tmp_path)
    doc = postgres_report_document({"metadata": {}}, ROWS, DB_ID, "portal.pdf")
    _ingest(app, tmp_path, doc)

    assert app.catalog.count_findings(cwe="CWE-89") == 1          # finding_identifiers filled
    assert app.catalog.count_findings(cve="CVE-2024-1234") == 1
    hits = app.build_retriever().retrieve("sql injection login", top_k=3)
    assert hits and all(h.chunk.field_path for h in hits)
    assert len(app.index) > 0                                     # vectors, not keywords alone
    app.close()


def test_second_ingest_of_a_report_replaces_it(tmp_path):
    app = make_app(tmp_path)
    doc = postgres_report_document({"metadata": {}}, ROWS, DB_ID)
    _ingest(app, tmp_path, doc)
    _ingest(app, tmp_path, doc)
    assert len(app.catalog.reports_overview()) == 1
    assert app.catalog.count_findings() == 1
    app.close()


def test_embed_endpoint_accepts_a_json_body(tmp_path):
    from fastapi.testclient import TestClient

    from ragaudit.api.server import create_app

    app = make_app(tmp_path)
    r = TestClient(create_app(app)).post("/api/embed", json={"texts": ["sql injection"], "is_query": True})
    assert r.status_code == 200 and r.json()["count"] == 1
    app.close()


def test_ingest_json_endpoint_replaces_instead_of_duplicating(tmp_path):
    from fastapi.testclient import TestClient

    from ragaudit.api.server import create_app

    app = make_app(tmp_path)
    client = TestClient(create_app(app))
    body = {"report_id": "ACME-1", "source_id": DB_ID,
            "data": {"detailed_observations": ROWS}}
    assert client.post("/api/ingest-json", json=body).json()["outcomes"][0]["status"] == "indexed"
    client.post("/api/ingest-json", json=body)
    assert [r["report_id"] for r in app.catalog.reports_overview()] == ["ACME-1"]
    assert app.catalog.count_findings() == 1
    app.close()
