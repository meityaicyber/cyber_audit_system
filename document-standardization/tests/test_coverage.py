import fitz

from report_to_json import coverage


def test_page_recall_counts_repeated_words():
    recall, missing = coverage.page_recall(coverage.tokens("high high medium low"), "High and medium")
    assert recall == 0.5
    assert set(missing) == {"high", "low"}


def test_page_recall_is_none_without_a_text_layer():
    assert coverage.page_recall([], "anything") == (None, [])


def test_reference_words_skip_text_under_masked_images(tmp_path):
    path = tmp_path / "p.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 60), "Visible sentence")
    page.insert_text((50, 160), "Hidden caption")
    doc.save(str(path))
    with fitz.open(str(path)) as doc:
        words = coverage.reference_words(doc[0], [(40, 140, 300, 180)])
    assert words == ["visible", "sentence"]


def _page(n, body):
    return f"<!-- PAGE_START: {n} -->\n## Page {n}\n\n{body}\n\n<!-- PAGE_END: {n} -->"


def test_dates_and_labels_count_as_placed():
    transcript = _page(1, "Report Release Date: 16.02.2026\n"
                          "| Prepared by | Jane Doe |\n"
                          "This report is intended solely for internal use by Acme.")
    data = {"report_meta": {"report_release_date": "2026-02-16"},
            "document_control": {"prepared_by": {"name": "Jane Doe"}}}
    cov = coverage.transcript_coverage(transcript, data)
    assert [u.text for u in cov.uncovered] == ["This report is intended solely for internal use by Acme."]
    assert 0 < cov.ratio < 1


def test_structural_text_is_not_content():
    transcript = "\n\n".join([
        _page(1, "ACME CONFIDENTIAL\nContents\nIntroduction ........ 3\nDetailed Observations ........ 5\n"
                 "Page 1 of 3"),
        _page(2, "ACME CONFIDENTIAL\nIntroduction\n| Sr. No. | Name | Designation |\n| --- | --- | --- |\n"
                 "| 1 | Jane Doe | Manager |\nPage 2 of 3"),
        _page(3, "ACME CONFIDENTIAL\n# Detailed Observations\nAssumptions:\nOnly listed APIs were tested.\n"
                 "Page 3 of 3"),
    ])
    units, structural = coverage.transcript_units(transcript)
    assert [(u.heading, u.text) for u in units] == [
        ("Introduction", "1"), ("Introduction", "Jane Doe"), ("Introduction", "Manager"),
        ("Assumptions", "Only listed APIs were tested.")]
    assert units[2].column == "Designation" and units[2].row == "1 | Jane Doe | Manager"
    # running header x3, contents title + 2 entries, 3 page footers, 2 headings, 2 column headers, 1 label
    # ("Sr. No." has no content words, so it is not counted at all)
    assert structural == 14


def test_unmapped_entries_are_paragraphs_with_context():
    transcript = "\n\n".join([
        _page(4, "Assumptions:\nBased on the scope, only the specified APIs were\ntested during the window."),
        _page(5, "continued onto the next page of the report.\n"
                 "| Sr. No. | Name | Listed on CERT-In |\n| --- | --- | --- |\n| 1 | Jane Doe | Yes |"),
    ])
    data = {"auditing_team": [{"sr_no": 1, "name": "Jane Doe"}]}
    entries = coverage.unmapped_entries(coverage.transcript_coverage(transcript, data).uncovered)
    assert entries == [
        {"page": 4, "heading": "Assumptions", "kind": "narrative", "context": None,
         "text": "Based on the scope, only the specified APIs were tested during the window. "
                 "continued onto the next page of the report."},
        {"page": 5, "heading": "Assumptions", "kind": "table_data", "text": "Yes",
         "context": "column: Listed on CERT-In; row: 1 | Jane Doe | Yes"},
    ]


def test_duplicate_text_is_kept_once():
    line = "Disclaimer: nothing here is warranted in any way."
    # back-to-back repeats, and a repeat separated by text that was placed in the schema
    transcript = _page(1, f"{line}\n{line}\nJane Doe\n{line}")
    cov = coverage.transcript_coverage(transcript, {"auditing_team": [{"name": "Jane Doe"}]})
    entries = coverage.unmapped_entries(cov.uncovered)
    assert [e["text"] for e in entries] == [line]
