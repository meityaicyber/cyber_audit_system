# How the pipeline works

Report-to-JSON turns security audit reports (VAPT, network, mobile, IoT) into one standardised JSON
document that follows `report_to_json/schema/master_schema.json`. The route is fixed:

```
file ─► malware gate ─► PDF ─► images to deep storage ─► pass 1 (VLM transcription) ─► pass 2 (schema) ─► completeness check ─► JSON
```

Everything goes through `DocumentPipeline.process_file`. One model, NVIDIA Qwen3-VL 4B Instruct AWQ, runs both passes
(see [models.md](models.md)).

## 0. Malware pre-gate

The file is scanned with YARA before anything parses it (`report_to_json/security/`). The gate scans:
- the raw bytes;
- for PDFs, every object dictionary as decompressed by PyMuPDF, plus every attached file;
- for DOCX files, every archive member, plus structural checks for macros, remote-template and OLE
  relationships, and executable embedded objects.

A `MALICIOUS` or `SUSPICIOUS` verdict stops processing. If YARA is unavailable, processing stops too:
the gate fails closed.

## 1. Normalise to PDF

A DOCX file is converted only after it passes the gate. Conversion runs in a child process with a
timeout, using either:
- Microsoft Word, in a private instance with macros force-disabled, read-only and no link updates; or
- LibreOffice headless, with a throw-away profile.

The resulting PDF is scanned again.

## 2. Images to deep storage

Every embedded image is stored content-addressed (SHA-256) in deep storage (`DEEP_STORAGE_DIR`). Each
placement large enough to be a figure gets a pointer tag such as `[IMAGE_PAGE_11_FIG_1]`. A
per-document manifest maps each tag to its stored object, page and position.

Placements smaller than `MIN_FIGURE_BOX_PT` (for example, a table header rasterised into thin slices)
are stored too, but left visible on the page. Masking them would hide text the model has to read.

## 3. Pass 1: vision transcription

Each page is rendered with every figure replaced by a white box showing its tag, so the model writes the
pointer exactly where the image was. The model transcribes the page verbatim to Markdown.

Completeness is checked against the PDF's own text layer, excluding text under masked figures. A page
below `PAGE_RECALL_THRESHOLD` is re-transcribed, and the model is told which words it missed. Tags
the model misreads are corrected, and tags it drops are re-added. If the model fails on a page, the
text layer is used for that page and the run is marked `fallback`.

## 4. Pass 2: restructuring into the master schema

The same model restructures the transcript one section at a time, so no response exceeds the output
limit:
1. front matter;
2. scope, team and tools;
3. executive summary;
4. appendices;
5. a findings index;
6. one call per finding, given only that finding's pages.

Each call is given two blocks from the structuring manual
([`schema/structuring_manual.md`](../report_to_json/schema/structuring_manual.md)):
- **the guardrails**, the same for every call: take values only from the transcript, no computing or
  deriving, keep the report's own contradictions, summary and detail fields filled independently, no
  near-miss listed values, never describe images, never copy secrets;
- **the field guide** for exactly the fields that call asks for: where each field's content comes from
  in a report, and what does not belong there.

The manual contains rules and definitions only, with no sample values or worked examples, because models
copy the specifics of examples. It is deliberately separate from `MASTER_SCHEMA_SPECIFICATION.md`,
whose scoring rationale ("must be populated for full credit") would push a model to fill fields.
Tests check three things:
- every schema field has a manual entry;
- no entry names a field that doesn't exist;
- no example phrasing or concrete image tag appears anywhere in the model-facing text.

Prompts start with the transcript, so a prefix-caching server encodes it once per document; the manual
blocks come after it. With a server backend, each response is constrained to its section's JSON Schema.
Otherwise responses are validated and repaired with retries. If the output still breaks the schema but
is usable, it is kept, and only the offending values are nulled and recorded. A section with no usable
output falls back to the rule-based parser, and the run is marked `fallback`.

## 5. Completeness check

The transcript is split into content (text lines and table cells) and structure. Structure is set aside
and counted in `coverage.structural_units_skipped`. It covers:
- headings and label lines, which become the `heading` of what follows;
- table-of-contents entries and column headers;
- running headers and footers, and page numbers.

Each piece of content is checked against the JSON. Dates are compared after normalisation, and field
names count as covering their labels. Content not placed in any field goes into `unmapped_content` in the run report,
so nothing from the document is lost:

```json
{"page": 4, "heading": "Assumptions", "kind": "narrative",
 "text": "Based on the scope, only the specified APIs were tested. ...", "context": null}
{"page": 5, "heading": "Details of Auditing Team", "kind": "table_data", "text": "Yes",
 "context": "column: Whether the resource has been listed on CERT-In's website; row: 1 | Ummed | Director | ..."}
```

| `kind` | Meaning |
| --- | --- |
| `narrative` | Prose the schema has no field for (introduction, assumptions, disclaimers, methodology narrative). Wrapped lines are merged into one entry per paragraph, even across page breaks. |
| `table_data` | A table value with no schema field. `context` gives its column and row. |
| `other` | Short text that fits neither of the above. |

Recurring `narrative` and `table_data` entries across reports point to gaps in the schema. The share of
content placed in schema fields is `coverage.placed_in_schema`.

Pages that fell back to the text layer render each table twice, once as a table and once as loose text,
because the rule-based parser needs both. So their `unmapped_content` is noisier, but those runs are
already marked `fallback`.

## Outputs

| File | Contents |
| --- | --- |
| `<name>.json` | **Exactly** the structure of `master_schema.json`: every key present, no other keys, every value of the declared type or `null`. |
| `<name>.meta.json` | The run report: `status`, per-page and per-section reports, gate verdicts, `coverage`, `unmapped_content`, and `dropped_values`. |

Before saving, every output is enforced against the master schema:
- **Kept after harmless normalisation:** `"7.5"` becomes `7.5`, `"high"` becomes `High`, and a full date
  becomes `YYYY-MM-DD`.
- **Set to `null` and recorded in `dropped_values` with the original:** anything else that doesn't fit.
  Examples are a severity of `Informational` (the schema lists only Critical/High/Medium/Low), a licence
  of `Freeware`, or a key the schema doesn't define.

Nothing is guessed into the schema's options, and nothing is lost.

## Run status

| `status` | Meaning |
| --- | --- |
| `ok` | Both passes ran on the model, and every check passed. |
| `needs_review` | Model output, but a check failed: low page recall, coverage below `COVERAGE_THRESHOLD`, repaired image tags, or schema issues. Details are in `status_reasons`. |
| `fallback` | **The model pipeline failed.** The text layer or the rule-based parser produced some or all of the output. The GUI shows this in red. |

The run report also records:
- the model and backend used;
- the gate verdicts, for the original file and for the converted PDF;
- per-page transcription reports (`pass1_pages`) and per-section structuring reports (`pass2_sections`);
- the image manifest path;
- validation errors and missing fields.

## The no-invention rule

Values come only from the document; anything the document doesn't state is `null`. The benchmarking
suite scores these fields (see `MASTER_SCHEMA_SPECIFICATION.md`), so an invented value would change
a report's score. The prompts forbid defaults, and the rule-based fallback never fills them in either.
