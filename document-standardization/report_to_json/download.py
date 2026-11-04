"""
Stage model weights for an air-gapped deployment, and verify them on arrival.

The weights are not kept in the repository (about 66 GB in multi-gigabyte files).
``models/manifest.json`` pins the model to an exact revision and lists every file
with its size and checksum instead.

On a machine WITH internet access:
    python -m report_to_json.download --status
    python -m report_to_json.download --model qwen3-vl-4b-instruct-awq --dest D:\\transfer\\models
    python -m report_to_json.download --refresh-manifest      # re-pin to the latest revisions

On the air-gapped system, after copying the folders into MODELS_DIR:
    python -m report_to_json.download --verify qwen3-vl-4b-instruct-awq

Set ``HF_TOKEN`` if the repository requires authentication.
The pipeline itself never downloads anything.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional

from . import config

MANIFEST_PATH = config.REPO_ROOT / "models" / "manifest.json"
_HF_API = "https://huggingface.co/api/models"


# --------------------------------------------------------------------------- manifest

def load_manifest(path: Path = MANIFEST_PATH) -> Dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _api(url: str) -> object:
    req = urllib.request.Request(url, headers={"User-Agent": "report-to-json"})
    token = os.environ.get("HF_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode("utf-8"))


def build_manifest() -> Dict:
    """Pin every supported model to its current revision and record each file's size and checksum."""
    models = {}
    for profile in config.MODELS.values():
        info = _api(f"{_HF_API}/{profile.repo_id}")
        revision = info["sha"]
        tree = _api(f"{_HF_API}/{profile.repo_id}/tree/{revision}?recursive=true")
        files = []
        for entry in sorted((e for e in tree if e.get("type") == "file"), key=lambda e: e["path"]):
            lfs = entry.get("lfs")
            files.append({"path": entry["path"], "size": entry.get("size", 0),
                          # LFS files carry a SHA-256; small files are identified by their git blob SHA-1.
                          "sha256": lfs["oid"] if lfs else None,
                          "git_sha1": None if lfs else entry.get("oid")})
        card = info.get("cardData") or {}
        models[profile.key] = {
            "repo_id": profile.repo_id,
            "revision": revision,
            "local_folder": profile.local_folder,
            "license": card.get("license_name") or card.get("license"),
            "gated": info.get("gated") or False,
            "total_bytes": sum(f["size"] for f in files),
            "files": files,
        }
    return {"source": "https://huggingface.co", "models": models}


def refresh_manifest(path: Path = MANIFEST_PATH) -> None:
    manifest = build_manifest()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")
    for key, model in manifest["models"].items():
        print(f"{key:22} {model['revision'][:12]}  {model['total_bytes'] / 1e9:6.1f} GB  {len(model['files'])} files")


# --------------------------------------------------------------------------- download / verify

def download(key: str, dest: Path) -> Path:
    os.environ["HF_HUB_OFFLINE"] = "0"  # this command is the one deliberate exception
    os.environ.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "0")
    from huggingface_hub import snapshot_download

    model = load_manifest()["models"][key]
    target = dest / model["local_folder"]
    target.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {model['repo_id']} @ {model['revision'][:12]} -> {target} "
          f"({model['total_bytes'] / 1e9:.1f} GB)")
    snapshot_download(repo_id=model["repo_id"], revision=model["revision"], local_dir=str(target))
    problems = verify(key, target)
    if problems:
        raise SystemExit("Download does not match the manifest:\n  " + "\n  ".join(problems))
    print(f"Verified. Copy {target} to <MODELS_DIR>/{model['local_folder']} on the air-gapped system.")
    return target


def _file_digest(path: Path, algorithm: str, prefix: bytes = b"") -> str:
    digest = hashlib.new(algorithm)
    digest.update(prefix)
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify(key: str, folder: Optional[Path] = None, manifest: Optional[Dict] = None) -> List[str]:
    """Problems found in a local copy of a model (empty list = the copy is complete and intact)."""
    model = (manifest or load_manifest())["models"][key]
    folder = folder or (config.models_dir() / model["local_folder"])
    problems = []
    for entry in model["files"]:
        path = folder / entry["path"]
        if not path.is_file():
            problems.append(f"missing: {entry['path']}")
            continue
        if path.stat().st_size != entry["size"]:
            problems.append(f"wrong size: {entry['path']} ({path.stat().st_size} != {entry['size']})")
            continue
        if entry.get("sha256"):
            if _file_digest(path, "sha256") != entry["sha256"]:
                problems.append(f"checksum mismatch: {entry['path']}")
        elif entry.get("git_sha1"):
            header = f"blob {entry['size']}\0".encode()
            if _file_digest(path, "sha1", header) != entry["git_sha1"]:
                problems.append(f"checksum mismatch: {entry['path']}")
    return problems


def status() -> None:
    manifest = load_manifest()["models"] if MANIFEST_PATH.exists() else {}
    for profile in config.MODELS.values():
        endpoint = config.model_endpoint(profile)
        weights = config.local_weights(profile)
        where = f"server {endpoint}" if endpoint else (f"weights {weights}" if weights else "NOT AVAILABLE")
        pinned = manifest.get(profile.key, {})
        size = f"{pinned['total_bytes'] / 1e9:.1f} GB @ {pinned['revision'][:12]}" if pinned else "not in manifest"
        print(f"{profile.key:22} {profile.repo_id:52} {size:24} {where}")


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", "-m", choices=list(config.MODELS), help="model to download (pinned revision)")
    parser.add_argument("--dest", "-d", type=Path, default=config.models_dir(), help="destination folder")
    parser.add_argument("--verify", choices=list(config.MODELS), help="check a local copy against the manifest")
    parser.add_argument("--path", type=Path, help="folder to verify (default: MODELS_DIR/<model folder>)")
    parser.add_argument("--refresh-manifest", action="store_true", help="re-pin revisions and checksums (online)")
    parser.add_argument("--status", "-s", action="store_true", help="show which models are available")
    args = parser.parse_args(argv)
    if args.refresh_manifest:
        refresh_manifest()
    elif args.model:
        download(args.model, args.dest)
    elif args.verify:
        problems = verify(args.verify, args.path)
        print("OK: complete and intact" if not problems else "\n".join(problems))
        sys.exit(1 if problems else 0)
    else:
        status()


if __name__ == "__main__":
    main()
