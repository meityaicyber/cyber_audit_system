# Document Standardization Pipeline

`report_to_json` is an air-gapped document standardisation pipeline for security audit reports (VAPT, network, mobile and
IoT; PDF or DOCX). It produces a single standardised JSON format defined by
[`master_schema.json`](report_to_json/schema/master_schema.json):

```
malware gate ─► PDF ─► images to deep storage (pointer tags) ─► VLM transcription ─► schema restructuring ─► JSON
```

- **One local model runs both passes:** NVIDIA Qwen3-VL 4B Instruct AWQ. No inference API is ever called.
- **Exactly the master schema.** The output JSON has precisely the structure of `master_schema.json`.
- **Nothing is dropped.** Transcription is checked against the PDF's text layer. Text that fits no schema
  field, and values the schema can't hold, are kept in a separate run report next to the JSON.
- **Nothing is invented.** Values the document doesn't state are `null`.
- **Fallback is failure.** The rule-based parser only runs when the model pipeline fails, and the output
  is then marked `fallback`.

Details:
- how each stage works: [docs/pipeline_overview.md](docs/pipeline_overview.md)
- the model and how to serve it: [docs/models.md](docs/models.md); staging the weights: [models/README.md](models/README.md)
- what each schema field means: [docs/MASTER_SCHEMA_SPECIFICATION.md](docs/MASTER_SCHEMA_SPECIFICATION.md)

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate              # Windows  (source .venv/bin/activate elsewhere)
pip install -r requirements.txt
copy .env.example .env              # then set the model endpoints / paths
```

Models run in a local inference server (recommended; see [docs/models.md](docs/models.md)) or in-process
(`pip install -r requirements.txt` and put the weights in `models/`). DOCX input needs Microsoft
Word (Windows) or LibreOffice for conversion to PDF.

## Run

```bash
python -m report_to_json      # or run_gui.bat, or python gui_app.py
```

Pick a report and press **Process report**. The model panel shows whether the model is reachable. Output goes to `outputs/`:

| Output | Contents |
| --- | --- |
| `<name>.json` | The standardised report: exactly the structure of `master_schema.json` |
| `<name>.meta.json` | Run report: status, per-page and per-section reports, gate verdicts, coverage, `unmapped_content`, `dropped_values` |
| `<name>_transcript.md` | The pass-1 transcript the JSON was built from |
| `deep_storage/manifests/<id>.json` | Image manifest: each `[IMAGE_PAGE_n_FIG_m]` tag mapped to its stored image |

## Integration

To call the pipeline from another system, use one function. It takes a report and returns the JSON:

```python
from report_to_json import standardize_report

response = standardize_report("path/to/report.pdf")      # PDF or DOCX
```

`response` is the JSON document itself, as text, with exactly the structure of `master_schema.json`.
That response is the output; it is identical to the `<name>.json` file the run also saves.

- The function returns whenever a result exists. If the model failed and the fallback produced the
  result, the JSON is still returned; the failure is logged as a warning and recorded in the run report
  (`<name>.meta.json`, `status: fallback`). Pass `strict=True` to raise `ModelPipelineFailed` instead.
- It raises only when no JSON can exist: `DocumentBlocked` when the malware pre-gate blocks the file, and
  `PipelineError` for a missing file, an unsupported type or another processing failure.
- The run's files are written to `outputs/`, or to `output_dir=...`.
- The model is set up on the first call and reused. Calls are processed one at a time.

When the caller also needs the run status or the run report, use `process_report`:

```python
from report_to_json import process_report

result = process_report("path/to/report.pdf")
result.data      # the JSON, as a dict
result.status    # "ok", "needs_review" or "fallback"
result.meta      # the run report (also saved as <name>.meta.json)
```

## Development

```bash
pip install -r requirements.txt
pytest
```

The tests use a scripted model to drive the whole route: gate, conversion order, masking, retries,
fallbacks, coverage and the GUI. No model weights or GPU are needed.

```
report_to_json/
  api.py           integration entry points: standardize_report, process_report
  pipeline.py      the route, stages 0-5, and run status
  security/        YARA pre-gate, OOXML inspection, rules/*.yar
  convert.py       DOCX -> PDF (Word or LibreOffice)
  storage.py       deep storage (content-addressed) and image manifests
  images.py        image offload, page masking with pointer tags, tag reconciliation
  vlm.py           pass 1 (transcription) and pass 2 (sectioned schema restructuring)
  backends.py      local OpenAI-compatible server / in-process Transformers
  coverage.py      page recall and transcript-to-JSON coverage
  structurer.py    rule-based fallback parser (textparse.py holds its helpers)
  transcribe.py    text-layer fallback transcription
  schema/          master template, derived JSON Schemas, validation
  gui.py           Tkinter desktop app
```

**Never commit client reports or anything derived from them.** `reports/`, `outputs/`, `deep_storage/`
and all `*.pdf` / `*.docx` files are git-ignored for that reason.
