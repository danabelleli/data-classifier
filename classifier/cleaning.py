"""
Value cleaning (spec 3.1).

Every value from the CSV goes through clean_value() before any rule looks at it,
so no rule needs to worry about stray spaces or placeholder words like "N/A".
"""

import csv
import io

# Placeholder words that mean "no value here". Compared in lowercase.
# Curly braces with plain values make a set: fast "is this in the list?" checks,
# like a JS Set.
EMPTY_MARKERS = {"", "n/a", "na", "null", "none", "unknown", "-"}


def clean_value(raw):
    """
    Trim whitespace and turn placeholder words into an empty string.

    Why: "  Austin " and "Austin" must be treated the same, and "N/A" must not
    count as a value (otherwise it would drag the match percentage down).
    """
    value = raw.strip()  # .strip() is JS .trim()
    if value.lower() in EMPTY_MARKERS:
        return ""
    return value


def non_empty(values):
    """
    Return the non-empty values as a list of (row_index, value) pairs.

    Why: all percentages are calculated over non-empty values only (spec 3.1),
    and the row index lets relational rules line up values from different
    columns in the same row.

    Python note: enumerate(values) gives (index, value) pairs, like
    values.forEach((value, index) => ...) in JS. The [... for ... if ...]
    syntax is a "list comprehension": a compact map + filter in one line.
    """
    return [(index, value) for index, value in enumerate(values) if value != ""]


MAX_ROWS = 10_000  # only the first 10,000 data rows are analyzed


def decode_text(data):
    """
    Turn the uploaded bytes into text.

    utf-8-sig is UTF-8 that also removes the invisible "byte order mark" Excel
    adds at the start of files (without this, the first header would start with
    a hidden character and never match a keyword).
    Files that are not UTF-8 at all (older Excel exports) fall back to cp1252,
    the Windows encoding, so the app still works on them.
    """
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("cp1252", errors="replace")


def read_csv(data):
    """
    Read CSV bytes into (headers, rows), every value a cleaned string.

    Every value stays a string: nothing is converted to a number, so an SSN
    like "012-34-5678" or a ZIP like "02134" keeps its leading zero.
    Short rows are padded with empty values so every row has one value per header.

    Python note: csv.reader needs a file-like object. io.StringIO wraps a string
    so it can be read like a file.
    """
    reader = csv.reader(io.StringIO(decode_text(data)))
    headers = [h.strip() for h in next(reader, [])]  # next() reads one row; [] if the file is empty
    rows = []
    for row in reader:
        if len(rows) >= MAX_ROWS:
            break
        if not any(cell.strip() for cell in row):
            continue  # skip completely blank lines
        cleaned = [clean_value(cell) for cell in row[: len(headers)]]
        cleaned += [""] * (len(headers) - len(cleaned))  # pad short rows
        rows.append(cleaned)
    return headers, rows
