"""The model manifest and the offline verification of staged weights."""

import hashlib

from report_to_json import config, download


def test_manifest_pins_every_offered_model():
    manifest = download.load_manifest()["models"]
    assert set(manifest) == set(config.MODELS)
    for key, model in manifest.items():
        profile = config.get_model(key)
        assert model["repo_id"] == profile.repo_id and model["local_folder"] == profile.local_folder
        assert len(model["revision"]) == 40
        assert model["files"] and all(f["sha256"] or f["git_sha1"] for f in model["files"])
        assert model["total_bytes"] == sum(f["size"] for f in model["files"])


def _manifest_for(files):
    entries = []
    for name, data, lfs in files:
        entries.append({
            "path": name, "size": len(data),
            "sha256": hashlib.sha256(data).hexdigest() if lfs else None,
            "git_sha1": None if lfs else hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest(),
        })
    return {"models": {"qwen3-vl-4b-instruct-awq": {"local_folder": "m", "files": entries}}}


def test_verify_accepts_an_intact_copy(tmp_path):
    files = [("config.json", b'{"a": 1}', False), ("model.safetensors", b"\x00" * 1000, True)]
    for name, data, _ in files:
        (tmp_path / name).write_bytes(data)
    assert download.verify("qwen3-vl-4b-instruct-awq", tmp_path, _manifest_for(files)) == []


def test_verify_reports_missing_truncated_and_corrupt_files(tmp_path):
    files = [("config.json", b'{"a": 1}', False), ("a.safetensors", b"\x01" * 100, True),
             ("b.safetensors", b"\x02" * 100, True)]
    manifest = _manifest_for(files)
    (tmp_path / "config.json").write_bytes(b'{"a": 2}')      # same size, different content
    (tmp_path / "a.safetensors").write_bytes(b"\x01" * 50)   # truncated copy
    problems = download.verify("qwen3-vl-4b-instruct-awq", tmp_path, manifest)
    assert problems == ["checksum mismatch: config.json", "wrong size: a.safetensors (50 != 100)",
                        "missing: b.safetensors"]
