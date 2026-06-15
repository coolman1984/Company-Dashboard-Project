"""
arabic.py - the shared Arabic text/number normalization core.

This is Stage 1 of the Arabic-first extraction work (see ROADMAP.md). It is a
dependency-light, pure-stdlib module used at every boundary where Arabic text is
compared, parsed, or grouped, so the rest of the pipeline can stay simple.

The single most important idea here is the split between two views of a value:

  * ``clean_display(s)`` - the ORIGINAL text, stripped only of invisible junk
    (bidi/format controls, tatweel, stray whitespace). Letters are NEVER folded.
    This is what we store and show, so a client always sees their own spelling.

  * ``match_key(s)`` - an aggressively normalized form used ONLY for matching,
    grouping and de-duplication: diacritics removed, alef/yaa/taa-marbuta/hamza
    variants folded, Arabic-Indic digits mapped to ASCII, Latin case-folded.

Keeping the two separate is what lets us total up "أحمد" and "احمد" as one
customer (via the match key) while still displaying the exact name the client
typed (via the display value).

Nothing here mutates project data on its own; the extractor and mapper call into
it. All functions are safe on ``None`` and non-string input.
"""
from __future__ import annotations

import re
import unicodedata

# Invisible / directional / format characters that must never affect matching
# or display: zero-width spaces, the bidi marks and isolates, the BOM and the
# soft hyphen. Arabic spreadsheets are full of these around RTL text.
_FORMAT_CONTROLS = (
    "​‌‍"              # ZWSP, ZWNJ, ZWJ
    "‎‏"                    # LRM, RLM
    "‪‫‬‭‮"  # LRE, RLE, PDF, LRO, RLO
    "⁦⁧⁨⁩"        # LRI, RLI, FSI, PDI
    "﻿­"                    # ZWNBSP/BOM, soft hyphen
)
_TATWEEL = "ـ"  # decorative kashida elongation, carries no meaning

# Arabic diacritics (harakat), tanwin, shadda/sukun and the superscript alef.
_HARAKAT = re.compile("[ً-ٰٟ]")

# Arabic-Indic (U+0660..) and Eastern Arabic-Indic / Persian (U+06F0..) digits.
_DIGIT_MAP = {}
for _i in range(10):
    _DIGIT_MAP[ord("٠") + _i] = str(_i)
    _DIGIT_MAP[ord("۰") + _i] = str(_i)

# Letter folds applied only for the match key. Maps to "" (None) means "drop".
_LETTER_FOLD = {
    "آ": "ا",  # آ alef madda      -> ا
    "أ": "ا",  # أ alef hamza above -> ا
    "إ": "ا",  # إ alef hamza below -> ا
    "ٱ": "ا",  # ٱ alef wasla      -> ا
    "ى": "ي",  # ى alef maqsura    -> ي
    "ة": "ه",  # ة taa marbuta     -> ه
    "ؤ": "و",  # ؤ waw with hamza  -> و
    "ئ": "ي",  # ئ yaa with hamza  -> ي
    "ء": None,      # ء standalone hamza -> drop
}

_DROP_CONTROLS = {ord(c): None for c in _FORMAT_CONTROLS + _TATWEEL}
_FOLD_TABLE = {ord(k): v for k, v in _LETTER_FOLD.items()}
_MINUS_SIGN = "−"     # proper minus sign, often pasted instead of '-'
_ARABIC_THOUSANDS = "٬"  # ٬
_ARABIC_DECIMAL = "٫"    # ٫


def clean_display(value) -> str:
    """Original text with only invisible junk removed; letters left intact.

    Use this for anything stored or shown to the user.
    """
    if value is None:
        return ""
    text = unicodedata.normalize("NFC", str(value))
    text = text.translate(_DROP_CONTROLS)
    # Collapse every run of whitespace (incl. NBSP, thin/narrow spaces) to one.
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def to_ascii_digits(value) -> str:
    """Map Arabic-Indic and Persian digits to ASCII 0-9; leave the rest."""
    if value is None:
        return ""
    return str(value).translate(_DIGIT_MAP)


def match_key(value) -> str:
    """Aggressively normalized key for matching/grouping (never for display).

    Folds the common Arabic spelling variants so the same name written
    different ways collapses to one key.
    """
    text = clean_display(value)
    text = _HARAKAT.sub("", text)
    text = text.translate(_DIGIT_MAP)
    text = text.translate(_FOLD_TABLE)
    text = text.casefold()
    return re.sub(r"\s+", " ", text).strip()


def parse_number(value):
    """Parse a possibly Arabic-formatted numeric cell into a float.

    Handles Arabic-Indic/Persian digits, the Arabic thousands (٬) and decimal
    (٫) separators, Latin thousands commas, currency symbols/words, accounting
    parentheses for negatives, and the Unicode minus sign. Returns ``None`` for
    an empty cell and raises ``ValueError`` for genuinely non-numeric text, so
    callers can attach file/row context.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError(f"not a number: {value!r}")
    if isinstance(value, (int, float)):
        return float(value)

    text = clean_display(value)
    if text == "":
        return None
    text = text.translate(_DIGIT_MAP).replace(_MINUS_SIGN, "-")

    negative = False
    if re.fullmatch(r"\(.*\)", text):          # accounting negative: (1,250)
        negative = True
        text = text[1:-1]

    text = text.replace(_ARABIC_THOUSANDS, "")  # ٬ thousands
    text = text.replace(_ARABIC_DECIMAL, ".")   # ٫ decimal
    text = text.replace(",", "")                 # Latin thousands
    if "-" in text:                              # any minus -> negative number
        negative = True

    # Extract the numeric token, ignoring surrounding currency words/symbols.
    # A leading/trailing dot is never a decimal point here (it usually belongs
    # to an abbreviation like "ر.س"), so the token must start and end on a digit.
    match = re.search(r"\d[\d.]*\d|\d", text)
    if not match:
        raise ValueError(f"no numeric content in {value!r}")
    try:
        number = float(match.group(0))
    except ValueError:
        raise ValueError(f"no numeric content in {value!r}")
    return -number if negative else number


# Gregorian month names in Arabic, both the Egyptian/Gulf transliterations and
# the Levantine/Iraqi names. Lookup is by match_key, so spelling variants
# (e.g. أبريل vs ابريل, آذار vs اذار) resolve automatically.
_MONTHS_RAW = {
    1: ["يناير", "كانون الثاني"],
    2: ["فبراير", "شباط"],
    3: ["مارس", "آذار"],
    4: ["أبريل", "نيسان"],
    5: ["مايو", "أيار"],
    6: ["يونيو", "يونيه", "حزيران"],
    7: ["يوليو", "يوليه", "تموز"],
    8: ["أغسطس", "آب"],
    9: ["سبتمبر", "أيلول"],
    10: ["أكتوبر", "تشرين الأول"],
    11: ["نوفمبر", "تشرين الثاني"],
    12: ["ديسمبر", "كانون الأول"],
}
_MONTH_LOOKUP = {}
for _num, _names in _MONTHS_RAW.items():
    for _name in _names:
        _MONTH_LOOKUP[match_key(_name)] = _num


def month_to_number(value):
    """Return 1-12 for an Arabic Gregorian month name, or ``None`` if unknown."""
    return _MONTH_LOOKUP.get(match_key(value))
