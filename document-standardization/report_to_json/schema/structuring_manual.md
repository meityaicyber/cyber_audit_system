# Structuring manual

Guidance handed to the model in pass 2, section by section. It describes where content comes from and
what is forbidden. It deliberately contains no sample values or worked examples: models copy the
specifics of examples. Keep it that way; a test rejects example phrasing.

Format: each top-level heading is one block. Field bullets name the field path relative to the section,
with `[]` marking list items.

# Guardrails

1. Every value comes from the transcript. If the transcript does not state something, the field is null, or an empty list for list fields. Never invent, estimate, default or fill a value from your own knowledge.
2. Do not compute or derive values. Do not count findings to fill a total, tally severities to fill counts, derive impact or likelihood levels from a severity, derive a CVSS score or vector, or work out a CWE or CVE from a vulnerability's name or description.
3. The only transformations allowed are formatting: dates are written as YYYY-MM-DD when the transcript gives a complete date, and a listed value may differ from the report's wording only in letter case or spacing.
4. Record the report's own statements even when they contradict each other. If the summary and the detailed findings disagree, keep each as stated in its own place. Never correct, reconcile or complete the report.
5. Each piece of information goes where the report gives it. Detailed-finding fields are filled only from that finding's detailed description; summary-table fields only from the summary table. Never copy between them to fill a gap.
6. Narrative fields carry the report's complete wording for that field. Do not summarise, shorten, paraphrase, translate, correct spelling, or combine text from different places.
7. Identifiers are copied character for character: finding identifiers, CVE and CWE identifiers, URLs, IP addresses, e-mail addresses, version strings and names. Do not reformat, expand or complete them.
8. Fields with listed values take exactly one listed value. When the report's term is not one of them, the field is null; never substitute the closest option or a synonym.
9. Number fields take a number the report prints. A range, a word, or a number with qualifying text means null.
10. Image tags of the form [IMAGE_PAGE_<page>_FIG_<n>] are pointers to stored images. Copy them exactly and only into proof_of_concept[].reference. Never create a tag, and never describe what an image shows: you cannot see the images.
11. Running headers and footers, page numbers, the table of contents and the report's own section headings are not values, except where a field asks for a title or a classification marking.
12. Content that fits no field is left out. Never place text in an unrelated field to avoid losing it; unplaced text is preserved separately.
13. Never copy passwords, secrets, tokens, keys or one-time codes into any field, even when the report prints them.
14. Use only the keys shown in the requested structure. Do not add, rename or nest keys differently.

# report_meta

- `report_id`: the identifier the report assigns to itself as its report number or report ID. An identifier given only in the document-control table belongs in document_control.document_id instead.
- `report_title`: the report's title as printed on its cover or title page.
- `report_type`: the type of assessment or audit as the report names it, verbatim.
- `report_release_date`: the date the report states it was released or issued.
- `report_version`: a version the report labels as the version of the report itself. A version printed only in the document-control table belongs in document_control.document_version, and this field stays null.
- `audit_type`: the report's statement of whether this is an initial audit or a follow-up or re-audit, verbatim.
- `audit_period.from`: the start of the period the report labels as the audit period.
- `audit_period.to`: the end of that audit period. Testing dates stated separately belong in audit_timeline.
- `classification`: the confidentiality or classification marking the report applies to itself, whether stated in its details or printed as a marking on its pages.

# document_control

- `document_title`: the title given in the document-control or document-preparation table.
- `document_id`: the document identifier given in that table.
- `document_version`: the document version given in that table.
- `prepared_by.name`: the person the report names as having prepared the document.
- `prepared_by.auditing_team_sr_no`: the auditing-team serial number of that same person, only when exactly one team member's name corresponds to the name given (a shortened form of the same name counts); otherwise null.
- `reviewed_by.name`: the person named as reviewer.
- `reviewed_by.auditing_team_sr_no`: the reviewer's auditing-team serial number, under the same matching rule.
- `approved_by.name`: the person named as approver.
- `approved_by.auditing_team_sr_no`: the approver's auditing-team serial number, under the same matching rule.
- `released_by.name`: the person named as having released or issued the document.
- `released_by.auditing_team_sr_no`: that person's auditing-team serial number, under the same matching rule.
- `release_date`: the release date recorded in document control.
- `change_history[]`: one entry per row of the change or revision history, in order.
- `change_history[].version`: that row's version.
- `change_history[].date`: that row's date.
- `change_history[].remarks`: that row's remarks or reason for change.
- `distribution_list[]`: one entry per recipient in the distribution list.
- `distribution_list[].name`: the recipient's name.
- `distribution_list[].organization`: the recipient's organisation.
- `distribution_list[].designation`: the recipient's designation or role.
- `distribution_list[].email`: the recipient's e-mail address.

# engagement_scope

- `assets[]`: one entry per row of the in-scope asset table, in order. Assets named only inside findings are not scope assets.
- `assets[].sr_no`: the row's serial number as printed.
- `assets[].asset_description`: the asset name or description column.
- `assets[].url`: the URL or endpoint column, joined back together if the transcript breaks it across lines.
- `assets[].criticality`: the asset's criticality as printed.
- `assets[].internal_ip`: the value in the column the report labels as internal or private IP. Never decide yourself whether an address is internal.
- `assets[].public_ip`: the value in the column the report labels as public or external IP.
- `assets[].in_scope_functions`: the functions, modules or features the report lists as in scope for that asset.
- `scope_updated_till`: the date up to which the report says its scope list is current.
- `exclusions[]`: each item the report explicitly declares out of scope or excluded. If the report explicitly states there are no exclusions, record that statement as the single entry. Assumptions and limitations are not exclusions unless the report calls them exclusions or out of scope.
- `testing_credentials[]`: one entry per test account or role the report says was used for testing.
- `testing_credentials[].role`: the role, privilege level or persona of that account.
- `testing_credentials[].account_identifier`: the account's username or identifier only.
- `testing_credentials[].auth_type`: how that account authenticated, as the report describes it.
- `testing_credentials[].purpose`: why the report says the account was used.

# auditing_team

- `sr_no`: the member's serial number as printed.
- `name`: the member's name.
- `designation`: the member's designation or role.
- `email`: the member's e-mail address.
- `certifications`: the full text of the member's qualifications or certifications cell.
- One entry per member of the auditing-team table, in order. Table columns without a matching field are left out.

# audit_timeline

- `assessment_start_date`: the date the report gives as the start of the assessment or testing activity.
- `assessment_end_date`: the date the report gives as the end of the assessment or testing activity. The report release date and the audit period are separate fields.

# methodology

- `standards_referred[]`: each standard, framework, guideline or benchmark the report says the audit followed or referred to, one per entry, named as in the report. Tools, methodology steps, and standards cited only as a reference inside a single finding are not included.

# tools_used

- `sr_no`: the tool's serial number as printed.
- `tool_name`: the tool's name.
- `version`: the version exactly as printed.
- `license_type`: the licence type only when the report states open source or licensed; any other licensing term means null.
- One entry per row of the tools table, in order.

# executive_summary

- `total_findings`: the total number of findings the report itself states in its summary. Never count.
- `severity_count.critical`: the number of critical findings the report states in its summary. Never count.
- `severity_count.high`: the number of high findings the report states in its summary.
- `severity_count.medium`: the number of medium findings the report states in its summary.
- `severity_count.low`: the number of low findings the report states in its summary. Severity levels without a key here are left out.
- `narrative`: the complete prose of the executive summary, excluding the summary table.
- `summary_table[]`: one entry per row of the report's findings summary table, in order, each value taken from that row only and never from the detailed findings.
- `summary_table[].sr_no`: the row's serial number.
- `summary_table[].finding_id`: the row's finding identifier.
- `summary_table[].affected_asset`: the row's complete affected-asset text.
- `summary_table[].title`: the row's title.
- `summary_table[].cwe`: the row's CWE text.
- `summary_table[].severity`: the row's severity.
- `summary_table[].status`: the row's status.
- `summary_table[].new_or_repeat`: whether the row marks the finding as new or repeat.

# detailed_observations

- Fill every field only from this finding's own detailed description, including the evidence that follows it.
- `finding_id`: the identifier printed for this finding; if the report only numbers its findings, the number as printed.
- `title`: the finding's title.
- `status`: the finding's current status as stated in its description.
- `severity`: the severity or risk rating stated for this finding.
- `impact_level`: only when the report states this finding's impact level in those terms; never derived from severity.
- `likelihood_level`: only when the report states this finding's likelihood or ease of exploitation in those terms; never derived from severity.
- `cve_id[]`: each CVE identifier stated for this finding, one per entry.
- `cvss_score`: the CVSS score printed for this finding.
- `cvss_vector`: the CVSS vector string printed for this finding.
- `severity_rationale`: text the report gives specifically to justify this finding's severity. The report's general risk-rating definitions are not a rationale.
- `reported_epss_score`: an EPSS score the report states for this finding.
- `observation_date`: the date this finding was observed or identified, when stated.
- `cwe[]`: each CWE stated for this finding, one per entry, as written including its name when the report gives one.
- `affected_asset[]`: each URL, endpoint, IP address, host, application or component the report lists as affected by this finding, one per entry, together with any label the report attaches to it.
- `regulatory_references[]`: each regulation, compliance requirement or standard the report cites for this finding specifically.
- `observation_description`: the complete description or observation text.
- `preconditions`: the stated prerequisites or conditions for exploiting the finding.
- `proof_of_concept[]`: one entry per evidence item of this finding, in order.
- `proof_of_concept[].sr_no`: the item's position within this finding's evidence, counting from 1.
- `proof_of_concept[].type`: image for an image tag; text for textual evidence, meaning written steps, requests or responses.
- `proof_of_concept[].reference`: the image tag for image evidence; null for text evidence.
- `proof_of_concept[].capture_date`: a capture date the report states for that item.
- `proof_of_concept[].is_retest`: true for evidence the report places under a retest or revalidation heading; false otherwise.
- `proof_of_concept[].redacted`: only when the report states whether that item is redacted.
- `proof_of_concept[].description`: the caption or text the report gives for that item, verbatim. Never a description of an image's contents.
- `impact`: the complete impact text.
- `likely_root_cause`: text the report presents as the root cause or cause of the finding.
- `recommendation`: the complete recommendation or remediation text.
- `reference`: the references or links the report cites for this finding, as printed.
- `new_or_repeat`: whether the report marks this finding as new or repeat.

# appendices

- `risk_rating_criteria[]`: one entry per rating level the report defines, in order.
- `risk_rating_criteria[].rating`: the rating level's name.
- `risk_rating_criteria[].description`: the report's definition of that rating level, verbatim.
- `risk_rating_criteria[].impact_level`: the impact level the report's rating matrix maps to that rating, only when the report states the mapping.
- `risk_rating_criteria[].likelihood_level`: the likelihood level the report's rating matrix maps to that rating, only when the report states the mapping.
- `retest_closure[]`: one entry per retest or closure record the report gives for a finding.
- `retest_closure[].finding_id`: the finding the record refers to.
- `retest_closure[].retest_date`: the date of the retest.
- `retest_closure[].closure_evidence_ref`: the number of the evidence item the report cites as proof of closure, only when cited.
- `retest_closure[].status`: the status the record gives.

# findings index

- A finding is an individual vulnerability or observation that has its own detailed description in the report.
- List each finding once, in the order of the detailed findings section.
- Rows that appear only in a summary table, methodology or process steps, section headings, risk-rating definitions, and checklist items the report marks as compliant or passed are not findings.
- `finding_id`: the identifier printed for the finding, or null when none is printed.
- `title`: the finding's title as printed in its detailed description.
- `start_page`: the page where the finding's detailed description begins.
- `end_page`: the last page of the finding's description, including its evidence.
