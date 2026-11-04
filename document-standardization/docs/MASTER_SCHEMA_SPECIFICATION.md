# Master Schema Reference & Standardization Specification
What every section and field of the standardized audit-report JSON contains, and why it exists.

### This document walks through the master schema field by field - every leaf value the schema defines gets its own row, none grouped away. For each, it states what the field holds and why it is there. Most fields exist because they feed a specific formula in the Cybersecurity Audit Report Benchmarking Suite - those are named explicitly by criterion (i through vii, or by sub-dimension iv.a through iv.e). A smaller number of fields are administrative or identification metadata - a row index, a document ID - that no formula reads but that the schema still needs for record-keeping, traceability, or to key one record to another. Both kinds are labelled plainly rather than dressed up as scored when they are not.

### report_meta

### Top-level identifying and administrative information about the report as a whole - not read by any scoring criterion directly, but necessary to identify, version, and route the report.

### document_control

### Version-control and sign-off information for the document itself, distinct from the audit engagement described in report_meta.

### engagement_scope

### What was actually declared in scope for testing - the ground truth that findings are checked against, and the basis for criterion i's scope-and-access-level sub-score.

### assets

### testing_credentials

### auditing_team

### The people who performed the audit. This entire section feeds criterion iii.

### audit_timeline

### The dates the assessment itself was actually carried out, as distinct from when the report was released.

### methodology

### The standards and frameworks the audit claims to have followed.

### tools_used

### The tooling used to conduct the assessment.

### executive_summary

### The report's own summary of its findings, aimed at a non-technical reader. Feeds criterion v almost entirely.

### summary_table

### detailed_observations

### The core of the report: one entry per vulnerability finding. This section feeds more of the rubric than any other - most of criterion iv, and all of criterion vi and vii.

### proof_of_concept

### appendices

### Supporting reference material and the closure record.

### risk_rating_criteria

### retest_closure

## 1. report_meta

| Field | Type | Why it's needed |
| --- | --- | --- |
| report_id | string | Unique identifier for the report; keys the benchmark's output record to this specific submission. Administrative, not scored. |
| report_title | string | Human-readable title for display and indexing. Administrative, not scored. |
| report_type | string | Declares the assessment type (API Assessment, Web VAPT, and so on). Left as free text deliberately, for categorization elsewhere; used downstream to route which sector-specific checks apply once categorized. |
| report_release_date | date | When the report was issued. One of the fallback anchors for criterion vii's observation_date when a finding does not specify its own, and an input to org-level timeliness tracking outside this rubric. |
| report_version | string | Distinguishes a first issue from a follow-up revision (for example 1.0 vs 1.1). Administrative, not scored. |
| audit_type | string | Initial vs follow-up audit, left as free text. Gives meaning to new_or_repeat on individual findings - a follow-up report re-raising a Repeat finding signals unresolved risk. |
| audit_period.from | date | Start of the calendar window the audit covers. Administrative context, supports org-level timeliness tracking. |
| audit_period.to | date | End of the calendar window the audit covers. Administrative context, supports org-level timeliness tracking. |
| classification | string | Confidentiality marking (for example Confidential). Administrative, not scored. |

---

## 2. document_control

| Field | Type | Why it's needed |
| --- | --- | --- |
| document_title | string | Internal title for the document itself, distinct from report_meta.report_title. Administrative, not scored. |
| document_id | string | Internal document identifier, distinct from report_meta.report_id. Administrative, not scored. |
| document_version | string | Tracks document-level revisions, distinct from report_meta.report_version. Administrative, not scored. |
| prepared_by | object (name, auditing_team_sr_no) | Identifies who drafted the report. The auditing_team_sr_no reference is one side of criterion iii's reviewer-distinctness check. |
| reviewed_by | object (name, auditing_team_sr_no) | Identifies who reviewed the report. Feeds criterion iii directly: this must reference a different auditing_team_sr_no than prepared_by for the report to earn full credit on reviewer distinctness. |
| approved_by | object (name, auditing_team_sr_no) | Identifies who signed off on the report. Checked for distinctness from prepared_by under the same criterion iii logic as reviewed_by. |
| released_by | object (name, auditing_team_sr_no) | Identifies who issued the final report. Administrative sign-off record; not separately scored beyond the same distinctness logic. |
| release_date | date | Cross-checked against report_meta.report_release_date for internal consistency; also a timeliness anchor. |
| change_history | array (version, date, remarks) | Revision log. Not read by any current criterion; kept as a standard audit trail so a reviewer can see what changed between versions. |
| distribution_list | array (name, organization, designation, email) | Who received the report. Administrative, not scored. |

---

## 3. engagement_scope - assets

| Field | Type | Why it's needed |
| --- | --- | --- |
| assets[].sr_no | number | Row index for the asset table. Administrative, not scored. |
| assets[].asset_description | string | Short label for the asset (for example "ICCW"). Identifies which system a finding belongs to; contributes to iv.b's asset matching alongside url. |
| assets[].url | string | The actual endpoint or address in scope. This is the specific value criterion iv.b matches every finding's affected_asset against, after normalization. |
| assets[].criticality | string | Declared business criticality of the asset (for example High). Not read by the current seven criteria, but relevant context for prioritizing findings - a natural input to a future risk-weighted composite. |
| assets[].internal_ip | string | Internal network location of the asset. Not scored directly, but helps confirm a finding's affected_asset genuinely corresponds to this scope entry rather than a look-alike host. |
| assets[].public_ip | string | Public network location of the asset. Same role as internal_ip for externally-facing assets. |
| assets[].in_scope_functions | string | Which functions or methods of the asset were in scope (for example "Full API Methods"). Feeds criterion i's scope-and-access-level sub-score alongside exclusions - narrows what "complete" testing would have covered. |

---

## 4. engagement_scope - metadata & exclusions

| Field | Type | Why it's needed |
| --- | --- | --- |
| scope_updated_till | date | When the scope table was last confirmed current. Feeds criterion i's scope-and-access-level sub-score, checked for staleness against audit_timeline.assessment_end_date. |
| exclusions | array of strings | What was explicitly not tested. Feeds criterion i: must be populated (even an explicit "none") for full credit, since a silently empty field cannot be told apart from an undisclosed gap. |

---

## 5. engagement_scope - testing_credentials

| Field | Type | Why it's needed |
| --- | --- | --- |
| testing_credentials[].role | string | Which privilege level or persona was tested (for example "Unauthenticated", "Standard Customer"). The core signal for criterion i's access-level-coverage check - multiple relevant roles should be represented for a role-differentiated API. |
| testing_credentials[].account_identifier | string | Identifies which test account was used for that role, without storing a live secret. Supports traceability; not itself scored. |
| testing_credentials[].auth_type | string | How that role authenticates (for example "OAuth Bearer Token", "MPIN + OTP"). Confirms the role was tested with realistic authentication; read alongside role for criterion i. |
| testing_credentials[].purpose | string | Why that role was included in testing. Gives the access-level-coverage check something to verify against when judging whether role coverage was deliberate rather than incidental. |

---

## 6. auditing_team

| Field | Type | Why it's needed |
| --- | --- | --- |
| sr_no | number | Row index for the team table. Administrative, not scored. |
| name | string | Feeds criterion iii's field-completeness score (FC), and is the field document_control's role objects reference by auditing_team_sr_no. |
| designation | string | Feeds criterion iii's field-completeness score; also informs whether team seniority is appropriate to engagement scope. |
| email | string | Feeds criterion iii's field-completeness score; a secondary identifier for matching against the empanelment snapshot when a name alone is ambiguous. |
| certifications | string | Feeds criterion iii's certification match-rate score (CM) directly - checked against the current CERT-In empanelment snapshot. |

---

## 7. audit_timeline

| Field | Type | Why it's needed |
| --- | --- | --- |
| assessment_start_date | date | Start of the assessment window. Used alongside assessment_end_date for criterion i's scope-staleness check and org-level timeliness tracking. |
| assessment_end_date | date | End of the assessment window. Feeds criterion i's scope-staleness check directly, and is the primary fallback anchor for criterion vii's observation_date when a finding does not specify its own. |

---

## 8. methodology

| Field | Type | Why it's needed |
| --- | --- | --- |
| standards_referred | array of strings | Feeds criterion i's standards-disclosure sub-score (S_disc) directly: the percentage of entries that match the accepted whitelist of frameworks. |

---

## 9. tools_used

| Field | Type | Why it's needed |
| --- | --- | --- |
| sr_no | number | Row index for the tools table. Administrative, not scored. |
| tool_name | string | Feeds criterion i's tool-disclosure-completeness sub-score (T_comp). |
| version | string | Feeds criterion i's tool-disclosure-completeness sub-score - a tool named without a version is treated as incompletely disclosed. |
| license_type | enum (Open Source, Licensed) | Feeds criterion i's tool-disclosure-completeness sub-score. |

---

## 10. executive_summary

| Field | Type | Why it's needed |
| --- | --- | --- |
| total_findings | number | Cross-checked against the actual count of entries in detailed_observations as part of criterion v's reconciliation gate (K). |
| severity_count | object (critical, high, medium, low) | Cross-checked against the actual severity distribution in detailed_observations; a mismatch here is exactly what criterion v's reconciliation gate is built to catch. |
| narrative | string | The free-text summary paragraph. This is what criterion v's LLM judge actually reads to grade clarity, comprehensiveness and actionability - without it there is nothing for that criterion to grade beyond a bare table. |

---

## 11. executive_summary - summary_table

| Field | Type | Why it's needed |
| --- | --- | --- |
| summary_table[].sr_no | number | Row index. Administrative, not scored. |
| summary_table[].finding_id | string | Links this row to its matching detailed_observations entry - the key criterion v's reconciliation gate matches on. |
| summary_table[].affected_asset | string | Cross-checked against the corresponding detailed_observations entry for consistency under criterion v. |
| summary_table[].title | string | Cross-checked against the corresponding detailed_observations entry for consistency under criterion v. |
| summary_table[].cwe | string | Cross-checked against the corresponding detailed_observations entry for consistency under criterion v. |
| summary_table[].severity | enum (Critical, High, Medium, Low) | Cross-checked against the corresponding detailed_observations entry; a mismatch fails criterion v's reconciliation gate. |
| summary_table[].status | enum (Open, Closed, Partially Remediated) | Cross-checked against the corresponding detailed_observations entry for consistency under criterion v. |
| summary_table[].new_or_repeat | enum (New, Repeat) | Cross-checked against the corresponding detailed_observations entry for consistency under criterion v. |

---

## 12. detailed_observations

| Field | Type | Why it's needed |
| --- | --- | --- |
| finding_id | string | Primary key. Links this finding to its summary_table row and to any matching appendices.retest_closure entries. |
| title | string | Short label, loosely cross-checked against the matching summary_table row. |
| status | enum (Open, Closed, Partially Remediated) | Feeds iv.e's closure-and-revalidation gate directly. |
| severity | enum (Critical, High, Medium, Low) | Feeds criterion vi's consistency check and the executive-summary reconciliation gate in criterion v. |
| impact_level | enum (Major, Moderate, Minor) | Optional. When present, lets criterion vi's consistency check run as a direct lookup against appendices.risk_rating_criteria instead of LLM inference from prose. |
| likelihood_level | enum (Easy, Moderate, Hard) | Optional. Paired with impact_level for the same rule-based matrix lookup under criterion vi; falls back to inference from preconditions when absent. |
| cve_id | array of strings | Feeds criterion vii: the key that drives the NVD and FIRST.org lookups. May be empty for business-logic or API findings with no assigned CVE. |
| cvss_score | number | Feeds criterion vii's delta computation against the authoritative NVD score for each listed CVE. |
| cvss_vector | string | For CVE-bearing findings, the reported vector string. For no-CVE findings, this is the manually asserted vector that severity_rationale must justify. |
| severity_rationale | string | Required for no-CVE findings under criterion vii, since there is no authoritative external score to check the asserted severity against. |
| reported_epss_score | number | Feeds criterion vii's EPSS delta computation against the authoritative FIRST.org score. |
| observation_date | date | Pins which day's EPSS snapshot to compare against. EPSS is a daily time series, so an unpinned comparison drifts on every run purely from time passing. |
| cwe | array of strings | Classifies the root-cause weakness type. Contributes to iv.a's structural-completeness check and criterion i's standards-to-finding traceability sub-score. |
| affected_asset | array of strings | Feeds iv.b: must resolve, after normalization, to a declared engagement_scope.assets entry. |
| regulatory_references | array of strings | Feeds criterion ii as the primary structured signal, rather than relying purely on NLP over the impact and recommendation prose. |
| observation_description | string | The core narrative of what was found. Feeds iv.a's completeness check and gives iv.c's proof-of-concept relevance check something concrete to verify the screenshot against. |
| preconditions | string | Prerequisite conditions for exploiting the finding. Feeds iv.a's completeness check and criterion vi's likelihood-axis inference when likelihood_level is not supplied directly. |
| impact | string | Business or technical consequence of the finding. Feeds iv.a's completeness check and criterion vi's impact-axis inference when impact_level is not supplied directly. |
| likely_root_cause | string | Feeds iv.a's completeness check and iv.d's recommendation-quality check - whether the recommendation actually addresses this stated cause. |
| recommendation | string | Feeds iv.d directly: specificity, technical correctness and actionability are all graded from this field. |
| reference | string | Any external citation or link the auditor included. Feeds iv.a's completeness check. |
| new_or_repeat | enum (New, Repeat) | Not read by any of the current seven report-level criteria. Kept because it is the natural hook for an org-level repeat-finding-rate metric later, and costs nothing to retain now. |

---

## 13. detailed_observations - proof_of_concept

| Field | Type | Why it's needed |
| --- | --- | --- |
| proof_of_concept[].sr_no | number | Row index within the finding's evidence set. Administrative, not scored. |
| proof_of_concept[].type | enum (image, text) | Determines which grading pathway applies under iv.c - image entries go through the vision-capable judge, text entries do not. |
| proof_of_concept[].reference | string | Locates the actual evidence (for example a page or figure locator) for the vision-capable model to fetch and grade under iv.c. |
| proof_of_concept[].capture_date | date | When this piece of evidence was captured. Compared against the finding's other evidence to identify which entries qualify as valid retest evidence under iv.e. |
| proof_of_concept[].is_retest | boolean | Flags whether this entry is a revalidation capture rather than original test evidence. Read directly by iv.e's closure gate. |
| proof_of_concept[].redacted | enum (Yes, No, NA) | Declares whether sensitive data in the image has been redacted; iv.c's redaction-hygiene sub-score verifies this claim against the image itself. |
| proof_of_concept[].description | string | Optional caption. Gives iv.c's relevance check additional context for what the image is meant to demonstrate. |

---

## 14. appendices - risk_rating_criteria

| Field | Type | Why it's needed |
| --- | --- | --- |
| risk_rating_criteria[].rating | string | The severity label being defined (for example "High"). Feeds criterion vi's matrix-presence gate. |
| risk_rating_criteria[].description | string | The qualitative definition of that rating. Feeds criterion vi's gate; a vague, generic description weakens the matrix's usefulness for the consistency check. |
| risk_rating_criteria[].impact_level | string | Names the impact-axis label this rating maps to. Enables the rule-based lookup version of criterion vi's consistency check when findings supply impact_level. |
| risk_rating_criteria[].likelihood_level | string | Names the likelihood-axis label this rating maps to. Enables the same rule-based lookup, paired with a finding's likelihood_level. |

---

## 15. appendices - retest_closure

| Field | Type | Why it's needed |
| --- | --- | --- |
| retest_closure[].finding_id | string | Links this closure record to its detailed_observations entry - the key iv.e cross-references on. |
| retest_closure[].retest_date | date | When the retest was performed. Must be later than the finding's original proof_of_concept evidence for iv.e to treat the closure as valid. |
| retest_closure[].closure_evidence_ref | number | Points to the specific proof_of_concept entry (by sr_no) that substantiates the retest. iv.e will not accept a closure claim without a valid reference here. |
| retest_closure[].status | enum (Open, Closed, Partially Remediated) | The authoritative closure status for this finding, read by iv.e's three-tier cap logic. |

---

