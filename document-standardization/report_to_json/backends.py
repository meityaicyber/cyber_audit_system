"""
Model backends. The model serves both passes through a single backend.

``OpenAICompatBackend``  a local OpenAI-compatible server (vLLM, SGLang, TensorRT-LLM).
                         Preferred: handles 100B-class MoE models across GPUs, prefix-caches
                         the transcript shared by pass-2 calls, and enforces JSON schemas
                         during decoding (``response_format: json_schema``).
``TransformersBackend``  in-process Hugging Face Transformers from a local weights folder.
                         No constrained decoding; pass 2 validates and repairs instead.

Both are offline-only: the server must be local to the air-gapped network and
Transformers loads with ``local_files_only=True``.
"""

from __future__ import annotations

import base64
import io
import json
import logging
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Protocol

from PIL import Image

from . import config

log = logging.getLogger(__name__)


class BackendError(RuntimeError):
    """The model could not be reached or failed to generate."""


@dataclass
class Generation:
    text: str
    truncated: bool  # hit the output token limit


class ModelBackend(Protocol):
    description: str
    supports_json_schema: bool

    def generate(self, prompt: str, image: Optional[Image.Image] = None,
                 json_schema: Optional[Dict[str, Any]] = None, max_tokens: int = 8192) -> Generation: ...

    def check(self) -> None:
        """Raise BackendError if the model is not usable."""

    def close(self) -> None: ...


def _png_data_url(image: Image.Image) -> str:
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


class OpenAICompatBackend:
    supports_json_schema = True

    def __init__(self, profile: config.ModelProfile, base_url: str, timeout: float = 1800):
        self.profile = profile
        self.base_url = base_url.rstrip("/")
        self.model_name = config.served_model_name(profile)
        self.timeout = timeout
        self.description = f"server {self.base_url} ({self.model_name})"
        self._api_key = os.environ.get("R2J_API_KEY", "")

    def _request(self, path: str, payload: Optional[dict] = None, timeout: Optional[float] = None) -> dict:
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = urllib.request.Request(self.base_url + path, data=data, method="POST" if data else "GET",
                                     headers={"Content-Type": "application/json",
                                              **({"Authorization": f"Bearer {self._api_key}"} if self._api_key else {})})
        try:
            with urllib.request.urlopen(req, timeout=timeout or self.timeout) as resp:
                body = resp.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise BackendError(f"{self.base_url}{path} returned HTTP {exc.code}: {detail}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise BackendError(f"Cannot reach model server {self.base_url}: {exc}") from exc
        try:
            reply = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:  # a proxy error page, a truncated body...
            raise BackendError(f"{self.base_url}{path} did not return JSON: {body[:200]!r}") from exc
        if not isinstance(reply, dict):
            raise BackendError(f"{self.base_url}{path} returned unexpected JSON: {str(reply)[:200]}")
        return reply

    def check(self) -> None:
        served = [m.get("id") for m in self._request("/models", timeout=10).get("data", [])]
        if self.model_name not in served:
            raise BackendError(f"Server {self.base_url} does not serve {self.model_name!r} (serves {served}); "
                               f"set {self.profile.env_prefix}_SERVED_NAME")

    def generate(self, prompt: str, image: Optional[Image.Image] = None,
                 json_schema: Optional[Dict[str, Any]] = None, max_tokens: int = 8192) -> Generation:
        content: list = []
        if image is not None:  # image first, then the instruction
            content.append({"type": "image_url", "image_url": {"url": _png_data_url(image)}})
        content.append({"type": "text", "text": prompt})
        payload: Dict[str, Any] = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": content}],
            "temperature": 0,
            "max_tokens": min(max_tokens, self.profile.max_output_tokens),
        }
        if self.profile.chat_template_kwargs:
            payload["chat_template_kwargs"] = self.profile.chat_template_kwargs
        mm_kwargs = config.mm_processor_kwargs(self.profile)
        if mm_kwargs and image is not None:
            payload["mm_processor_kwargs"] = mm_kwargs
        if json_schema is not None:
            payload["response_format"] = {"type": "json_schema",
                                          "json_schema": {"name": "section", "schema": json_schema, "strict": True}}
        body = self._request("/chat/completions", payload)
        try:
            choice = body["choices"][0]
            return Generation(text=choice["message"]["content"] or "", truncated=choice.get("finish_reason") == "length")
        except (KeyError, IndexError, TypeError) as exc:
            raise BackendError(f"Unexpected response from {self.base_url}: {str(body)[:300]}") from exc

    def close(self) -> None:
        pass


class TransformersBackend:
    supports_json_schema = False

    def __init__(self, profile: config.ModelProfile, weights: Path):
        self.profile = profile
        self.weights = weights
        self.description = f"in-process Transformers ({weights})"
        self._model = None
        self._processor = None
        self._load_error: Optional[BackendError] = None

    def check(self) -> None:
        """Loads the model, so a model that cannot run is detected before any page is processed."""
        if not (self.weights / "config.json").exists():
            raise BackendError(f"No model weights at {self.weights}")
        self._load()

    def _load(self) -> None:
        if self._model is not None:
            return
        if self._load_error is not None:  # a failed load is not retried on every page
            raise self._load_error
        try:
            self._load_model()
        except BackendError as exc:
            self._load_error = exc
            raise
        except Exception as exc:  # missing processor files, CUDA out of memory, corrupt weights...
            self._load_error = BackendError(f"Could not load {self.weights}: {type(exc).__name__}: {exc}")
            self._model = self._processor = None
            raise self._load_error from exc

    def _load_model(self) -> None:
        try:
            import importlib

            importlib.import_module("torch")
            import transformers
        except ImportError as exc:
            raise BackendError("In-process inference needs torch and transformers "
                               "(pip install -r requirements-models.txt)") from exc
        common = {"trust_remote_code": self.profile.trust_remote_code, "local_files_only": True}
        self._processor = transformers.AutoProcessor.from_pretrained(str(self.weights), **common)
        errors = []
        # Which auto class the model registers under depends on the transformers version.
        for cls_name in ("AutoModelForImageTextToText", "AutoModelForMultimodalLM", "AutoModelForCausalLM"):
            cls = getattr(transformers, cls_name, None)
            if cls is None:
                continue
            try:
                self._model = cls.from_pretrained(str(self.weights), device_map="auto", torch_dtype="auto", **common)
                break
            except (ValueError, KeyError) as exc:  # model type not registered for this auto class
                errors.append(f"{cls_name}: {exc}")
        if self._model is None:
            raise BackendError(f"Could not load {self.weights}: " + "; ".join(errors))
        self._model.eval()
        log.info("Loaded %s in-process", self.weights)

    def generate(self, prompt: str, image: Optional[Image.Image] = None,
                 json_schema: Optional[Dict[str, Any]] = None, max_tokens: int = 8192) -> Generation:
        import torch

        self._load()
        content: list = [{"type": "image", "image": image}] if image is not None else []
        content.append({"type": "text", "text": prompt})
        max_new = min(max_tokens, self.profile.max_output_tokens)
        try:
            inputs = self._processor.apply_chat_template(
                [{"role": "user", "content": content}], add_generation_prompt=True, tokenize=True,
                return_dict=True, return_tensors="pt", **self.profile.chat_template_kwargs,
                **(config.mm_processor_kwargs(self.profile) if image is not None else {}),
            ).to(self._model.device)
            with torch.inference_mode():
                output = self._model.generate(**inputs, max_new_tokens=max_new, do_sample=False, repetition_penalty=1.05)
        except Exception as exc:
            raise BackendError(f"Generation failed: {exc}") from exc
        new_tokens = output[0, inputs["input_ids"].shape[1]:]
        text = self._processor.decode(new_tokens, skip_special_tokens=True)
        return Generation(text=text, truncated=len(new_tokens) >= max_new)

    def close(self) -> None:
        self._model = self._processor = None
        self._load_error = None
        try:
            import gc

            import torch
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass


def create_backend(model_key: str) -> ModelBackend:
    """The configured backend for ``model_key``: a local server if one is configured, else local weights."""
    profile = config.get_model(model_key)
    endpoint = config.model_endpoint(profile)
    if endpoint:
        return OpenAICompatBackend(profile, endpoint)
    weights = config.local_weights(profile)
    if weights:
        return TransformersBackend(profile, weights)
    raise BackendError(
        f"{profile.label} is not available: start a local server and set {profile.env_prefix}_ENDPOINT "
        f"(or R2J_MODEL_ENDPOINT), or place the weights in {config.models_dir() / profile.local_folder}")
