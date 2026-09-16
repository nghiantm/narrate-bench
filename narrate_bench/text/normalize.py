"""Project text normalizer, versioned via NORMALIZER_VERSION.

Fixed pipeline order: NFKC -> straight quotes -> dash unification ->
abbreviation expansion -> numeral spelling -> whitespace collapse.
Each step only depends on the previous one's output.
"""

from __future__ import annotations

import re
import unicodedata

NORMALIZER_VERSION = "1"

_QUOTE_MAP = str.maketrans(
    {
        "“": '"',
        "”": '"',
        "„": '"',
        "«": '"',
        "»": '"',
        "‘": "'",
        "’": "'",
        "‚": "'",
        "‹": "'",
        "›": "'",
    }
)

# Em dash, en dash, and double-hyphen all collapse to " - ".
_DASH_RE = re.compile(r"\s*(?:—|–|--)\s*")

# Longest keys first so e.g. "Mrs." matches before "Mr." could ever misfire.
ABBREVIATIONS = {
    "Mrs.": "Missus",
    "Mr.": "Mister",
    "Dr.": "Doctor",
    "St.": "Saint",
    "Mt.": "Mount",
    "vs.": "versus",
    "etc.": "et cetera",
    "Jr.": "Junior",
    "Sr.": "Senior",
}
_ABBREV_RE = re.compile(
    "|".join(re.escape(k) for k in sorted(ABBREVIATIONS, key=len, reverse=True))
)

_ONES = [
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
    "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
    "seventeen", "eighteen", "nineteen",
]
_TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]


def _below_100(n: int) -> str:
    if n < 20:
        return _ONES[n]
    tens, rem = divmod(n, 10)
    return _TENS[tens] + ("-" + _ONES[rem] if rem else "")


def _below_1000(n: int) -> str:
    if n < 100:
        return _below_100(n)
    hundreds, rem = divmod(n, 100)
    words = _ONES[hundreds] + " hundred"
    if rem:
        words += " " + _below_100(rem)
    return words


def _spell_year(n: int) -> str:
    """Years 1000-2099 spoken the conventional way, e.g. 1984 -> nineteen eighty-four."""
    if n % 100 == 0:
        first_two = n // 100
        return _below_100(first_two) + " hundred" if n < 2000 else _below_1000(n // 1000) + " thousand"
    if n < 2000:
        first_two, last_two = divmod(n, 100)
        if last_two < 10:
            return _below_100(first_two) + " oh " + _ONES[last_two]
        return _below_100(first_two) + " " + _below_100(last_two)
    rem = n - 2000
    return "two thousand" + (" " + _below_100(rem) if rem else "")


_YEAR_RE = re.compile(r"\b(1[0-9]{3}|20[0-9]{2})\b")
_INT_RE = re.compile(r"\b\d{1,3}\b")


def _spell_numerals(text: str) -> str:
    text = _YEAR_RE.sub(lambda m: _spell_year(int(m.group(0))), text)
    text = _INT_RE.sub(lambda m: _below_1000(int(m.group(0))), text)
    return text


def _collapse_whitespace(text: str) -> str:
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = text.translate(_QUOTE_MAP)
    text = _DASH_RE.sub(" - ", text)
    text = _ABBREV_RE.sub(lambda m: ABBREVIATIONS[m.group(0)], text)
    text = _spell_numerals(text)
    text = _collapse_whitespace(text)
    return text
