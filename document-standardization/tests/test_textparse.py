import pytest

from report_to_json import textparse as tp


@pytest.mark.parametrize("raw, iso", [
    ("16.02.2026", "2026-02-16"),
    ("29/05/2025", "2025-05-29"),
    ("16th February 2026", "2026-02-16"),
    ("05th September 2025", "2025-09-05"),
    ("9-May-24", "2024-05-09"),
    ("May 5, 2024", "2024-05-05"),
    ("2025-03-21", "2025-03-21"),
    ("12/31/2025", "2025-12-31"),  # month-first only when day-first is impossible
])
def test_parse_date(raw, iso):
    assert tp.parse_date(raw) == iso


@pytest.mark.parametrize("raw", ["v1.0", "11.80.1", "2026.1", "NA", "", None])
def test_parse_date_rejects_non_dates(raw):
    assert tp.parse_date(raw) is None


def test_date_field_keeps_unparseable_text():
    assert tp.date_field("Q3 of FY26") == "Q3 of FY26"
    assert tp.date_field("-") is None


def test_clean_value_keeps_document_na_but_drops_dashes():
    assert tp.clean_value("  NA ") == "NA"
    assert tp.clean_value(" - ") is None
    assert tp.clean_value("a\n  b") == "a b"


def test_join_wrapped_url():
    assert tp.join_wrapped_url("https://host- name.test/pa th?x=1") == "https://host-name.test/path?x=1"
    assert tp.join_wrapped_url("P2P - https://a.test") == "P2P - https://a.test"


def test_parse_tables_and_compact():
    md = "text\n| A | A |  | B |\n| --- | --- | --- | --- |\n| 1 | x |  | y&#124;z |\nafter"
    [table] = tp.parse_tables(md)
    assert table.rows == [["A", "A", "", "B"], ["1", "x", "", "y|z"]]
    assert tp.compact(table.rows[0]) == ["A", "B"]


def test_serial():
    assert tp.serial("3") == 3
    assert tp.serial("3.") == 3
    assert tp.serial("S. No") is None


def test_prose_joins_wrapped_lines_and_bullets():
    text = "first line\ncontinues here\n•\nbullet one\n• bullet two\nPage 3 of 9\nCONFIDENTIAL"
    assert tp.prose(text) == "first line continues here\n• bullet one\n• bullet two"
