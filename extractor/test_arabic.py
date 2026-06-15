"""
Self-contained tests for extractor/arabic.py (no pytest required).

Run:  python3 -m extractor.test_arabic
"""
from __future__ import annotations

from extractor import arabic as a


def _eq(got, expected, label):
    assert got == expected, f"{label}: expected {expected!r}, got {got!r}"


def test_clean_display_keeps_letters():
    # Letters (incl. the hamza on alef) must be preserved exactly.
    _eq(a.clean_display("أحمد"), "أحمد", "alef-hamza preserved")
    # Tatweel (kashida) is decorative and is removed.
    _eq(a.clean_display("شركةــــ"), "شركة", "tatweel stripped")
    # Bidi marks / zero-width chars around RTL text are removed.
    _eq(a.clean_display("‏مبيعات‎"), "مبيعات", "bidi marks stripped")
    # NBSP and runs of whitespace collapse to a single normal space.
    _eq(a.clean_display("صافي   المبيعات"), "صافي المبيعات", "nbsp collapsed")
    _eq(a.clean_display(None), "", "None -> empty")


def test_match_key_folds_variants():
    # The whole point: spelling variants collapse to one key...
    assert a.match_key("أحمد") == a.match_key("احمد"), "alef variants should match"
    assert a.match_key("مصطفى") == a.match_key("مصطفي"), "yaa/alef-maqsura should match"
    assert a.match_key("شركة") == a.match_key("شركه"), "taa-marbuta should match"
    # ...but genuinely different words must NOT collapse.
    assert a.match_key("مبيعات") != a.match_key("مشتريات"), "distinct words stay distinct"
    # Diacritics and digit systems are normalized away for matching.
    _eq(a.match_key("مُبِيعَات"), a.match_key("مبيعات"), "harakat ignored")


def test_to_ascii_digits():
    _eq(a.to_ascii_digits("٠١٢٣٤٥٦٧٨٩"), "0123456789", "arabic-indic digits")
    _eq(a.to_ascii_digits("۰۱۲۳"), "0123", "eastern/persian digits")
    _eq(a.to_ascii_digits("سنة ٢٠٢٥"), "سنة 2025", "mixed text untouched")


def test_parse_number_arabic_formats():
    _eq(a.parse_number("٢٠٢٥"), 2025.0, "arabic-indic integer")
    _eq(a.parse_number("1,250"), 1250.0, "latin thousands")
    _eq(a.parse_number("١٬٢٥٠٫٥٠"), 1250.5, "arabic separators")
    _eq(a.parse_number("(1250)"), -1250.0, "accounting negative")
    _eq(a.parse_number("1250﷼"), 1250.0, "trailing rial symbol")
    _eq(a.parse_number("ر.س ١٢٥٠"), 1250.0, "leading currency words")
    _eq(a.parse_number("-٣٫٥"), -3.5, "negative arabic decimal")
    _eq(a.parse_number("−3"), -3.0, "unicode minus sign")
    _eq(a.parse_number(1250), 1250.0, "passthrough int")
    _eq(a.parse_number(12.5), 12.5, "passthrough float")
    _eq(a.parse_number(""), None, "empty -> None")
    _eq(a.parse_number(None), None, "None -> None")


def test_parse_number_rejects_garbage():
    for bad in ("abc", "ر.س", True):
        try:
            a.parse_number(bad)
        except ValueError:
            continue
        raise AssertionError(f"parse_number({bad!r}) should have raised ValueError")


def test_month_to_number():
    _eq(a.month_to_number("يناير"), 1, "egyptian january")
    _eq(a.month_to_number("كانون الثاني"), 1, "levantine january")
    _eq(a.month_to_number("ديسمبر"), 12, "egyptian december")
    _eq(a.month_to_number("كانون الأول"), 12, "levantine december")
    _eq(a.month_to_number("ابريل"), 4, "april without hamza")
    _eq(a.month_to_number("آذار"), 3, "march with madda")
    _eq(a.month_to_number("not a month"), None, "unknown -> None")


def main():
    test_clean_display_keeps_letters()
    test_match_key_folds_variants()
    test_to_ascii_digits()
    test_parse_number_arabic_formats()
    test_parse_number_rejects_garbage()
    test_month_to_number()
    print("arabic normalization tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
