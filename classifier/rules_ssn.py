"""
National ID (US Social Security Number) rule (spec 4.2).
"""

import re

# Three groups of digits (3, 2, 4) with an optional dash or space between them.
# The parentheses "capture" each group so we can validate it separately.
SSN_PATTERN = re.compile(r"(\d{3})([- ]?)(\d{2})([- ]?)(\d{4})")

# Note: no negative keywords. A header like "employee_id" does NOT block SSN.
HEADER_KEYWORDS = ["ssn", "social", "social_security", "national_id"]


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


def check_ssn(value):
    """
    Return (matched, note) for one value.

    The note says the separator style for matches ("Match · dashes") or why the
    value failed. fullmatch matters: "021000021-4455667788" contains 9 digits in
    a row, but the whole value is not an SSN, so it does not match.
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
    return True, f"Match · {separator_style(sep1, sep2)}"
