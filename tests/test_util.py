from jira_archiver.util import cell, fmt, fmt_dt, safe_name, unique


def test_safe_name_replaces_illegal_chars_and_truncates():
    assert safe_name('a:b/c?.txt') == "a_b_c_.txt"
    assert safe_name("") == "file"
    long = safe_name("x" * 300 + ".pdf")
    assert len(long) == 150 and long.endswith(".pdf")


def test_unique_is_case_insensitive():
    used = set()
    assert unique("A.png", used) == "A.png"
    assert unique("a.png", used) == "a-2.png"
    assert unique("A.png", used) == "A-3.png"


def test_fmt_dt():
    assert fmt_dt("2024-03-05T14:30:00.000+0100") == "2024-03-05 14:30 +0100"
    assert fmt_dt(None) == ""


def test_fmt_values():
    assert fmt(None) == ""
    assert fmt([{"name": "a"}, {"name": "b"}]) == "a, b"
    assert fmt({"value": "P", "child": {"value": "C"}}) == "P → C"
    assert fmt({"displayName": "Ann"}) == "Ann"


def test_cell_escapes_table_chars():
    assert cell("a|b\nc") == "a\\|b<br>c"
