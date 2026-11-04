"""
AI Pipeline Service
-------------------
Standalone FastAPI microservice that receives a report file,
runs a dummy AI analysis pipeline, and returns structured JSON results.
"""

import asyncio
import hashlib
import random
import uuid
import logging
from datetime import datetime, timezone

# Configure logging so we can see the ML pipeline progress in Docker logs
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    force=True
)

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="AI Pipeline Service",
    description="Dummy AI analysis pipeline for cyber-audit reports",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _generate_dummy_results(report_id: str, file_bytes: bytes, filename: str) -> dict:
    """Return the exact JSON structure provided by the user with zero additional information."""
    return {
  "report_meta": {
    "report_id": "AUD-2026-0047",
    "report_title": "Web Application and Infrastructure Security Audit Report",
    "report_type": "Cybersecurity Audit Report",
    "report_release_date": "2026-09-20",
    "report_version": "1.0",
    "audit_type": "Vulnerability Assessment and Penetration Testing",
    "audit_period": {
      "from": "2026-08-01",
      "to": "2026-09-15"
    },
    "classification": "Confidential"
  },
  "document_control": {
    "document_title": "Web Application and Infrastructure Security Audit Report",
    "document_id": "SEC-AUD-2026-0047",
    "document_version": "1.0",
    "prepared_by": {
      "name": "Rahul Sharma",
      "auditing_team_sr_no": 1
    },
    "reviewed_by": {
      "name": "Ananya Mehta",
      "auditing_team_sr_no": 2
    },
    "approved_by": {
      "name": "Vikram Singh",
      "auditing_team_sr_no": 3
    },
    "released_by": {
      "name": "Priya Kapoor",
      "auditing_team_sr_no": 4
    },
    "release_date": "2026-09-20",
    "change_history": [
      {
        "version": "0.1",
        "date": "2026-09-10",
        "remarks": "Initial draft prepared"
      },
      {
        "version": "0.2",
        "date": "2026-09-15",
        "remarks": "Findings and evidence updated after technical review"
      },
      {
        "version": "1.0",
        "date": "2026-09-20",
        "remarks": "Final report approved and released"
      }
    ],
    "distribution_list": [
      {
        "name": "Arjun Malhotra",
        "organization": "Example Technologies Pvt. Ltd.",
        "designation": "Chief Information Security Officer",
        "email": "arjun.malhotra@example.com"
      },
      {
        "name": "Neha Verma",
        "organization": "Example Technologies Pvt. Ltd.",
        "designation": "IT Security Manager",
        "email": "neha.verma@example.com"
      },
      {
        "name": "Rohit Bansal",
        "organization": "Example Technologies Pvt. Ltd.",
        "designation": "Infrastructure Lead",
        "email": "rohit.bansal@example.com"
      }
    ]
  },
  "engagement_scope": {
    "assets": [
      {
        "sr_no": 1,
        "asset_description": "Customer-facing web application",
        "url": "https://portal.example.com",
        "criticality": "High",
        "internal_ip": "10.20.10.15",
        "public_ip": "203.0.113.25",
        "in_scope_functions": "Authentication, user management, dashboard, file upload and reporting"
      },
      {
        "sr_no": 2,
        "asset_description": "REST API service",
        "url": "https://api.example.com",
        "criticality": "Critical",
        "internal_ip": "10.20.10.20",
        "public_ip": "203.0.113.30",
        "in_scope_functions": "Authentication API, customer API, transaction API and administrative endpoints"
      },
      {
        "sr_no": 3,
        "asset_description": "Corporate VPN Gateway",
        "url": "https://vpn.example.com",
        "criticality": "High",
        "internal_ip": "10.20.5.10",
        "public_ip": "203.0.113.40",
        "in_scope_functions": "Remote access authentication and VPN connectivity"
      },
      {
        "sr_no": 4,
        "asset_description": "Internal Database Server",
        "url": "N/A",
        "criticality": "Critical",
        "internal_ip": "10.20.30.15",
        "public_ip": "N/A",
        "in_scope_functions": "Application database and audit-log storage"
      }
    ],
    "scope_updated_till": "2026-08-05",
    "exclusions": [
      "Denial-of-service testing",
      "Social engineering",
      "Physical security testing",
      "Production database modification",
      "Destructive exploitation"
    ],
    "testing_credentials": [
      {
        "role": "Standard User",
        "account_identifier": "test_user_01",
        "auth_type": "Username and Password",
        "purpose": "Testing standard user functionality and authorization controls"
      },
      {
        "role": "Administrator",
        "account_identifier": "test_admin_01",
        "auth_type": "Username and Password with MFA",
        "purpose": "Testing administrative functionality and privilege boundaries"
      },
      {
        "role": "API Consumer",
        "account_identifier": "api_test_client",
        "auth_type": "API Key",
        "purpose": "Testing API authentication and authorization"
      }
    ]
  },
  "auditing_team": [
    {
      "sr_no": 1,
      "name": "Rahul Sharma",
      "designation": "Senior Security Analyst",
      "email": "rahul.sharma@audit-example.com",
      "certifications": "OSCP, CEH"
    },
    {
      "sr_no": 2,
      "name": "Ananya Mehta",
      "designation": "Security Consultant",
      "email": "ananya.mehta@audit-example.com",
      "certifications": "CISSP, CISA"
    },
    {
      "sr_no": 3,
      "name": "Vikram Singh",
      "designation": "Lead Auditor",
      "email": "vikram.singh@audit-example.com",
      "certifications": "CISA, ISO 27001 LA"
    },
    {
      "sr_no": 4,
      "name": "Priya Kapoor",
      "designation": "Audit Manager",
      "email": "priya.kapoor@audit-example.com",
      "certifications": "CISM, CRISC"
    }
  ],
  "audit_timeline": {
    "assessment_start_date": "2026-08-10",
    "assessment_end_date": "2026-09-05"
  },
  "methodology": {
    "standards_referred": [
      "OWASP Web Security Testing Guide",
      "OWASP Top 10",
      "NIST SP 800-115",
      "CIS Controls v8",
      "ISO/IEC 27001:2022"
    ]
  },
  "tools_used": [
    {
      "sr_no": 1,
      "tool_name": "Nmap",
      "version": "7.95",
      "license_type": "Open Source"
    },
    {
      "sr_no": 2,
      "tool_name": "Burp Suite Professional",
      "version": "2026.7",
      "license_type": "Licensed"
    },
    {
      "sr_no": 3,
      "tool_name": "OWASP ZAP",
      "version": "2.16.1",
      "license_type": "Open Source"
    },
    {
      "sr_no": 4,
      "tool_name": "Nessus Professional",
      "version": "10.9",
      "license_type": "Licensed"
    },
    {
      "sr_no": 5,
      "tool_name": "Nuclei",
      "version": "3.4.2",
      "license_type": "Open Source"
    }
  ],
  "executive_summary": {
    "total_findings": 8,
    "severity_count": {
      "critical": 1,
      "high": 2,
      "medium": 3,
      "low": 2
    },
    "narrative": "The security assessment identified eight findings across the web application, API, VPN gateway and supporting infrastructure. One Critical, two High, three Medium and two Low severity findings were identified. The most significant issues involved insufficient authorization controls, an exposed administrative service and insecure session-management configuration. Immediate remediation is recommended for the Critical and High severity findings, followed by remediation of the remaining Medium and Low severity findings according to the organization's risk-management process.",
    "summary_table": [
      {
        "sr_no": 1,
        "finding_id": "FND-001",
        "affected_asset": "https://api.example.com",
        "title": "Broken Object Level Authorization",
        "cwe": "CWE-862",
        "severity": "Critical",
        "status": "Open",
        "new_or_repeat": "New"
      },
      {
        "sr_no": 2,
        "finding_id": "FND-002",
        "affected_asset": "https://portal.example.com",
        "title": "Insufficient Session Expiration",
        "cwe": "CWE-613",
        "severity": "High",
        "status": "Open",
        "new_or_repeat": "New"
      },
      {
        "sr_no": 3,
        "finding_id": "FND-003",
        "affected_asset": "203.0.113.40",
        "title": "Exposed Administrative Service",
        "cwe": "CWE-668",
        "severity": "High",
        "status": "Partially Remediated",
        "new_or_repeat": "Repeat"
      },
      {
        "sr_no": 4,
        "finding_id": "FND-004",
        "affected_asset": "https://portal.example.com",
        "title": "Missing Security Headers",
        "cwe": "CWE-693",
        "severity": "Medium",
        "status": "Open",
        "new_or_repeat": "New"
      },
      {
        "sr_no": 5,
        "finding_id": "FND-005",
        "affected_asset": "https://api.example.com",
        "title": "Verbose API Error Messages",
        "cwe": "CWE-209",
        "severity": "Medium",
        "status": "Closed",
        "new_or_repeat": "New"
      },
      {
        "sr_no": 6,
        "finding_id": "FND-006",
        "affected_asset": "10.20.30.15",
        "title": "Database Account Password Policy Weakness",
        "cwe": "CWE-521",
        "severity": "Medium",
        "status": "Open",
        "new_or_repeat": "Repeat"
      },
      {
        "sr_no": 7,
        "finding_id": "FND-007",
        "affected_asset": "https://portal.example.com",
        "title": "Server Version Disclosure",
        "cwe": "CWE-200",
        "severity": "Low",
        "status": "Closed",
        "new_or_repeat": "New"
      },
      {
        "sr_no": 8,
        "finding_id": "FND-008",
        "affected_asset": "https://api.example.com",
        "title": "Missing Rate Limiting on Authentication Endpoint",
        "cwe": "CWE-307",
        "severity": "Low",
        "status": "Open",
        "new_or_repeat": "New"
      }
    ]
  },
  "detailed_observations": [
    {
      "finding_id": "FND-001",
      "title": "Broken Object Level Authorization",
      "status": "Open",
      "severity": "Critical",
      "impact_level": "Major",
      "likelihood_level": "Easy",
      "cve_id": [],
      "cvss_score": 9.1,
      "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:N",
      "severity_rationale": "An authenticated low-privileged user was able to access objects belonging to another user by modifying an object identifier in an API request.",
      "reported_epss_score": 0.0,
      "observation_date": "2026-08-18",
      "cwe": [
        "CWE-862"
      ],
      "affected_asset": [
        "https://api.example.com/v1/customer/profile"
      ],
      "regulatory_references": [
        "OWASP API Security Top 10 - API1:2023",
        "ISO/IEC 27001:2022 A.8.3"
      ],
      "observation_description": "The API did not consistently verify whether the authenticated user was authorized to access the requested object. By changing the object identifier in a request, test data belonging to another account could be retrieved.",
      "preconditions": "A valid authenticated low-privileged test account is required.",
      "proof_of_concept": [
        {
          "sr_no": 1,
          "type": "text",
          "reference": "POC-FND001-REQ01",
          "capture_date": "2026-08-18",
          "is_retest": False,
          "redacted": "Yes",
          "description": "Modified object identifier in an authenticated API request and observed unauthorized object access."
        },
        {
          "sr_no": 2,
          "type": "image",
          "reference": "IMG-FND001-01",
          "capture_date": "2026-08-18",
          "is_retest": False,
          "redacted": "Yes",
          "description": "Screenshot showing API response containing data associated with a different test account."
        }
      ],
      "impact": "Successful exploitation could allow unauthorized access to customer information and potentially permit unauthorized modification of application objects.",
      "likely_root_cause": "Authorization checks were implemented inconsistently across API endpoints and relied on client-supplied object identifiers.",
      "recommendation": "Implement server-side object-level authorization checks for every API request and verify resource ownership against the authenticated principal before returning or modifying data.",
      "reference": "OWASP API Security Top 10 - API1:2023",
      "new_or_repeat": "New"
    },
    {
      "finding_id": "FND-002",
      "title": "Insufficient Session Expiration",
      "status": "Open",
      "severity": "High",
      "impact_level": "Major",
      "likelihood_level": "Moderate",
      "cve_id": [],
      "cvss_score": 7.5,
      "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:U/C:H/I:N/A:N",
      "severity_rationale": "Application sessions remained valid significantly longer than the organization's defined session-management requirements.",
      "reported_epss_score": 0.001,
      "observation_date": "2026-08-20",
      "cwe": [
        "CWE-613"
      ],
      "affected_asset": [
        "https://portal.example.com"
      ],
      "regulatory_references": [
        "OWASP ASVS V3",
        "ISO/IEC 27001:2022 A.8.5"
      ],
      "observation_description": "Testing showed that an authenticated session remained active beyond the expected inactivity timeout.",
      "preconditions": "A valid authenticated test account is required.",
      "proof_of_concept": [
        {
          "sr_no": 1,
          "type": "text",
          "reference": "POC-FND002-REQ01",
          "capture_date": "2026-08-20",
          "is_retest": False,
          "redacted": "Yes",
          "description": "Session token remained accepted after the expected inactivity period."
        }
      ],
      "impact": "A stolen or unattended session token could remain usable for an extended period, increasing the window for unauthorized account access.",
      "likely_root_cause": "Session timeout configuration was not aligned with the documented security requirements.",
      "recommendation": "Configure appropriate idle and absolute session timeouts, invalidate sessions during logout and implement server-side session revocation where required.",
      "reference": "OWASP Application Security Verification Standard",
      "new_or_repeat": "New"
    },
    {
      "finding_id": "FND-003",
      "title": "Exposed Administrative Service",
      "status": "Partially Remediated",
      "severity": "High",
      "impact_level": "Major",
      "likelihood_level": "Moderate",
      "cve_id": [],
      "cvss_score": 8.2,
      "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:N",
      "severity_rationale": "An administrative management interface was accessible from an external network segment.",
      "reported_epss_score": 0.002,
      "observation_date": "2026-08-22",
      "cwe": [
        "CWE-668"
      ],
      "affected_asset": [
        "203.0.113.40"
      ],
      "regulatory_references": [
        "CIS Controls v8",
        "NIST SP 800-115"
      ],
      "observation_description": "Network scanning identified an externally accessible administrative service on the VPN gateway.",
      "preconditions": "Network access to the public interface is required.",
      "proof_of_concept": [
        {
          "sr_no": 1,
          "type": "image",
          "reference": "IMG-FND003-01",
          "capture_date": "2026-08-22",
          "is_retest": False,
          "redacted": "Yes",
          "description": "Port scan evidence showing the exposed administrative service."
        },
        {
          "sr_no": 2,
          "type": "text",
          "reference": "POC-FND003-RETEST01",
          "capture_date": "2026-09-05",
          "is_retest": True,
          "redacted": "Yes",
          "description": "Retest confirmed that external exposure was restricted but internal administrative access remained enabled."
        }
      ],
      "impact": "Exposure of administrative interfaces increases the attack surface and may allow unauthorized access attempts against privileged services.",
      "likely_root_cause": "Administrative access controls were not fully restricted to trusted management networks.",
      "recommendation": "Restrict administrative interfaces to approved management networks, implement VPN-based administration and enforce network-level access controls.",
      "reference": "CIS Controls v8 - Control 12",
      "new_or_repeat": "Repeat"
    },
    {
      "finding_id": "FND-004",
      "title": "Missing Security Headers",
      "status": "Open",
      "severity": "Medium",
      "impact_level": "Moderate",
      "likelihood_level": "Moderate",
      "cve_id": [],
      "cvss_score": 5.3,
      "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:U/C:L/I:N/A:N",
      "severity_rationale": "Multiple recommended HTTP security headers were absent from application responses.",
      "reported_epss_score": 0.0,
      "observation_date": "2026-08-24",
      "cwe": [
        "CWE-693"
      ],
      "affected_asset": [
        "https://portal.example.com"
      ],
      "regulatory_references": [
        "OWASP Secure Headers Project"
      ],
      "observation_description": "HTTP responses did not consistently include security headers such as Content-Security-Policy and X-Content-Type-Options.",
      "preconditions": "No special privileges are required.",
      "proof_of_concept": [
        {
          "sr_no": 1,
          "type": "text",
          "reference": "POC-FND004-HEADERS01",
          "capture_date": "2026-08-24",
          "is_retest": False,
          "redacted": "NA",
          "description": "HTTP response header inspection identified missing recommended security headers."
        }
      ],
      "impact": "The absence of security headers may increase exposure to browser-based attacks and reduce defense-in-depth protections.",
      "likely_root_cause": "Security headers were not centrally configured at the application or reverse-proxy layer.",
      "recommendation": "Implement and validate appropriate security headers based on application requirements and test them across all externally accessible endpoints.",
      "reference": "OWASP Secure Headers Project",
      "new_or_repeat": "New"
    },
    {
      "finding_id": "FND-005",
      "title": "Verbose API Error Messages",
      "status": "Closed",
      "severity": "Medium",
      "impact_level": "Moderate",
      "likelihood_level": "Moderate",
      "cve_id": [],
      "cvss_score": 5.0,
      "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:N/A:N",
      "severity_rationale": "API responses exposed implementation details that could assist an attacker during reconnaissance.",
      "reported_epss_score": 0.0,
      "observation_date": "2026-08-25",
      "cwe": [
        "CWE-209"
      ],
      "affected_asset": [
        "https://api.example.com"
      ],
      "regulatory_references": [
        "OWASP API Security Top 10"
      ],
      "observation_description": "Invalid requests returned detailed application and database error information.",
      "preconditions": "No special privileges are required.",
      "proof_of_concept": [
        {
          "sr_no": 1,
          "type": "text",
          "reference": "POC-FND005-ERR01",
          "capture_date": "2026-08-25",
          "is_retest": False,
          "redacted": "Yes",
          "description": "API response exposed internal implementation details."
        },
        {
          "sr_no": 2,
          "type": "text",
          "reference": "POC-FND005-RETEST01",
          "capture_date": "2026-09-05",
          "is_retest": True,
          "redacted": "Yes",
          "description": "Retest confirmed generic error messages were returned."
        }
      ],
      "impact": "Information disclosure could assist attackers in understanding internal application architecture.",
      "likely_root_cause": "Production error-handling middleware returned detailed exception information.",
      "recommendation": "Return generic client-facing error messages and log detailed exception information only on protected server-side logging infrastructure.",
      "reference": "CWE-209",
      "new_or_repeat": "New"
    },
    {
      "finding_id": "FND-006",
      "title": "Database Account Password Policy Weakness",
      "status": "Open",
      "severity": "Medium",
      "impact_level": "Moderate",
      "likelihood_level": "Hard",
      "cve_id": [],
      "cvss_score": 5.9,
      "cvss_vector": "CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:U/C:H/I:N/A:N",
      "severity_rationale": "A database service account was configured with password controls that did not meet the organization's documented security requirements.",
      "reported_epss_score": 0.0,
      "observation_date": "2026-08-28",
      "cwe": [
        "CWE-521"
      ],
      "affected_asset": [
        "10.20.30.15"
      ],
      "regulatory_references": [
        "CIS Controls v8"
      ],
      "observation_description": "Review of database account configuration identified a service account with an outdated password-management configuration.",
      "preconditions": "Privileged configuration access is required.",
      "proof_of_concept": [
        {
          "sr_no": 1,
          "type": "text",
          "reference": "POC-FND006-CONFIG01",
          "capture_date": "2026-08-28",
          "is_retest": False,
          "redacted": "Yes",
          "description": "Configuration review identified password policy deviation."
        }
      ],
      "impact": "Weak credential-management controls can increase the risk of unauthorized database access if credentials are compromised.",
      "likely_root_cause": "Legacy service-account configuration was not migrated to the current password-management standard.",
      "recommendation": "Apply strong password requirements, rotate service-account credentials regularly and use a managed secrets solution where feasible.",
      "reference": "CIS Controls v8",
      "new_or_repeat": "Repeat"
    },
    {
      "finding_id": "FND-007",
      "title": "Server Version Disclosure",
      "status": "Closed",
      "severity": "Low",
      "impact_level": "Minor",
      "likelihood_level": "Easy",
      "cve_id": [],
      "cvss_score": 3.1,
      "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:N/A:N",
      "severity_rationale": "The web server disclosed software version information through HTTP response headers.",
      "reported_epss_score": 0.0,
      "observation_date": "2026-08-30",
      "cwe": [
        "CWE-200"
      ],
      "affected_asset": [
        "https://portal.example.com"
      ],
      "regulatory_references": [
        "OWASP Testing Guide"
      ],
      "observation_description": "Server response headers disclosed the underlying web server software and version.",
      "preconditions": "No special privileges are required.",
      "proof_of_concept": [
        {
          "sr_no": 1,
          "type": "text",
          "reference": "POC-FND007-HEADERS01",
          "capture_date": "2026-08-30",
          "is_retest": False,
          "redacted": "NA",
          "description": "HTTP headers disclosed server software information."
        },
        {
          "sr_no": 2,
          "type": "text",
          "reference": "POC-FND007-RETEST01",
          "capture_date": "2026-09-05",
          "is_retest": True,
          "redacted": "NA",
          "description": "Retest confirmed server version information was removed."
        }
      ],
      "impact": "Version disclosure can provide attackers with additional information for reconnaissance.",
      "likely_root_cause": "Default server configuration exposed software version information.",
      "recommendation": "Disable unnecessary server version disclosure at the web-server and reverse-proxy layers.",
      "reference": "OWASP Testing Guide",
      "new_or_repeat": "New"
    },
    {
      "finding_id": "FND-008",
      "title": "Missing Rate Limiting on Authentication Endpoint",
      "status": "Open",
      "severity": "Low",
      "impact_level": "Minor",
      "likelihood_level": "Moderate",
      "cve_id": [],
      "cvss_score": 3.7,
      "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:N/A:N",
      "severity_rationale": "The authentication endpoint did not consistently enforce request-rate controls during testing.",
      "reported_epss_score": 0.0,
      "observation_date": "2026-09-01",
      "cwe": [
        "CWE-307"
      ],
      "affected_asset": [
        "https://api.example.com/v1/auth/login"
      ],
      "regulatory_references": [
        "OWASP API Security Top 10"
      ],
      "observation_description": "Multiple authentication requests could be submitted without triggering an effective rate-limiting response.",
      "preconditions": "Network access to the authentication endpoint is required.",
      "proof_of_concept": [
        {
          "sr_no": 1,
          "type": "text",
          "reference": "POC-FND008-RATE01",
          "capture_date": "2026-09-01",
          "is_retest": False,
          "redacted": "Yes",
          "description": "Controlled authentication requests were submitted to evaluate rate-limiting behavior."
        }
      ],
      "impact": "Insufficient rate limiting can increase exposure to automated authentication attacks and excessive request traffic.",
      "likely_root_cause": "Rate-limiting controls were configured at the infrastructure layer but not consistently applied to the authentication API.",
      "recommendation": "Implement server-side rate limiting, account-based throttling, progressive delays and appropriate monitoring for repeated authentication failures.",
      "reference": "OWASP API Security Top 10",
      "new_or_repeat": "New"
    }
  ],
  "appendices": {
    "risk_rating_criteria": [
      {
        "rating": "Critical",
        "description": "Finding could result in severe compromise of confidentiality, integrity or availability and requires immediate remediation.",
        "impact_level": "Major",
        "likelihood_level": "Easy"
      },
      {
        "rating": "High",
        "description": "Finding could result in significant unauthorized access or compromise and should be remediated with high priority.",
        "impact_level": "Major",
        "likelihood_level": "Moderate"
      },
      {
        "rating": "Medium",
        "description": "Finding represents a material security weakness that should be addressed through planned remediation.",
        "impact_level": "Moderate",
        "likelihood_level": "Moderate"
      },
      {
        "rating": "Low",
        "description": "Finding represents a limited security weakness or information disclosure with comparatively lower impact.",
        "impact_level": "Minor",
        "likelihood_level": "Easy"
      }
    ],
    "retest_closure": [
      {
        "finding_id": "FND-003",
        "retest_date": "2026-09-05",
        "closure_evidence_ref": 2,
        "status": "Partially Remediated"
      },
      {
        "finding_id": "FND-005",
        "retest_date": "2026-09-05",
        "closure_evidence_ref": 2,
        "status": "Closed"
      },
      {
        "finding_id": "FND-007",
        "retest_date": "2026-09-05",
        "closure_evidence_ref": 2,
        "status": "Closed"
      }
    ]
  }
}

@app.post("/run")
async def run_pipeline(
    report_id: str = Form(...),
    file: UploadFile = File(...),
):
    """
    Run the AI analysis pipeline on the uploaded report file.
    Streams logs as Server-Sent Events, ending with the final JSON result.
    """
    file_bytes = await file.read()
    filename = file.filename or "unknown"
    
    import tempfile
    import os
    import sys
    import threading
    import queue
    import json
    from pathlib import Path
    from fastapi.responses import StreamingResponse
    
    # Add the document-standardization folder to the path dynamically
    doc_standardization_path = Path(__file__).resolve().parent.parent.parent / "document-standardization"
    if str(doc_standardization_path) not in sys.path:
        sys.path.append(str(doc_standardization_path))
        
    from report_to_json.api import process_report

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    tmp.write(file_bytes)
    tmp.close()
    tmp_path = tmp.name

    log_queue = queue.Queue()
    
    # Use threading.local to store the report_id for the current thread
    thread_local = threading.local()
    
    class ReportFilter(logging.Filter):
        def filter(self, record):
            record.report_id = getattr(thread_local, 'report_id', None)
            return True

    class QueueHandler(logging.Handler):
        def __init__(self, target_report_id, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.target_report_id = target_report_id

        def emit(self, record):
            if getattr(record, 'report_id', None) == self.target_report_id:
                log_queue.put({"type": "log", "message": self.format(record)})

    handler = QueueHandler(target_report_id=report_id)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger = logging.getLogger('report_to_json')
    
    # Ensure the filter is attached to the HANDLER so it applies to propagated records
    report_filter = ReportFilter()
    handler.addFilter(report_filter)
    logger.addHandler(handler)

    def worker():
        # Set the report_id for this specific worker thread
        thread_local.report_id = report_id
        try:
            result = process_report(tmp_path, save_to_disk=False)
            log_queue.put({"type": "result", "data": result.data})
        except Exception as e:
            log_queue.put({"type": "error", "message": str(e)})
        finally:
            log_queue.put(None)  # Sentinel to end the stream
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            logger.removeHandler(handler)

    thread = threading.Thread(target=worker)
    thread.start()

    async def event_generator():
        try:
            while True:
                # Use asyncio.to_thread to wait for the queue without blocking the event loop
                item = await asyncio.to_thread(log_queue.get)
                if item is None:
                    break
                yield f"data: {json.dumps(item)}\n\n"
        finally:
            logger.removeHandler(handler)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "ai-pipeline"}
