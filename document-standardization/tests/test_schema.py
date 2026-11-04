from report_to_json import schema


def test_json_schema_is_derived_from_template():
    js = schema.json_schema()
    obs = js["properties"]["detailed_observations"]["items"]["properties"]
    assert obs["severity"]["enum"] == ["Critical", "High", "Medium", "Low", None]
    assert obs["cvss_score"] == {"type": ["number", "null"]}
    assert js["properties"]["report_meta"]["properties"]["report_release_date"]["anyOf"][0]["pattern"]
    assert js["additionalProperties"] is False  # no keys beyond the master schema


def test_template_is_the_master_schema_as_specified():
    t = schema.template()
    assert list(t) == ["report_meta", "document_control", "engagement_scope", "auditing_team", "audit_timeline",
                       "methodology", "tools_used", "executive_summary", "detailed_observations", "appendices"]
    assert list(t["executive_summary"]["severity_count"]) == ["critical", "high", "medium", "low"]


def test_enforce_builds_the_exact_shape():
    out, dropped = schema.enforce({"report_meta": {"report_title": "T"}, "detailed_observations": [{"title": "x"}]})
    assert dropped == []
    assert out["report_meta"]["report_title"] == "T"
    assert out["report_meta"]["audit_period"] == {"from": None, "to": None}
    assert out["detailed_observations"][0]["proof_of_concept"] == []
    assert set(out) == set(schema.template())
    assert schema.validate(out) == []


def test_enforce_normalises_losslessly_and_drops_the_rest():
    out, dropped = schema.enforce({
        "report_meta": {"report_release_date": "16.02.2026", "audit_period": {"from": "after 3 Jan 2025"}},
        "tools_used": [{"tool_name": "Nmap", "version": 7.94, "license_type": "open source"},
                       {"tool_name": "Nessus", "license_type": "Freeware"}],
        "executive_summary": {"total_findings": "12", "severity_count": {"informational": 2}},
        "detailed_observations": [{"cwe": ["CWE-79", None], "proof_of_concept": [{"is_retest": "true"}]}],
        "extra_section": {"a": 1},
    })
    assert out["report_meta"]["report_release_date"] == "2026-02-16"
    assert out["report_meta"]["audit_period"]["from"] is None  # a sentence, not a date: not rewritten
    assert out["tools_used"][0] == {"sr_no": None, "tool_name": "Nmap", "version": "7.94",
                                    "license_type": "Open Source"}
    assert out["tools_used"][1]["license_type"] is None
    assert out["executive_summary"]["total_findings"] == 12
    assert out["detailed_observations"][0]["cwe"] == ["CWE-79"]
    assert out["detailed_observations"][0]["proof_of_concept"][0]["is_retest"] is True
    assert {d["path"] for d in dropped} == {
        "report_meta.audit_period.from", "tools_used[1].license_type",
        "executive_summary.severity_count.informational", "extra_section"}
    assert schema.validate(out) == []


def test_validate_reports_enum_and_date_problems():
    data = schema.conform({"report_meta": {"report_release_date": "16.02.2026"},
                           "detailed_observations": [{"severity": "Severe"}]})
    errors = schema.validate(data)
    assert any(e.startswith("report_meta.report_release_date") for e in errors)
    assert any(e.startswith("detailed_observations[0].severity") for e in errors)


def test_missing_fields_aggregates_list_items():
    data = schema.conform({"detailed_observations": [{"title": "a", "cvss_score": 5.0}, {"title": "b"}]})
    missing = schema.missing_fields(data)
    assert "detailed_observations[*].cvss_score (1/2 missing)" in missing
    assert "auditing_team (empty)" in missing
    assert "report_meta.report_id" in missing
