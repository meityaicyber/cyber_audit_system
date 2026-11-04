import json

from report_to_json.structurer import RuleBasedStructurer

# Values the previous structurer invented when a field was missing. None may
# appear in output unless the document itself contains them.
FORMER_FABRICATIONS = [
    "https://api.target.com",
    "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:N",
    "None declared",
    "2026-05-29",
    "Missing server-side authorization and parameter validation.",
    "Attacker has network access and standard API permissions.",
    "Vulnerability identified and verified during API security assessment.",
    "Auditor 1",
]

CERT_IN_TRANSCRIPT = """# Document Transcript: sample.pdf

<!-- PAGE_START: 1 -->
## Page 1

### Table 1.1
| Report Release Date | 16.02.2026 |
| --- | --- |
| Type of Audit | API Assessment Final Report |
| Type of Audit Report | Follow Up Report |
| Period | 29.07.2025 to 15.02.2026 |

### Table 1.2
|  |  |  | Document Preparation |
| --- | --- | --- | --- |
| Document Title | Document Title |  | API Assessment Report |
| Document Version |  |  | 1.1 |
| Prepared by |  |  | Jane Doe |
| Reviewed by |  |  | John Roe |

### Page Text Content
Acme Payments API Assessment Report
<!-- PAGE_END: 1 -->

<!-- PAGE_START: 2 -->
## Page 2

### Table 2.1
| Version | Version |  | Date | Remarks |
| --- | --- | --- | --- | --- |
| 1.0 |  |  | 05th September 2025 | First Audit Report |

### Table 2.2
| Sr. No. | Name | Designation | Email Id | Certifications | Listed |
| --- | --- | --- | --- | --- | --- |
| 1 | Jane Doe | Senior Associate | jane@example.test | CEH, OSCP | Yes |
| 2 | John Roe | Manager | john@example.test | - | No |

### Table 2.3
| S. No | Name of Tool/Software used | Version | Open Source/Licensed |
| --- | --- | --- | --- |
| 1 | Burp Suite Pro | 2026.1 | Licensed |

### Table 2.4
| S. | Asset | Criticality | Internal | URL | Public |
| --- | --- | --- | --- | --- | --- |
| No | Description | of Asset | IP |  | IP |
| 1 | Payments API | High | 10.0.0.5 | https://api.example- test/v2/pay | NA |

### Page Text Content
Audit Activities and Timelines
Assessment Start Date
Assessment End Date
29th July 2025
16th February 2026
Audit Methodology and Criteria/Standard Referred
Testing followed the OWASP API Security Top 10 and NIST SP 800-115.
Tools/Software Used
<!-- PAGE_END: 2 -->

<!-- PAGE_START: 3 -->
## Page 3

### Page Text Content
Executive Summary
Two issues were identified in the payments API.
1
Detailed Observations
1. Broken Authentication
Status: Closed Severity:
High
Detailed Observation:
The API accepts requests with an empty
encrypted payload.
Impact:
An attacker can submit unencrypted payment data.
CVE/CWE:
•
CWE-284: Improper Access Control •  CWE-693: Protection Mechanism Failure
Affected Asset:
•
P2P - https://api.example.test/v2/pay
Recommendation:
Reject empty or invalid encrypted fields.
Reference: NA
New or Repeat observation: Repeat
Proof of Concept:
[IMAGE_PAGE_3_FIG_1] *(Figure 1: page_3_fig_1.png, 800x600px)*
Revalidation Proof of Concept:
[IMAGE_PAGE_3_FIG_2] *(Figure 2: page_3_fig_2.png, 800x600px)*
<!-- PAGE_END: 3 -->
"""

CASE_TEMPLATE = """Detailed Findings
Case I
i.
Affected Asset i.e. IP/URL/Application etc.
192.168.25.109
ii. Observation/vulnerability
title
Bluetooth Enabled
iii.
Detailed observation / Vulnerable point
Bluetooth is enabled on the device.
iv.
CVE/CWE
CWE-119
v.
Severity
High
vi.
Recommendation
Disable Bluetooth if not required.
vii. Reference
Case I
viii. New or Repeat observation
New
Case II
ii.
Observation/ Vulnerability title
SSH Enabled iii.  Detailed observation /
Vulnerable point
SSH is exposed.
v.
Severity
Medium
vi.
Recommendation
Restrict SSH.
"""


def structure(md):
    return RuleBasedStructurer().structure(md)


def test_metadata_and_tables_are_extracted():
    d = structure(CERT_IN_TRANSCRIPT)
    meta = d["report_meta"]
    assert meta["report_title"] == "Acme Payments API Assessment Report"
    assert meta["report_type"] == "API Assessment Final Report"
    assert meta["audit_type"] == "Follow Up Report"
    assert meta["report_release_date"] == "2026-02-16"
    assert meta["audit_period"] == {"from": "2025-07-29", "to": "2026-02-15"}
    assert d["audit_timeline"] == {"assessment_start_date": "2025-07-29", "assessment_end_date": "2026-02-16"}

    dc = d["document_control"]
    assert dc["prepared_by"] == {"name": "Jane Doe", "auditing_team_sr_no": 1}
    assert dc["reviewed_by"] == {"name": "John Roe", "auditing_team_sr_no": 2}
    assert dc["approved_by"] == {"name": None, "auditing_team_sr_no": None}
    assert dc["change_history"] == [{"version": "1.0", "date": "2025-09-05", "remarks": "First Audit Report"}]

    assert [m["name"] for m in d["auditing_team"]] == ["Jane Doe", "John Roe"]
    assert d["auditing_team"][1]["certifications"] is None  # "-" in the document
    assert d["tools_used"] == [{"sr_no": 1, "tool_name": "Burp Suite Pro", "version": "2026.1",
                                "license_type": "Licensed"}]
    assert d["methodology"]["standards_referred"] == ["OWASP API Security Top 10", "NIST SP 800-115"]

    [asset] = d["engagement_scope"]["assets"]
    assert asset["asset_description"] == "Payments API"
    assert asset["criticality"] == "High"
    assert asset["internal_ip"] == "10.0.0.5"
    assert asset["url"] == "https://api.example-test/v2/pay"


def test_finding_fields_and_evidence():
    [obs] = structure(CERT_IN_TRANSCRIPT)["detailed_observations"]
    assert obs["finding_id"] == "1"
    assert obs["title"] == "Broken Authentication"
    assert obs["status"] == "Closed"
    assert obs["severity"] == "High"  # label and value on different lines
    assert obs["observation_description"] == "The API accepts requests with an empty encrypted payload."
    assert obs["cwe"] == ["CWE-284: Improper Access Control", "CWE-693: Protection Mechanism Failure"]
    assert obs["affected_asset"] == ["P2P - https://api.example.test/v2/pay"]
    assert obs["new_or_repeat"] == "Repeat"
    assert obs["reference"] == "NA"
    assert [(p["reference"], p["is_retest"]) for p in obs["proof_of_concept"]] == [
        ("[IMAGE_PAGE_3_FIG_1]", False), ("[IMAGE_PAGE_3_FIG_2]", True)]


def test_missing_fields_are_null_not_invented():
    d = structure(CERT_IN_TRANSCRIPT)
    obs = d["detailed_observations"][0]
    for key in ("cvss_score", "cvss_vector", "severity_rationale", "preconditions", "likely_root_cause",
                "impact_level", "likelihood_level", "observation_date", "reported_epss_score"):
        assert obs[key] is None, key
    assert obs["cve_id"] == []
    assert all(p["capture_date"] is None and p["redacted"] is None for p in obs["proof_of_concept"])
    assert d["engagement_scope"]["exclusions"] == []
    assert d["appendices"]["risk_rating_criteria"] == []
    assert d["report_meta"]["classification"] is None


def test_nothing_is_fabricated_for_an_empty_document():
    d = structure("# Document Transcript: empty.pdf\n\nNothing useful here.")
    dumped = json.dumps(d)
    for value in FORMER_FABRICATIONS:
        assert value not in dumped
    assert d["detailed_observations"] == []
    assert d["auditing_team"] == [] and d["tools_used"] == []
    assert d["methodology"]["standards_referred"] == []
    assert d["report_meta"]["report_type"] is None


def test_executive_summary_is_derived_from_findings():
    d = structure(CERT_IN_TRANSCRIPT)
    es = d["executive_summary"]
    assert es["total_findings"] == 1
    assert es["severity_count"]["high"] == 1
    assert es["narrative"] == "Two issues were identified in the payments API."
    assert es["summary_table"][0]["cwe"] == "CWE-284"


def test_cert_in_case_template():
    obs = structure(CASE_TEMPLATE)["detailed_observations"]
    assert [(o["finding_id"], o["title"], o["severity"]) for o in obs] == [
        ("I", "Bluetooth Enabled", "High"), ("II", "SSH Enabled", "Medium")]
    assert obs[0]["affected_asset"] == ["192.168.25.109"]
    assert obs[0]["cwe"] == ["CWE-119"]
    assert obs[0]["recommendation"] == "Disable Bluetooth if not required."
    assert obs[1]["observation_description"] == "SSH is exposed."


def test_numbered_methodology_prose_is_not_a_finding():
    md = ("1. Possible (Medium): Possible, but not expected.\n"
          "2. Likely (High): Likely, with moderate effort.\n"
          "Severity Rating\nRange\n")
    assert structure(md)["detailed_observations"] == []


def test_findings_table_fallback_without_header():
    md = ("### Table 21.1\n"
          "| 1 | app.apk |  | Absence of code signing | CWE- 347 | High | High |  | "
          "It is strongly recommended to sign all non-development builds with a release certificate. |\n"
          "| --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
          "| 2 | app.apk |  | Hardcoded credentials | CWE-798 | Information | Information |  | "
          "No immediate remediation is required, but minimise local storage of identifiers. |\n")
    obs = structure(md)["detailed_observations"]
    assert [(o["title"], o["severity"], o["cwe"]) for o in obs] == [
        ("Absence of code signing", "High", ["CWE-347"]),
        ("Hardcoded credentials", "Informational", ["CWE-798"])]
    assert obs[0]["affected_asset"] == ["app.apk"]
