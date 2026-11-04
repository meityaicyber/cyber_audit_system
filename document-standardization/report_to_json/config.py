"""
Runtime configuration: paths, environment settings and the model registry.

The system is designed for air-gapped deployment: every model runs locally,
either behind a local OpenAI-compatible server (vLLM, SGLang, TensorRT-LLM)
or in-process with Transformers from a local weights folder. Nothing is ever
downloaded at runtime.

Every setting can be overridden from the environment (or a ``.env`` file in the
repository root, loaded by the GUI on start-up).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

PACKAGE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_DIR.parent

SCHEMA_TEMPLATE_PATH = PACKAGE_DIR / "schema" / "master_schema.json"
YARA_RULES_DIR = PACKAGE_DIR / "security" / "rules"

DEFAULT_OUTPUT_DIR = REPO_ROOT / "outputs"
DEFAULT_REPORTS_DIR = REPO_ROOT / "reports"

# Air-gapped: make every Hugging Face library refuse network access.
for _var in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_DATASETS_OFFLINE"):
    os.environ.setdefault(_var, "1")


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


def models_dir() -> Path:
    return Path(os.environ.get("MODELS_DIR", REPO_ROOT / "models"))


def deep_storage_dir() -> Path:
    """Root of the content-addressed image store."""
    return Path(os.environ.get("DEEP_STORAGE_DIR", REPO_ROOT / "deep_storage"))


# --------------------------------------------------------------------------- quality gates

def page_recall_threshold() -> float:
    """Minimum share of a page's text-layer words that pass 1 must reproduce."""
    return _env_float("PAGE_RECALL_THRESHOLD", 0.97)


def coverage_threshold() -> float:
    """Minimum share of transcript text that pass 2 must place in schema fields."""
    return _env_float("COVERAGE_THRESHOLD", 0.95)


def pass1_retries() -> int:
    return _env_int("PASS1_RETRIES", 2)


def pass2_retries() -> int:
    return _env_int("PASS2_RETRIES", 2)


def render_dpi() -> int:
    return _env_int("RENDER_DPI", 200)


# --------------------------------------------------------------------------- models

@dataclass(frozen=True)
class ModelProfile:
    """A local model. The same model runs both passes."""

    key: str
    label: str
    repo_id: str
    local_folder: str
    context_tokens: int
    max_output_tokens: int
    # Passed to the chat template (e.g. to turn reasoning traces off for literal transcription).
    chat_template_kwargs: Dict[str, Any] = field(default_factory=dict)
    # Passed to the multimodal processor. Deployment-specific (e.g. an image token budget);
    # set via <KEY>_MM_PROCESSOR_KWARGS as JSON.
    mm_processor_kwargs: Dict[str, Any] = field(default_factory=dict)
    trust_remote_code: bool = False
    note: str = ""

    @property
    def env_prefix(self) -> str:
        return "R2J_" + self.key.upper().replace("-", "_").replace(".", "_")


# The pipeline runs on exactly one model. The registry shape is kept so the profile's
# settings (template arguments, remote code, env prefix) stay in one declared place.
MODELS: Dict[str, ModelProfile] = {
    "qwen3-vl-4b-instruct-awq": ModelProfile(
        key="qwen3-vl-4b-instruct-awq",
        label="Qwen3-VL 4B Instruct AWQ (4-bit)",
        repo_id="Qwen/Qwen3-VL-4B-Instruct-AWQ",
        local_folder="Qwen3-VL-4B-Instruct-AWQ-4bit",
        context_tokens=262_144,
        max_output_tokens=32_768,
        chat_template_kwargs={},
        trust_remote_code=False,
        note="Qwen3 Vision Language model, 4B parameters, AWQ 4-bit quantized.",
    ),
    "nemotron-30b": ModelProfile(
        key="nemotron-30b",
        label="Nemotron 30B",
        repo_id="nvidia/Nemotron-30B",
        local_folder="Nemotron-30B",
        context_tokens=32768,
        max_output_tokens=8192,
        chat_template_kwargs={},
        trust_remote_code=True,
        note="Nemotron 30B model",
    ),
}

DEFAULT_MODEL = "qwen3-vl-4b-instruct-awq"


def get_model(key: str) -> ModelProfile:
    try:
        return MODELS[key]
    except KeyError:
        raise ValueError(f"Unknown model {key!r}; choose one of {sorted(MODELS)}") from None


def model_endpoint(profile: ModelProfile) -> Optional[str]:
    """Base URL of a local OpenAI-compatible server for this model, if configured.

    ``R2J_<MODEL>_ENDPOINT`` wins over the shared ``R2J_MODEL_ENDPOINT``.
    """
    return os.environ.get(f"{profile.env_prefix}_ENDPOINT") or os.environ.get("R2J_MODEL_ENDPOINT") or None


def served_model_name(profile: ModelProfile) -> str:
    """Model name the server was started with (``vllm serve <path> --served-model-name ...``)."""
    return os.environ.get(f"{profile.env_prefix}_SERVED_NAME", profile.repo_id)


def local_weights(profile: ModelProfile) -> Optional[Path]:
    """Local weights folder for in-process loading, if present."""
    override = os.environ.get(f"{profile.env_prefix}_PATH")
    candidates = [Path(override)] if override else [models_dir() / profile.local_folder]
    for folder in candidates:
        if (folder / "config.json").exists() and (any(folder.glob("*.safetensors")) or any(folder.glob("*.bin"))):
            return folder
    return None


def mm_processor_kwargs(profile: ModelProfile) -> Dict[str, Any]:
    import json

    raw = os.environ.get(f"{profile.env_prefix}_MM_PROCESSOR_KWARGS")
    if not raw:
        return dict(profile.mm_processor_kwargs)
    return {**profile.mm_processor_kwargs, **json.loads(raw)}
