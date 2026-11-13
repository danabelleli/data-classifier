"""
Phone Number rule, US only (spec 4.3).
"""

import csv
import re
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# Reading the pattern piece by piece:
#   (\+?1[-. ]?)?      optional country code: "+1", "1", "+1 ", "1-"
#   \(?([2-9]\d{2})\)?  area code, optionally in parentheses. Captured as group 2.
#                       [2-9] means it cannot start with 0 or 1 (never valid in the US).
#   [-. ]?             optional separator
#   ([2-9]\d{2})       exchange (next 3 digits), also cannot start with 0 or 1
#   [-. ]?\d{4}        optional separator, then the last 4 digits
# Because the grouping must be 3-3-4, "2024-12-3100" (4-2-4) and "123-45-6789"
# (an SSN, 3-2-4) do not match.
PHONE_PATTERN = re.compile(r"(\+?1[-. ]?)?\(?([2-9]\d{2})\)?[-. ]?([2-9]\d{2})[-. ]?\d{4}")

HEADER_KEYWORDS = ["phone", "mobile", "cell", "tel", "telephone", "contact_number"]


def load_area_codes():
    """
    Read data/area_codes.csv (from NANPA) into a dict {"212": "New York", ...}.

    Why a list of real area codes: a 10-digit number like an order ID has the
    right shape but almost never starts with a real, in-service area code.
    Loaded once when this module is first imported, then reused for every value.
    """
    with open(DATA_DIR / "area_codes.csv", encoding="utf-8") as f:
        return {row["area_code"]: row["region"] for row in csv.DictReader(f)}


AREA_CODES = load_area_codes()


def region_of(area_code):
    """Return the region for an area code, for example "New York" for "212"."""
    return AREA_CODES.get(area_code, "unknown region")  # .get = value or a default


def check_phone(value):
    """
    Return (matched, note, area_code) for one value.

    area_code is returned so the reason can name the most common one
    ("212 = New York"). It is None when the value is not a phone number.
    """
    match = PHONE_PATTERN.fullmatch(value)
    if not match:
        return False, "No match · not a US phone format", None
    area_code = match.group(2)  # group(2) is the area code captured above
    if area_code not in AREA_CODES:
        return False, f"No match · area code {area_code} is not a US area code in service", None
    return True, f"Match · {area_code} ({region_of(area_code)})", area_code
