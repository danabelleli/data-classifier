"""
Phone Number rule (spec 4.3): US numbers, plus international numbers written
with a "+" and an ITU country code.
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

# A value made of digits only, with no formatting at all: "2125550101", "12125550101".
RAW_DIGITS = re.compile(r"\d+")

# Note used when a raw-digit value is not counted (see check_phone).
# decide.py compares against it to count those values for the reason text.
RAW_DIGITS_NOTE = "No match · raw digits need a phone header"


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


def check_phone(value, raw_allowed):
    """
    Return (matched, note, area_code) for one value.

    area_code is returned so the reason can name the most common one
    ("212 = New York"). It is None when the value is not a phone number.

    raw_allowed: True when the column header matches a phone keyword.
    Why: a formatted value ((212) 555-0101, 212-555-0101, +1 212 555 0101) has
    the shape people use to write phone numbers, so the format itself is
    evidence. A raw value (2125550101) is just a 10-digit number: order IDs like
    2024001001 also start with a real area code (202). So raw digits only count
    when the header says the column holds phone numbers. The header never
    replaces the values: raw values must still match the pattern and the area
    code list. ("+12125550101" has a "+", a phone sign, so it is not raw.)
    """
    match = PHONE_PATTERN.fullmatch(value)
    if not match:
        return False, "No match · not a US phone format", None
    area_code = match.group(2)  # group(2) is the area code captured above
    if area_code not in AREA_CODES:
        return False, f"No match · area code {area_code} is not a US area code in service", None
    if RAW_DIGITS.fullmatch(value) and not raw_allowed:
        return False, RAW_DIGITS_NOTE, None
    return True, f"Match · {area_code} ({region_of(area_code)})", area_code


# ---------------------------------------------------------------------------
# International numbers
# ---------------------------------------------------------------------------
# Why: the rule above only knows US numbers, so a "contact_phone" column with
# +44 20 7946 0958, +972 52-123-4567 and +81 3-1234-5678 was Not classified.
# An international number is accepted when ALL of these are true:
#   1. it starts with "+" (numbers starting with "00", or with no prefix at all,
#      are not accepted: without the "+" they are just digits);
#   2. the digits after the "+" start with a country code from the official
#      ITU-T E.164 list (data/country_codes.csv);
#   3. the rest is digits, optionally separated by spaces, dashes, dots or
#      parentheses;
#   4. the whole number (country code + the rest) has 8 to 15 digits
#      (15 is the maximum allowed by ITU-T E.164).
# Numbers with country code +1 do NOT use this rule: they go through the US
# rule above (NANPA area codes and every US check), so US validation stays as strict.
# Like formatted US numbers, international numbers count without a phone header:
# the "+" followed by a real country code is the evidence.

# "+", a digit, then digits and separators (space, dash, dot, parentheses).
INTERNATIONAL_PATTERN = re.compile(r"\+\d[\d .()-]*")

MIN_INTERNATIONAL_DIGITS = 8
MAX_INTERNATIONAL_DIGITS = 15  # ITU-T E.164 maximum


def load_country_codes():
    """
    Read data/country_codes.csv (from the ITU) into a dict {"44": "United Kingdom ...", ...}.
    Loaded once when this module is first imported.
    """
    with open(DATA_DIR / "country_codes.csv", encoding="utf-8") as f:
        return {row["country_code"]: row["name"] for row in csv.DictReader(f)}


COUNTRY_CODES = load_country_codes()


def country_code_of(digits):
    """
    Return the country code at the start of a digit string, or None.
    Country codes are 1 to 3 digits long, and no code is the start of another
    one (ITU designs them that way), so at most one length can match.
    """
    for length in (1, 2, 3):
        if digits[:length] in COUNTRY_CODES:
            return digits[:length]
    return None


def check_international(value):
    """
    Check one value against the international rule.
    Returns None when the rule does not apply (no "+" at the start, or country
    code +1, which the US rule handles). Otherwise returns (matched, note).
    """
    if not value.startswith("+"):
        return None
    digits = re.sub(r"\D", "", value)  # \D = any character that is not a digit
    code = country_code_of(digits)
    if code == "1":
        return None
    if not INTERNATIONAL_PATTERN.fullmatch(value):
        return False, "No match · not an international phone format"
    if code is None:
        return False, f"No match · +{digits[:3]} does not start with an ITU country code"
    if not MIN_INTERNATIONAL_DIGITS <= len(digits) <= MAX_INTERNATIONAL_DIGITS:
        return False, f"No match · international numbers have 8-15 digits (this one has {len(digits)})"
    return True, f"Match · international +{code} ({COUNTRY_CODES[code]})"


def check_any_phone(value, raw_allowed):
    """
    Return (matched, note, area_code, kind) for one value, trying the
    international rule first and the US rule otherwise.
    kind is "us" or "international" for a match (None otherwise), so the reason
    can say how many of each were found. area_code is only set for US matches.
    """
    international = check_international(value)
    if international is not None:
        matched, note = international
        return matched, note, None, "international" if matched else None
    matched, note, area_code = check_phone(value, raw_allowed)
    return matched, note, area_code, "us" if matched else None
