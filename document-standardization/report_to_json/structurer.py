"""
Stage 3 (deterministic path): structure an intermediate Markdown transcript into
the master schema.

Ground rule: every value in the output comes from the document. A field the
parser cannot find is ``null`` (or an empty list) — never a plausible-looking
default. Downstream benchmarking scores these fields, so an invented CVSS vector,
asset URL or exclusion list would silently change a report's score.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from . import textparse as tp

log = logging.getLogger(__name__)


# --------------------------------------------------------------------------- metadata labels

# Normalised label text -> field it populates. Matched against whole table
# cells / whole text lines only, so "type of audit" never matches
# "type of audit report".
META_LABELS: Dict[str, str] = {
    "report release date": "report_release_date",
    "date of report": "report_release_date",
    "report date": "report_release_date",
    "report id": "report_id",
    "report no": "report_id",
    "report number": "report_id",
    "report title": "report_title",
    "type of audit": "report_type",
    "type of assessment": "report_type",
    "assessment type": "report_type",
    "report type": "report_type",
    "type of audit report": "audit_type",
    "audit report type": "audit_type",
    "period": "audit_period",
    "audit period": "audit_period",
    "assessment period": "audit_period",
    "period of audit": "audit_period",
    "classification": "classification",
    "document classification": "classification",
    "document title": "document_title",
    "document id": "document_id",
    "document version": "document_version",
    "prepared by": "prepared_by",
    "reviewed by": "reviewed_by",
    "approved by": "approved_by",
    "released by": "released_by",
    "issued by": "released_by",
    "release date": "release_date",
    "assessment start date": "assessment_start_date",
    "assessment end date": "assessment_end_date",
    "audit start date": "assessment_start_date",
    "audit end date": "assessment_end_date",
    "date up to which the list has been updated": "scope_updated_till",
}

STANDARDS: List[Tuple[str, str]] = [
    ("OWASP API Security Top 10", r"OWASP\s+API\s+(?:Security\s+)?Top\s*(?:10|Ten)"),
    ("OWASP Mobile Top 10", r"OWASP\s+Mobile\s+(?:Security\s+)?Top\s*(?:10|Ten)"),
    ("OWASP IoT Top 10", r"OWASP\s+IoT\s+Top\s*(?:10|Ten)"),
    ("OWASP Top 10", r"OWASP\s+Top\s*(?:10|Ten)"),
    ("OWASP MASVS", r"\bMASVS\b"),
    ("OWASP MASTG", r"\bMASTG\b|\bMSTG\b"),
    ("OWASP ASVS", r"\bASVS\b"),
    ("OWASP Web Security Testing Guide", r"OWASP\s+(?:Web\s+Security\s+)?Testing\s+Guide|\bWSTG\b"),
    ("NIST SP 800-115", r"SP\s*800-115"),
    ("NIST SP 800-53", r"SP\s*800-53"),
    ("NIST Cybersecurity Framework", r"NIST\s+(?:Cyber\s*security\s+Framework|CSF)"),
    ("PTES", r"\bPTES\b|Penetration\s+Testing\s+Execution\s+Standard"),
    ("OSSTMM", r"\bOSSTMM\b"),
    ("CERT-In Guidelines", r"CERT-?In"),
    ("ISO/IEC 27001", r"ISO(?:/IEC)?\s*27001"),
    ("PCI DSS", r"PCI[\s-]*DSS"),
    ("SANS/CWE Top 25", r"SANS\s+(?:Top\s*)?25|CWE\s+Top\s*25"),
    ("CIS Benchmarks", r"\bCIS\s+(?:Controls|Benchmarks?)"),
    ("MITRE ATT&CK", r"MITRE\s+ATT&?CK"),
    ("ETSI EN 303 645", r"EN\s*303\s*645"),
]

# --------------------------------------------------------------------------- finding labels

FINDING_LABELS: List[Tuple[str, str]] = [
    ("retest_poc", r"(?:Re-?validation|Re-?test(?:ing)?)\s+Proof\s+of\s+Concepts?"),
    ("poc", r"(?:References?\s+to\s+evidence\s*/\s*)?Proof\s+of\s+Concepts?|PoC|Steps\s+to\s+Reproduce|Screenshots?"),
    ("finding_id", r"(?:Finding|Observation|Vulnerability)\s+(?:ID|No\.?|Number)"),
    ("observation_date", r"(?:Observation|Identified|Discovery)\s+Date|Date\s+(?:Identified|Observed)"),
    ("title", r"Observation\s*/\s*Vulnerability\s+title|(?:Vulnerability|Observation|Finding)\s+Title"),
    ("observation_description",
     r"Detailed\s+Observations?(?:\s*/\s*Vulnerable\s+point)?"
     r"|(?:Observation|Vulnerability|Finding)\s+Description|Description|Observation"),
    ("impact_level", r"Impact\s+(?:Level|Rating)"),
    ("likelihood_level", r"Likelihood(?:\s+Level)?|Ease\s+of\s+Exploitation"),
    ("impact", r"(?:Business\s+)?Impact"),
    ("cve_cwe", r"CVE\s*/\s*CWE|CWE\s*/\s*CVE|CWE(?:\s+ID)?|CVE(?:\s+ID)?"),
    ("affected_asset",
     r"Affected\s+(?:Assets?|URLs?|IPs?|IP\s+Address(?:es)?|Endpoints?|Hosts?|Components?|Systems?|Applications?)"
     r"(?:\s+i\.?e\.?[^\n:]*)?|Vulnerable\s+(?:URLs?|Endpoints?)"),
    ("recommendation", r"Recommendations?|Remediation|Mitigation|Solution"),
    ("reference", r"References?|Ref"),
    ("new_or_repeat", r"New\s+or\s+Repeat(?:\s+Observation)?|New\s*/\s*Repeat"),
    ("status", r"(?:Current\s+)?Status"),
    ("severity_rationale", r"Severity\s+Rationale|Risk\s+Rationale"),
    ("severity", r"Severity(?:\s+Rating)?|Risk(?:\s+Rating)?"),
    ("cvss_vector", r"CVSS\s+Vector|Vector\s+String"),
    ("cvss", r"CVSS(?:\s*v?\d(?:\.\d)?)?(?:\s+Base)?(?:\s+Score)?"),
    ("epss", r"EPSS(?:\s+Score)?"),
    ("preconditions", r"Pre-?conditions?|Prerequisites?"),
    ("likely_root_cause", r"(?:Likely\s+)?Root\s+Cause"),
    ("regulatory_references",
     r"Regulatory\s+(?:References?|Requirements?)|Compliance\s+(?:References?|Mapping)"),
]

_LABEL_ALTS = "|".join(f"(?P<{key}>{pattern})" for key, pattern in FINDING_LABELS)
_ITEM_MARK = r"(?:[•\-*]|(?:[ivx]{1,4}|\d{1,2})[.)])"

# A label is recognised when it:
#  - starts a line (optionally after a bullet or "iv."-style marker) and is followed by
#    a colon, or stands alone on its line (CERT-In "Case" template, value on next lines);
#  - follows other text on the same line, is capitalised and followed by a colon
#    ("Status: Open Severity: High", "app.apk Recommendation:");
#  - follows other text after a roman-numeral marker ("SSH Enabled iii. Detailed observation").
_LABEL_RES = [
    re.compile(
        rf"(?m)^[ \t]*(?:{_ITEM_MARK}[ \t]*)?(?:\*\*)?(?i:{_LABEL_ALTS})(?:\*\*)?"
        r"[ \t]*(?:\([^)\n]*\))?[ \t]*(?::(?:\*\*)?|(?=[ \t]*$))"
    ),
    re.compile(rf"(?m)(?<=\S)[ \t]+(?:\*\*)?(?:{_LABEL_ALTS})(?:\*\*)?[ \t]*:(?:\*\*)?"),
    re.compile(rf"(?m)(?<=\S)[ \t]+[ivx]{{1,4}}\.\s+(?i:{_LABEL_ALTS})[ \t]*(?::|(?=[ \t]*$))"),
]


def _label_matches(text: str) -> List[re.Match]:
    """All label matches in ``text``, ordered and without overlaps."""
    found = sorted((m for rx in _LABEL_RES for m in rx.finditer(text)), key=lambda m: (m.start(), -m.end()))
    out: List[re.Match] = []
    for m in found:
        if not out or m.start() >= out[-1].end():
            out.append(m)
    return out


# (header pattern, how far ahead a Severity/Status label must appear to accept it)
_FINDING_HEADER_RES = [
    (re.compile(r"^\s*(?:#{1,6}\s*)?(?P<num>\d{1,3})[.)]\s+(?P<title>\S.{1,200}?)\s*$"), 600),
    (re.compile(
        r"^\s*(?:#{1,6}\s*)?(?:Finding|Observation|Vulnerability)\s*(?:No\.?|#)?\s*"
        r"(?P<num>[A-Za-z]*-?\d{1,4})\s*[:.\-–]\s*(?P<title>\S.{1,200}?)\s*$",
        re.IGNORECASE,
    ), 600),
    # CERT-In "Case I / Case II" template: title comes from the "Observation/Vulnerability title" field.
    (re.compile(r"^\s*(?:#{1,6}\s*)?Case\s+(?P<num>[IVXLC]{1,6}|\d{1,3})\s*[:.\-–]?\s*(?P<title>.{0,200}?)\s*$"), 3000),
]
_SEVERITY_OR_STATUS_RE = re.compile(
    r"(?im)^[ \t]*(?:[•\-*][ \t]*)?(?:(?:[ivx]{1,4}|\d{1,2})[.)][ \t]*)?(?:\*\*)?"
    r"(?:Severity(?:\s+Rating)?|Status|Risk(?:\s+Rating)?)(?:\*\*)?[ \t]*(?::|$)"
    r"|[ \t](?:Severity|Status)[ \t]*:"
)
_APPENDIX_RE = re.compile(r"(?im)^[ \t]*(?:#{1,6}\s*)?(?:Appendix|Appendices|Annexure)\b.*$")

SEVERITIES = ["Critical", "High", "Medium", "Low", "Informational"]


class RuleBasedStructurer:
    """Deterministic transcript → master-schema parser."""

    def structure(self, markdown: str) -> Dict[str, Any]:
        tables = tp.parse_tables(markdown)
        meta = self._collect_labels(markdown, tables)
        team = self._auditing_team(tables)
        observations = self._observations(markdown)

        period_raw = meta.get("audit_period")
        period_dates = tp.find_dates(period_raw) if period_raw else []
        start = tp.date_field(meta.get("assessment_start_date"))
        end = tp.date_field(meta.get("assessment_end_date"))
        start, end = start or self._timeline_date(markdown, 0), end or self._timeline_date(markdown, 1)

        data: Dict[str, Any] = {
            "report_meta": {
                "report_id": tp.clean_value(meta.get("report_id")),
                "report_title": tp.clean_value(meta.get("report_title")) or self._report_title(markdown),
                "report_type": tp.clean_value(meta.get("report_type")),
                "report_release_date": tp.date_field(meta.get("report_release_date")),
                "report_version": tp.clean_value(meta.get("document_version")),
                "audit_type": tp.clean_value(meta.get("audit_type")),
                "audit_period": {
                    "from": period_dates[0] if period_dates else None,
                    "to": period_dates[1] if len(period_dates) > 1 else None,
                },
                "classification": tp.clean_value(meta.get("classification")),
            },
            "document_control": {
                "document_title": tp.clean_value(meta.get("document_title")),
                "document_id": tp.clean_value(meta.get("document_id")),
                "document_version": tp.clean_value(meta.get("document_version")),
                **{role: self._signoff(meta.get(role), team)
                   for role in ("prepared_by", "reviewed_by", "approved_by", "released_by")},
                "release_date": tp.date_field(meta.get("release_date")),
                "change_history": self._change_history(tables),
                "distribution_list": self._distribution_list(tables),
            },
            "engagement_scope": {
                "assets": self._assets(tables),
                "scope_updated_till": tp.date_field(meta.get("scope_updated_till")),
                "exclusions": self._exclusions(markdown),
                "testing_credentials": [],
            },
            "auditing_team": team,
            "audit_timeline": {"assessment_start_date": start, "assessment_end_date": end},
            "methodology": {"standards_referred": self._standards(markdown)},
            "tools_used": self._tools(tables),
            "executive_summary": {
                "total_findings": len(observations),
                "severity_count": _severity_count(observations),
                "narrative": self._executive_narrative(markdown),
                "summary_table": [
                    {
                        "sr_no": i,
                        "finding_id": obs["finding_id"],
                        "affected_asset": obs["affected_asset"][0] if obs["affected_asset"] else None,
                        "title": obs["title"],
                        "cwe": obs["cwe"][0].split(":")[0].strip() if obs["cwe"] else None,
                        "severity": obs["severity"],
                        "status": obs["status"],
                        "new_or_repeat": obs["new_or_repeat"],
                    }
                    for i, obs in enumerate(observations, 1)
                ],
            },
            "detailed_observations": observations,
            "appendices": {"risk_rating_criteria": [], "retest_closure": []},
        }
        return data

    # ------------------------------------------------------------------ labels

    def _collect_labels(self, markdown: str, tables: List[tp.MdTable]) -> Dict[str, str]:
        found: Dict[str, str] = {}

        # 1. Two-column key/value table rows ("| Prepared by | | | Dev Rana |").
        for table in tables:
            for row in table.rows:
                cells = tp.compact(row)
                if len(cells) == 2:
                    field = META_LABELS.get(tp.norm_key(cells[0]))
                    if field and field not in found and tp.norm_key(cells[1]) not in META_LABELS:
                        found[field] = cells[1]
            # A header row of label cells followed by a row of values.
            for header, values in zip(table.rows, table.rows[1:]):
                keys = [META_LABELS.get(tp.norm_key(c)) for c in header]
                if all(keys) and len(keys) == len(values) and len(keys) > 1:
                    for field, value in zip(keys, values):
                        if tp.clean_value(value):
                            found.setdefault(field, value)

        # 2. Text lines: "Label: value" or "Label" followed by the value on the next line.
        lines = tp.prose_lines(markdown)
        for i, line in enumerate(lines):
            m = re.match(r"^(.{2,60}?)\s*:\s*(\S.*)$", line)
            if m and (field := META_LABELS.get(tp.norm_key(m.group(1)))):
                found.setdefault(field, m.group(2))
                continue
            field = META_LABELS.get(tp.norm_key(line))
            if field and field not in found and i + 1 < len(lines):
                # Consecutive label lines are a flattened header row ("Start Date / End Date /
                # <date> / <date>"); pairing each label with the next line would misassign them.
                prev_is_label = i > 0 and tp.norm_key(lines[i - 1]) in META_LABELS
                nxt = lines[i + 1]
                if not prev_is_label and tp.norm_key(nxt) not in META_LABELS:
                    found[field] = nxt
        return found

    def _signoff(self, raw: Optional[str], team: List[Dict[str, Any]]) -> Dict[str, Any]:
        name = tp.clean_value(raw)
        sr_no = None
        if name:
            lowered = name.lower()
            for member in team:
                member_name = (member.get("name") or "").lower()
                if member_name and (lowered in member_name or member_name in lowered):
                    sr_no = member["sr_no"]
                    break
        return {"name": name, "auditing_team_sr_no": sr_no}

    def _report_title(self, markdown: str) -> Optional[str]:
        """First line on page 1 that reads like a report title."""
        first_page = markdown.split("<!-- PAGE_END: 1 -->")[0]
        for line in tp.prose_lines(first_page)[:15]:
            if re.search(r"\b(Report|Assessment)\s*$", line, re.IGNORECASE) and tp.norm_key(line) not in META_LABELS:
                if not line.lower().startswith("# document transcript"):
                    return tp.clean_value(line.lstrip("# "))
        return None

    def _timeline_date(self, markdown: str, which: int) -> Optional[str]:
        """Dates listed after an 'Assessment Start Date / Assessment End Date' header pair."""
        m = re.search(r"Assessment\s+Start\s+Date\s*\n\s*Assessment\s+End\s+Date\s*\n(.{0,200})",
                      markdown, re.IGNORECASE | re.DOTALL)
        if not m:
            return None
        dates = tp.find_dates(m.group(1))
        return dates[which] if len(dates) > which else None

    # ------------------------------------------------------------------ sections

    def _section(self, markdown: str, heading: str, stop: str) -> Optional[str]:
        """Text under the last heading-like line matching ``heading`` (skips the TOC)."""
        starts = list(re.finditer(rf"(?im)^[ \t]*(?:#{{1,6}}\s*)?(?:\d+(?:\.\d+)*\.?\s*)?(?:{heading})[ \t]*:?[ \t]*$",
                                  markdown))
        if not starts:
            return None
        begin = starts[-1].end()
        end_m = re.search(rf"(?im)^[ \t]*(?:#{{1,6}}\s*)?(?:\d+(?:\.\d+)*\.?\s*)?(?:{stop})\b", markdown[begin:])
        return markdown[begin: begin + end_m.start()] if end_m else markdown[begin:]

    def _standards(self, markdown: str) -> List[str]:
        section = self._section(
            markdown,
            r"(?:Audit\s+)?Methodology.*|Standards?\s+(?:Referred|Followed).*|Criteria.*Standard.*",
            r"Tools|Executive\s+Summary|Detailed\s+Observations",
        )
        if not section:
            return []
        return [name for name, pattern in STANDARDS if re.search(pattern, section, re.IGNORECASE)]

    def _exclusions(self, markdown: str) -> List[str]:
        section = self._section(
            markdown, r"(?:Exclusions?|Out[\s-]of[\s-]Scope(?:\s+Items)?)",
            r"Details\s+of\s+Auditing|Audit\s+Activities|Methodology|Tools|Executive\s+Summary",
        )
        if not section:
            return []
        items = [tp.clean_value(l.lstrip("•-* ")) for l in tp.prose_lines(section)]
        return [i for i in items if i][:50]

    def _executive_narrative(self, markdown: str) -> Optional[str]:
        section = self._section(markdown, r"Executive\s+Summary", r"Detailed\s+Observations|Appendi")
        if not section:
            return None
        paragraph: List[str] = []
        for line in tp.prose_lines(section):
            if re.fullmatch(r"\d{1,3}", line):
                break  # start of the summary table's text rendering
            paragraph.append(line)
        return tp.clean_value(" ".join(paragraph)) if paragraph else None

    # ------------------------------------------------------------------ tables

    @staticmethod
    def _table_text(table: tp.MdTable, rows: int = 4) -> str:
        return " ".join(" ".join(r) for r in table.rows[:rows]).lower()

    def _auditing_team(self, tables: List[tp.MdTable]) -> List[Dict[str, Any]]:
        team: List[Dict[str, Any]] = []
        seen = set()
        for table in tables:
            if "distribution" in self._table_text(table) or "organization" in self._table_text(table):
                continue
            for row in table.rows:
                cells = tp.compact(row)
                email_idx = next((i for i, c in enumerate(cells) if tp.EMAIL_RE.search(c)), None)
                if email_idx is None or tp.serial(cells[0]) is None or email_idx < 2:
                    continue
                email = tp.EMAIL_RE.search(cells[email_idx]).group(0)
                if email.lower() in seen:
                    continue
                seen.add(email.lower())
                after = [c for c in cells[email_idx + 1:] if c.lower() not in ("yes", "no")]
                team.append({
                    "sr_no": tp.serial(cells[0]),
                    "name": tp.clean_value(cells[1]),
                    "designation": tp.clean_value(" ".join(cells[2:email_idx])) if email_idx > 2 else None,
                    "email": email,
                    "certifications": tp.clean_value(after[0]) if after else None,
                })
        return team

    def _tools(self, tables: List[tp.MdTable]) -> List[Dict[str, Any]]:
        tools: List[Dict[str, Any]] = []
        seen = set()
        license_re = re.compile(r"^(licensed|open[\s-]?source|freeware|commercial|proprietary|free)$", re.IGNORECASE)
        for table in tables:
            is_tool_table = "tool" in self._table_text(table)
            for row in table.rows:
                cells = tp.compact(row)
                lic_idx = next((i for i, c in enumerate(cells) if license_re.match(c)), None)
                if lic_idx is None and not is_tool_table:
                    continue
                if len(cells) < 2 or tp.serial(cells[0]) is None:
                    continue
                name = cells[1]
                if "tool" in name.lower() and "name" in name.lower():
                    continue  # header row
                version = cells[2] if (lic_idx is None and len(cells) > 2) or (lic_idx and lic_idx > 2) else None
                key = (name.lower(), (version or "").lower())
                if key in seen:
                    continue
                seen.add(key)
                license_type = None
                if lic_idx is not None:
                    lic = cells[lic_idx].lower()
                    license_type = "Licensed" if lic == "licensed" else ("Open Source" if "open" in lic else cells[lic_idx])
                tools.append({
                    "sr_no": tp.serial(cells[0]),
                    "tool_name": tp.clean_value(name),
                    "version": tp.clean_value(version),
                    "license_type": license_type,
                })
        return tools

    def _change_history(self, tables: List[tp.MdTable]) -> List[Dict[str, Any]]:
        history = []
        for table in tables:
            text = self._table_text(table)
            if not ("version" in text and "date" in text) and "change history" not in text:
                continue
            for row in table.rows:
                cells = tp.compact(row)
                if len(cells) >= 2 and re.fullmatch(r"v?\d+(?:\.\d+)*", cells[0], re.IGNORECASE):
                    date = tp.parse_date(cells[1])
                    if not date:
                        continue
                    history.append({
                        "version": cells[0],
                        "date": date,
                        "remarks": tp.clean_value(" ".join(cells[2:])) if len(cells) > 2 else None,
                    })
        return history

    def _distribution_list(self, tables: List[tp.MdTable]) -> List[Dict[str, Any]]:
        people = []
        for table in tables:
            text = self._table_text(table)
            if "distribution" not in text and "organization" not in text:
                continue
            for row in table.rows:
                cells = tp.compact(row)
                email_idx = next((i for i, c in enumerate(cells) if tp.EMAIL_RE.search(c)), None)
                has_sr = tp.serial(cells[0]) is not None
                if email_idx is None or (has_sr and email_idx < 2):
                    continue
                body = cells[1:email_idx] if has_sr else cells[:email_idx]
                people.append({
                    "name": tp.clean_value(body[0]) if len(body) > 0 else None,
                    "organization": tp.clean_value(body[1]) if len(body) > 1 else None,
                    "designation": tp.clean_value(" ".join(body[2:])) if len(body) > 2 else None,
                    "email": tp.EMAIL_RE.search(cells[email_idx]).group(0),
                })
        return people

    def _assets(self, tables: List[tp.MdTable]) -> List[Dict[str, Any]]:
        assets: List[Dict[str, Any]] = []
        seen = set()
        for table in tables:
            n_header, header_map = self._asset_header(table.rows)
            scope_table = "description" in header_map and len(header_map) >= 2
            for row in table.rows[n_header:]:
                joined = " ".join(row)
                if re.search(r"\bCWE-\s*\d+|\b(critical|high|medium|low)\b.*\b(open|closed)\b", joined, re.IGNORECASE):
                    continue  # finding summary row, not a scope row
                urls = [tp.join_wrapped_url(c) for c in row if tp.URL_RE.match(c.strip())]
                ips = tp.IP_RE.findall(joined)
                sr_no = tp.serial(row[0]) if row else None
                if not (urls or ips) and not (scope_table and any(c.strip() for c in row)):
                    continue
                if sr_no is None and not header_map:
                    continue

                def col(name):
                    idx = header_map.get(name)
                    return tp.clean_value(row[idx]) if idx is not None and idx < len(row) else None

                description = col("description")
                if description is None and not header_map:
                    description = next((tp.clean_value(c) for c in row[1:]
                                        if c.strip() and not tp.URL_RE.match(c.strip()) and not tp.IP_RE.search(c)
                                        and c.strip().upper() != "NA"), None)
                internal = col("internal_ip") or next((ip for ip in ips if tp.is_private_ip(ip)), None)
                public = col("public_ip") or next((ip for ip in ips if not tp.is_private_ip(ip)), None)
                criticality = col("criticality")
                if criticality is None and not header_map:
                    criticality = next((c.strip().title() for c in row
                                        if c.strip().lower() in ("critical", "high", "medium", "low")), None)
                url = urls[0] if urls else (tp.join_wrapped_url(col("url")) if col("url") else None)
                key = (url or "", internal or "", public or "", description or "")
                if key == ("", "", "", "") or key in seen:
                    continue
                seen.add(key)
                assets.append({
                    "sr_no": sr_no if sr_no is not None else len(assets) + 1,
                    "asset_description": description,
                    "url": url,
                    "criticality": criticality,
                    "internal_ip": internal,
                    "public_ip": public,
                    "in_scope_functions": col("functions"),
                })
        return assets

    @staticmethod
    def _asset_header(rows: List[List[str]]) -> Tuple[int, Dict[str, int]]:
        """(number of header rows, column map) for a scope table.

        PDF tables often split one header over several rows ("Internal" / "IP"),
        so leading rows without a serial number, URL or IP are merged column-wise.
        """
        n_header, header = _merged_header(rows)
        if n_header == 0:
            return 0, {}
        patterns = {
            "description": r"asset\s+description|asset\s+name|application\s+name|host\s*name|^\s*asset\b",
            "criticality": r"critical",
            "internal_ip": r"internal\s+ip|private\s+ip",
            "public_ip": r"public\s+ip|external\s+ip",
            "url": r"\burl\b|end\s*point",
            "functions": r"function|in[\s-]scope",
        }
        mapping = _map_columns(header, patterns)
        return (n_header, mapping) if len(mapping) >= 2 else (0, {})

    # ------------------------------------------------------------------ findings

    def _observations(self, markdown: str) -> List[Dict[str, Any]]:
        headers = self._finding_headers(markdown)
        if not headers:
            # Some templates only list findings in a table (title/severity/CWE/...).
            return self._table_observations(tp.parse_tables(markdown))
        appendix = None
        for m in _APPENDIX_RE.finditer(markdown):
            if m.start() > headers[-1][0]:
                appendix = m.start()
                break

        observations = []
        for i, (_, body_start, number, title) in enumerate(headers):
            end = headers[i + 1][0] if i + 1 < len(headers) else (appendix or len(markdown))
            observations.append(self._observation(number, title, markdown[body_start:end]))
        return observations

    def _finding_headers(self, markdown: str) -> List[Tuple[int, int, str, Optional[str]]]:
        found = []
        offset = 0
        prev_line = ""
        for line in markdown.splitlines(keepends=True):
            stripped = line.strip()
            # A header directly under a short-value label is that label's value ("Reference\nCase I").
            lm = _LABEL_RES[0].match(prev_line) if prev_line else None
            prev_is_label = (bool(lm) and lm.end() >= len(prev_line)
                             and lm.lastgroup in ("reference", "finding_id", "title", "affected_asset"))
            for pattern, window_size in _FINDING_HEADER_RES:
                m = pattern.match(line.rstrip("\r\n"))
                if not m:
                    continue
                window = markdown[offset + len(line): offset + len(line) + window_size]
                # Finding titles are not sentences; numbered prose ("1. Possible (Medium): ...
                # not expected.") in methodology sections is.
                is_sentence = m.group("title").rstrip("* ").endswith(".")
                # "1. Affected URL/IP address" is a numbered field label, not a finding.
                tm = _LABEL_RES[0].match(m.group("title").strip())
                is_label = bool(tm) and tm.end() >= len(m.group("title").strip()) - 1
                if not prev_is_label and not is_sentence and not is_label and _SEVERITY_OR_STATUS_RE.search(window):
                    title = tp.clean_value(m.group("title").strip("*# "))
                    found.append((offset, offset + len(line), m.group("num"), title))
                break
            offset += len(line)
            if stripped and not tp.IMAGE_TOKEN_RE.match(stripped):
                prev_line = stripped
        return found

    _FINDING_COLUMNS = {
        "sr": r"^\s*(?:s\.?\s*no|sr|sl|#)",
        "title": r"observation\s+title|vulnerability\s+(?:name|title)|finding\s+title|name\s+of\s+(?:the\s+)?vulnerab"
                 r"|^\s*(?:observations?|vulnerabilit(?:y|ies)|findings?|title|issue)\s*$",
        "severity": r"severity|risk\s+rating|^\s*risk\s*$",
        "cwe": r"cwe|cve",
        "asset": r"affected|asset|\burl\b|\bip\b|host",
        "recommendation": r"recommend|remediation|mitigation",
        "status": r"status",
        "new_or_repeat": r"new\s*(?:or|/)\s*repeat",
        "impact": r"impact",
        "reference": r"reference",
        "complied": r"complied",
    }

    def _table_observations(self, tables: List[tp.MdTable]) -> List[Dict[str, Any]]:
        observations: List[Dict[str, Any]] = []
        mapping: Dict[str, int] = {}
        width = 0
        for table in tables:
            n_header, header = _merged_header(table.rows)
            new_map = _map_columns(header, self._FINDING_COLUMNS) if n_header else {}
            if "title" in new_map and "severity" in new_map:
                mapping, width = new_map, max(len(r) for r in table.rows)
            elif n_header == 0 and mapping and len(table.rows[0]) == width:
                pass  # headerless table continuing the previous findings table onto a new page
            else:
                mapping = {}
            for row in table.rows[n_header:]:
                row_map = mapping or _summary_row_columns(row)
                if not row_map:
                    continue

                def col(name, row=row, row_map=row_map):
                    idx = row_map.get(name)
                    return tp.clean_value(row[idx]) if idx is not None and idx < len(row) else None

                title = col("title")
                severity = _normalise_severity(col("severity"))
                if not title or severity is None:
                    continue
                if (col("complied") or "").lower() == "complied":
                    continue  # configuration check that passed
                cwe_cell = col("cwe") or ""
                sr = tp.serial(row[row_map["sr"]]) if row_map.get("sr", 99) < len(row) else None
                observations.append({
                    "finding_id": str(sr if sr is not None else len(observations) + 1),
                    "title": title,
                    "status": _normalise_status(col("status")),
                    "severity": severity,
                    "impact_level": None,
                    "likelihood_level": None,
                    "cve_id": sorted({c.upper() for c in tp.CVE_RE.findall(cwe_cell)}),
                    "cvss_score": None,
                    "cvss_vector": None,
                    "severity_rationale": None,
                    "reported_epss_score": None,
                    "observation_date": None,
                    "cwe": _split_cwes(re.sub(r"CWE-\s+(\d)", r"CWE-\1", cwe_cell)),
                    "affected_asset": [a for a in [col("asset")] if a and a.upper() != "NA"],
                    "regulatory_references": [],
                    "observation_description": None,
                    "preconditions": None,
                    "proof_of_concept": [],
                    "impact": col("impact"),
                    "likely_root_cause": None,
                    "recommendation": col("recommendation"),
                    "reference": col("reference"),
                    "new_or_repeat": _pick(col("new_or_repeat"), ("New", "Repeat"), {"repeated": "Repeat"}),
                })
        return observations

    def _observation(self, number, title, body) -> Dict[str, Any]:
        fields: Dict[str, str] = {}
        label_pos: Dict[str, int] = {}
        matches = _label_matches(body)
        for j, m in enumerate(matches):
            key = m.lastgroup
            value_end = matches[j + 1].start() if j + 1 < len(matches) else len(body)
            if key not in fields:
                fields[key] = body[m.end():value_end]
                label_pos[key] = m.start()

        def text(key):
            return tp.prose(fields[key]) if key in fields else None

        cve_cwe_text = tp.clean_value(" ".join(tp.prose_lines(fields.get("cve_cwe", ""))))
        cwe_source = cve_cwe_text or " ".join(tp.prose_lines(body))
        cvss_text = text("cvss") or ""
        cvss_m = re.search(r"\b(10(?:\.0)?|\d(?:\.\d)?)\b", cvss_text)
        vector_m = tp.CVSS_VECTOR_RE.search(fields.get("cvss_vector", "") or body)
        epss_m = re.search(r"\b(0?\.\d+|1(?:\.0+)?)\b", text("epss") or "")

        return {
            "finding_id": tp.clean_value(text("finding_id")) or str(number),
            "title": title or tp.clean_value(text("title")),
            "status": _normalise_status(text("status")),
            "severity": _normalise_severity(text("severity")),
            "impact_level": _pick(text("impact_level"), ("Major", "Moderate", "Minor")),
            "likelihood_level": _pick(text("likelihood_level"), ("Easy", "Moderate", "Hard")),
            "cve_id": sorted({c.upper() for c in tp.CVE_RE.findall(cve_cwe_text or body)}),
            "cvss_score": float(cvss_m.group(1)) if cvss_m else None,
            "cvss_vector": vector_m.group(0) if vector_m else None,
            "severity_rationale": text("severity_rationale"),
            "reported_epss_score": float(epss_m.group(1)) if epss_m else None,
            "observation_date": tp.date_field(text("observation_date")),
            "cwe": _split_cwes(cwe_source),
            "affected_asset": _split_items(fields.get("affected_asset")),
            "regulatory_references": _split_items(fields.get("regulatory_references")),
            "observation_description": text("observation_description"),
            "preconditions": text("preconditions"),
            "proof_of_concept": self._proof_of_concept(fields, label_pos, body),
            "impact": text("impact"),
            "likely_root_cause": text("likely_root_cause"),
            "recommendation": text("recommendation"),
            "reference": text("reference"),
            "new_or_repeat": _pick(text("new_or_repeat"), ("New", "Repeat"), {"repeated": "Repeat", "recurring": "Repeat"}),
        }

    @staticmethod
    def _proof_of_concept(fields, label_pos, body) -> List[Dict[str, Any]]:
        """Image tokens in the finding body, flagged as retest evidence when they follow
        a 'Revalidation/Retest Proof of Concept' label, plus any PoC text."""
        retest_pos = label_pos.get("retest_poc")
        entries: List[Dict[str, Any]] = []

        poc_text = tp.prose(fields["poc"]) if "poc" in fields else None
        if poc_text:
            entries.append({"type": "text", "reference": None, "is_retest": False, "description": poc_text})

        seen = set()
        for m in tp.IMAGE_TOKEN_RE.finditer(body):
            if m.group(0) in seen:
                continue
            seen.add(m.group(0))
            is_retest = retest_pos is not None and m.start() >= retest_pos
            entries.append({"type": "image", "reference": m.group(0), "is_retest": is_retest, "description": None})

        retest_text = tp.prose(fields["retest_poc"]) if "retest_poc" in fields else None
        if retest_text:
            entries.append({"type": "text", "reference": None, "is_retest": True, "description": retest_text})

        return [
            {"sr_no": i, "type": e["type"], "reference": e["reference"], "capture_date": None,
             "is_retest": e["is_retest"], "redacted": None, "description": e["description"]}
            for i, e in enumerate(entries, 1)
        ]


# --------------------------------------------------------------------------- table headers

_SEVERITY_WORD_RE = re.compile(r"\b(critical|high|medium|low|informational)\b", re.IGNORECASE)


def _merged_header(rows: List[List[str]]) -> Tuple[int, List[str]]:
    """Merge leading header rows column-wise (PDF tables often split "Internal" / "IP").

    Header rows are the leading rows without a serial number, URL, IP, severity
    word or long cell text; at most four are merged.
    """
    n = 0
    while n < min(4, len(rows) - 1):
        row = rows[n]
        joined = " ".join(row)
        if (tp.serial(row[0]) is not None or tp.URL_RE.search(joined) or tp.IP_RE.search(joined)
                or (n > 0 and _SEVERITY_WORD_RE.search(joined)) or max((len(c) for c in row), default=0) > 60):
            break
        n += 1
    if n == 0:
        return 0, []
    width = max(len(r) for r in rows[:n])
    return n, [" ".join(r[i] for r in rows[:n] if i < len(r)).strip() for i in range(width)]


def _summary_row_columns(row: List[str]) -> Dict[str, int]:
    """Column roles for a headerless findings-summary row, read from cell content.

    Only rows shaped like "| sr | asset | title | CWE-x | severity | recommendation |"
    qualify: a serial number, a CWE cell and a severity word after it are required.
    """
    if not row or tp.serial(row[0]) is None:
        return {}
    cwe_idx = next((i for i, c in enumerate(row) if re.match(r"\s*CWE-\s*\d", c, re.IGNORECASE)), None)
    if cwe_idx is None:
        return {}
    sev_idx = next((i for i in range(cwe_idx + 1, len(row)) if _normalise_severity(row[i]) in SEVERITIES), None)
    title_idx = next((i for i in range(cwe_idx - 1, 0, -1) if row[i].strip()), None)
    if sev_idx is None or title_idx is None:
        return {}
    mapping = {"sr": 0, "title": title_idx, "cwe": cwe_idx, "severity": sev_idx}
    asset_idx = next((i for i in range(1, title_idx) if row[i].strip()), None)
    if asset_idx is not None:
        mapping["asset"] = asset_idx
    rec_idx = next((i for i in range(sev_idx + 1, len(row)) if len(row[i].strip()) > 60), None)
    if rec_idx is not None:
        mapping["recommendation"] = rec_idx
    return mapping


def _map_columns(header: List[str], patterns: Dict[str, str]) -> Dict[str, int]:
    mapping: Dict[str, int] = {}
    for idx, cell in enumerate(header):
        for name, pattern in patterns.items():
            if name not in mapping and re.search(pattern, cell, re.IGNORECASE):
                mapping[name] = idx
                break
    return mapping


# --------------------------------------------------------------------------- normalisers

def _pick(value: Optional[str], allowed, synonyms: Optional[Dict[str, str]] = None) -> Optional[str]:
    if not value:
        return None
    lowered = value.lower()
    for option in allowed:
        if re.search(rf"\b{option.lower()}\b", lowered):
            return option
    for word, option in (synonyms or {}).items():
        if word in lowered:
            return option
    return value


def _normalise_severity(value: Optional[str]) -> Optional[str]:
    return _pick(value, SEVERITIES, {"info": "Informational", "moderate": "Medium"})


def _normalise_status(value: Optional[str]) -> Optional[str]:
    return _pick(value, ("Partially Remediated", "Open", "Closed"),
                 {"partial": "Partially Remediated", "remediated": "Closed", "fixed": "Closed", "resolved": "Closed"})


def _split_cwes(text: str) -> List[str]:
    text = re.sub(r"\s+", " ", text or "")
    out: List[str] = []
    for m in re.finditer(r"CWE-\d+(?:\s*[:\-–]\s*[^•\n]*?)?(?=\s*(?:•|CWE-\d|$|\s(?:Affected|Recommendation|Impact)\b))",
                         text, re.IGNORECASE):
        value = m.group(0).strip(" ,;")
        if value.upper() not in (o.upper() for o in out):
            out.append(value)
    return out


def _split_items(raw: Optional[str]) -> List[str]:
    if not raw:
        return []
    items = [tp.clean_value(part) for part in re.split(r"\n|•", tp.prose(raw) or "")]
    return [i for i in items if i and i.upper() != "NA"]


def _severity_count(observations: List[Dict[str, Any]]) -> Dict[str, int]:
    # Only the buckets the master schema defines; other severities stay on their finding.
    from .schema import template

    counts = {key: 0 for key in template()["executive_summary"]["severity_count"]}
    for obs in observations:
        if obs["severity"] and obs["severity"].lower() in counts:
            counts[obs["severity"].lower()] += 1
    return counts
