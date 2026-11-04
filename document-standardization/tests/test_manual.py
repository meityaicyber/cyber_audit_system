"""The structuring manual: complete for the schema, sent to the right calls, and free of examples."""

import re

import pytest

from report_to_json import schema, vlm
from report_to_json.schema import manual

# Phrasing that introduces examples. The manual and prompts give rules only: models copy the
# specifics of examples into their output.
EXAMPLE_PHRASES = re.compile(r"\b(e\.g\.|i\.e\.|for example|for instance|such as|example|like this)\b", re.IGNORECASE)


def _paths(node, prefix=""):
    """Documentable field paths of a template section, relative to that section."""
    if isinstance(node, dict):
        for key, sub in node.items():
            path = f"{prefix}.{key}" if prefix else key
            if isinstance(sub, (dict, list)) and not (isinstance(sub, list) and not isinstance(sub[0], dict)):
                yield from _paths(sub, path)
            else:
                yield path + ("[]" if isinstance(sub, list) else "")
    elif isinstance(node, list):
        if prefix:
            yield prefix + "[]"
        yield from _paths(node[0], prefix + "[]" if prefix else "")


@pytest.mark.parametrize("section", list(schema.template()))
def test_every_schema_field_is_documented(section):
    text = manual.blocks()[section]
    documented = set(re.findall(r"^- `([^`]+)`", text, re.MULTILINE))
    missing = [p for p in _paths(schema.template()[section]) if p not in documented]
    assert missing == [], f"{section}: no manual entry for {missing}"


def test_manual_documents_only_real_fields():
    for section in schema.template():
        valid = set(_paths(schema.template()[section]))
        for path in re.findall(r"^- `([^`]+)`", manual.blocks()[section], re.MULTILINE):
            assert path in valid, f"{section}: manual documents unknown field {path!r}"


def test_model_facing_text_contains_no_examples():
    model_facing = {name: body for name, body in manual.blocks().items() if name != "Structuring manual"}
    model_facing.update({
        "TRANSCRIBE_PROMPT": vlm.TRANSCRIBE_PROMPT, "RETRY_NOTE": vlm.RETRY_NOTE,
        "STRUCTURE_PROMPT": vlm.STRUCTURE_PROMPT, "FINDING_INSTRUCTION": vlm.FINDING_INSTRUCTION,
        "INDEX_INSTRUCTION": vlm.INDEX_INSTRUCTION,
        **{f"SECTIONS[{name}]": text for name, _, text in vlm.SECTIONS},
    })
    offenders = {name: EXAMPLE_PHRASES.findall(text) for name, text in model_facing.items()}
    assert {k: v for k, v in offenders.items() if v} == {}
    # No concrete image tag either: tags are described by their format only.
    assert not any(re.search(r"\[IMAGE_PAGE_\d+_FIG_\d+\]", text) for text in model_facing.values())


def test_each_call_gets_its_own_guide_and_the_guardrails(report_pdf, tmp_path):
    from report_to_json.pipeline import DocumentPipeline
    from report_to_json.storage import LocalDeepStorage
    from test_pipeline import perfect_model

    backend = perfect_model(report_pdf)
    DocumentPipeline(backend=backend, storage=LocalDeepStorage(tmp_path / "s")).process_file(report_pdf, tmp_path)
    prompts = {re.search(r"TASK: (.+)", c["prompt"]).group(1): c["prompt"]
               for c in backend.calls if c["image"] is None}

    finding_rule = "- `severity_rationale`: text the report gives specifically"
    front_rule = "- `report_title`: the report's title"
    index_rule = "A finding is an individual vulnerability"
    assert front_rule in prompts["extract the front matter"]
    assert finding_rule not in prompts["extract the front matter"]
    assert finding_rule in prompts["extract finding 1"] and front_rule not in prompts["extract finding 1"]
    assert index_rule in prompts["index the findings"]
    assert all(manual.guardrails() in p for p in prompts.values())
    # Guide and guardrails come after the transcript, so the shared prefix stays cacheable.
    p = prompts["extract finding 1"]
    assert p.index("</transcript>") < p.index("FIELD GUIDE") < p.index("GUARDRAILS")


def test_guardrails_cover_the_core_prohibitions():
    rails = manual.guardrails().lower()
    for rule in ("never invent", "do not compute", "contradict", "never copy between",
                 "never substitute the closest option", "never describe what an image shows",
                 "never copy passwords", "do not add, rename"):
        assert rule in rails, rule
