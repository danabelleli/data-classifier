"""
National ID (US Social Security Number) rule (spec 4.2).
"""

import re

# Three groups of digits (3, 2, 4) with an optional dash or space between them.
# The parentheses "capture" each group so we can validate it separately.
SSN_PATTERN = re.compile(r"(\d{3})([- ]?)(\d{2})([- ]?)(\d{4})")

# Note: no negative keywords. A header like "employee_id" does NOT block SSN.
# "tax_id" is included because US tax IDs for people are SSNs.
HEADER_KEYWORDS = ["ssn", "social", "social_security", "national_id", "tax_id"]

# Note used when a raw 9-digit value is not counted (see check_ssn).
# decide.py compares against it to count those values for the reason text.
RAW_DIGITS_NOTE = "No match · raw digits need an SSN header"


def separator_style(first_separator, second_separator):
    """
    Describe how the value was written: "dashes", "spaces", "no separators" or "mixed".
    Used in the reason so a reviewer can see the formats found in the column.
    """
    if first_separator == "-" and second_separator == "-":
        return "dashes"
    if first_separator == " " and second_separator == " ":
        return "spaces"
    if first_separator == "" and second_separator == "":
        return "no separators"
    return "mixed"


def validation_problem(area, group, serial):
    """
    Return why the digits can never be a real SSN, or None if they pass.

    These are the official SSA rules: numbers starting with 000, 666 or 900-999,
    a middle group of 00, or a last group of 0000 are never issued.
    """
    if area == "000" or area == "666" or area.startswith("9"):
        return f"first 3 digits {area} are never issued"
    if group == "00":
        return "middle 2 digits 00 are never issued"
    if serial == "0000":
        return "last 4 digits 0000 are never issued"
    return None


def check_ssn(value, raw_allowed):
    """
    Return (matched, note) for one value.

    The note says the separator style for matches ("Match · dashes") or why the
    value failed. fullmatch matters: "021000021-4455667788" contains 9 digits in
    a row, but the whole value is not an SSN, so it does not match.

    raw_allowed: True when the column header matches an SSN keyword.
    Why: a formatted value (123-45-6789, 123 45 6789) has the SSN's own 3-2-4
    shape, so the format itself is evidence. A raw 9-digit value (123456789) is
    just a number: most random 9-digit IDs (order numbers, account numbers)
    pass SSN validation too. So raw digits only count when the header says the
    column holds SSNs. The header never replaces the values: raw values must
    still pass the pattern and validation.
    """
    match = SSN_PATTERN.fullmatch(value)
    if not match:
        return False, "No match · not in SSN format"
    # match.groups() returns every captured group as a tuple (a fixed-size list).
    # Python lets you unpack it into several variables at once, like JS
    # destructuring: const [area, sep1, group, sep2, serial] = match.groups()
    area, sep1, group, sep2, serial = match.groups()
    problem = validation_problem(area, group, serial)
    if problem:
        return False, f"No match · {problem}"
    style = separator_style(sep1, sep2)
    if style == "no separators" and not raw_allowed:
        return False, RAW_DIGITS_NOTE
    return True, f"Match · {style}"


# ---------------------------------------------------------------------------
# Recovering SSNs that lost their leading zeros
# ---------------------------------------------------------------------------
# Real SSNs can start with 0 or 00 (area numbers 001-099 are valid; only 000
# is never issued). When a spreadsheet stores SSNs as numbers, it drops those
# zeros: 012345678 becomes 12345678 (8 digits), 001234567 becomes 1234567
# (7 digits). check_restored_ssn puts the zeros back. It is only used when
# decide.ssn_candidate has already confirmed the column is an SSN column
# (SSN header + at least 50% valid 9-digit SSNs); on its own, a 7- or 8-digit
# number is never treated as an SSN.

# Exactly 7 or 8 digits, nothing else.
SHORT_DIGITS = re.compile(r"\d{7,8}")


def check_restored_ssn(value):
    """
    Restore the leading zeros of a 7- or 8-digit value and validate it.
    Returns None if the value is not 7 or 8 digits; otherwise (matched, note).

    Python note: "1234567".zfill(9) pads with zeros on the left up to 9
    characters ("001234567"), like "1234567".padStart(9, "0") in JS.
    """
    if not SHORT_DIGITS.fullmatch(value):
        return None
    restored = value.zfill(9)
    zeros = "zero" if len(value) == 8 else "zeros"
    # The same SSA validation as every other SSN value.
    problem = validation_problem(restored[:3], restored[3:5], restored[5:])
    if problem:
        return False, f"No match · leading {zeros} restored ({restored}), but {problem}"
    return True, f"Match · leading {zeros} restored: {restored}"
