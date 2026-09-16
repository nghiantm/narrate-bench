import pytest

from narrate_bench.text.normalize import normalize

# (input, expected_output) golden cases. normalize() always appends a
# trailing "\n" (whitespace-collapse step), so expected strings include it.
CASES = [
    # NFKC
    ("café", "café\n"),
    ("x² test", "x2 test\n"),  # NFKC compatibility-decomposes superscript digits
    ("ﬁre", "fire\n"),  # ligature fi -> f + i
    ("Ａｂｃ", "Abc\n"),  # fullwidth -> ascii
    ("naïve", "naïve\n"),
    # Straight quotes
    ("“hello”", '"hello"\n'),
    ("‘hello’", "'hello'\n"),
    ("„hello”", '"hello"\n'),
    ("«hello»", '"hello"\n'),
    ("it’s", "it's\n"),
    ("‹x›", "'x'\n"),
    ("‚x‘", "'x'\n"),
    # Dash unification
    ("a—b", "a - b\n"),
    ("a–b", "a - b\n"),
    ("a--b", "a - b\n"),
    ("a — b", "a - b\n"),
    ("well—", "well -\n"),
    # Abbreviation expansion
    ("Mr. Bennet", "Mister Bennet\n"),
    ("Mrs. Bennet", "Missus Bennet\n"),
    ("Dr. Livesey", "Doctor Livesey\n"),
    ("St. Paul", "Saint Paul\n"),
    ("Mt. Everest", "Mount Everest\n"),
    ("cats vs. dogs", "cats versus dogs\n"),
    ("apples etc. oranges", "apples et cetera oranges\n"),
    ("John Jr. Smith", "John Junior Smith\n"),
    ("John Sr. Smith", "John Senior Smith\n"),
    ("Mrs. and Mr. Bennet", "Missus and Mister Bennet\n"),
    # Numeral spelling: integers < 1000
    ("0 apples", "zero apples\n"),
    ("5 apples", "five apples\n"),
    ("9 apples", "nine apples\n"),
    ("10 apples", "ten apples\n"),
    ("11 apples", "eleven apples\n"),
    ("19 apples", "nineteen apples\n"),
    ("20 apples", "twenty apples\n"),
    ("21 apples", "twenty-one apples\n"),
    ("42 apples", "forty-two apples\n"),
    ("99 apples", "ninety-nine apples\n"),
    ("100 apples", "one hundred apples\n"),
    ("101 apples", "one hundred one apples\n"),
    ("110 apples", "one hundred ten apples\n"),
    ("999 apples", "nine hundred ninety-nine apples\n"),
    ("1st place", "1st place\n"),  # ordinal, not touched
    ("42nd place", "42nd place\n"),  # ordinal, not touched
    # Numeral spelling: years
    ("in 1800", "in eighteen hundred\n"),
    ("in 1810", "in eighteen ten\n"),
    ("in 1805", "in eighteen oh five\n"),
    ("in 1894", "in eighteen ninety-four\n"),
    ("in 1900", "in nineteen hundred\n"),
    ("in 1901", "in nineteen oh one\n"),
    ("in 1984", "in nineteen eighty-four\n"),
    ("in 2000", "in two thousand\n"),
    ("in 2004", "in two thousand four\n"),
    ("in 2023", "in two thousand twenty-three\n"),
    # Whitespace collapse
    ("a    b", "a b\n"),
    ("a\t\tb", "a b\n"),
    ("a  \nb", "a\nb\n"),
    ("a\n\n\n\nb", "a\n\nb\n"),
    ("  leading and trailing  ", "leading and trailing\n"),
    ("line one\nline two\n\n\n", "line one\nline two\n"),
]


@pytest.mark.parametrize("raw,expected", CASES)
def test_normalize_golden_case(raw, expected):
    assert normalize(raw) == expected


def test_case_count_at_least_fifty():
    assert len(CASES) >= 50
