# Model

The pipeline runs on one model, **NVIDIA Qwen3-VL 4B Instruct AWQ**, for both passes: pass 1 transcribes
page images and pass 2 restructures the transcript into the master schema. All inference is local; the
system is designed to run air-gapped, and no inference API is ever called.

| | |
| --- | --- |
| Model | `Qwen/Qwen3-VL-4B-Instruct-AWQ` |
| Architecture | Hybrid Mamba-Transformer mixture-of-experts, about 31B parameters with about 3B active per token |
| Input | Text and images (also audio and video, unused here) |
| Context | 256K tokens |
| Licence | NVIDIA Open Model Agreement |
| Document benchmarks | OCRBench-V2 (English) 67.0 and MMLongBench-Doc 57.5 (vendor model card) |

Reasoning traces are switched off (`enable_thinking: false`) so that transcription is literal.

The model's small active size is the main risk for pass 2, which has to place a whole report into the
schema. The pipeline is built to compensate:
- it structures one section and one finding at a time;
- on a server backend, it constrains every answer to the schema;
- it gives the model the structuring manual with each call;
- it nulls only the individual values that break the schema rather than discarding a section.

Watch `coverage.placed_in_schema`, `dropped_values` and the run `status` in the run reports
(`<name>.meta.json`) when you first run it on real reports.

## Serving

Recommended: a local OpenAI-compatible server, for example vLLM:

```bash
vllm serve models/Qwen3-VL-4B-Instruct-AWQ-4bit \
     --served-model-name Qwen/Qwen3-VL-4B-Instruct-AWQ \
     --trust-remote-code --enable-prefix-caching
```

Then set `R2J_MODEL_ENDPOINT=http://<host>:8000/v1`. With a server, the pipeline gets two things:
- **Constrained decoding:** every pass-2 response is forced to match its section's JSON Schema.
- **Prefix caching:** pass-2 prompts all start with the same transcript, so the server encodes it once
  per document instead of once per call.

The in-process Transformers backend is used when no endpoint is set and the weights exist in
`models/Qwen3-VL-4B-Instruct-AWQ-4bit` (or under `MODELS_DIR`). It has no constrained
decoding; outputs are validated and repaired with retries.

NVIDIA also publishes FP8 and NVFP4 checkpoints of this model. To use one, serve it under the same
`--served-model-name`; the pipeline only talks to the server.

## Staging the weights

The weights (about 66 GB) are not in the repository. `models/manifest.json` pins the exact revision and
every file's checksum. See [models/README.md](../models/README.md) for how to download them on a
connected machine and verify them on the air-gapped system.
