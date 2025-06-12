import re

GRADE_RE = re.compile(r"\bGrade\b\s*[:\-]?\s*(\d{1,3})(?:\s*/\s*100)?", re.I)

def parse_grade(text: str):
    match = GRADE_RE.search(text)
    return match.group(1) if match else None

def test_parse_grade_with_total():
    assert parse_grade("Grade: 90/100") == "90"

def test_parse_grade_without_total():
    assert parse_grade("Grade: 90") == "90"

def test_parse_grade_unrelated_text():
    assert parse_grade("No grade here") is None
