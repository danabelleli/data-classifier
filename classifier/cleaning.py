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


class CsvReadError(Exception):
    """
    A problem with the uploaded file itself (empty, only a header, not a CSV).
    The message is written for the user: the API shows it as-is in the UI,
    instead of crashing or showing a technical Python error.
    """


# The exact messages shown in the UI (kept here so both endpoints use the same words).
EMPTY_FILE = "This file is empty."
HEADER_ONLY = "This file has column names but no data rows."
NOT_A_CSV = "This file couldn't be read as a CSV."

# The separators we try to detect, and the one used when detection fails.
SEPARATORS = ",;\t|"
DEFAULT_SEPARATOR = ","

# How much of the file is looked at to detect the separator. 64 KB covers the
# header and many rows, without slowing down big files.
SNIFF_SAMPLE_CHARS = 64 * 1024


def decode_text(data):
    """
    Turn the uploaded bytes into text.

    utf-8-sig is UTF-8 that also removes the invisible "byte order mark" Excel
    adds at the start of files (without this, the first header would start with
    a hidden character and never match a keyword).
    Excel's "Unicode text" export is UTF-16, which starts with its own byte order
    mark (FF FE or FE FF); those files are decoded as UTF-16 so they still work.
    Files that are not UTF-8 at all (older Excel exports) fall back to cp1252,
    the Windows encoding, so the app still works on them.

    A file containing NUL bytes (character 0) after decoding is a binary file
    (an .xlsx, an image, a PDF renamed to .csv): real text never contains it.
    Without this check, a binary file would be "read" as columns of garbage.
    """
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        try:
            text = data.decode("utf-16")
        except UnicodeDecodeError:
            raise CsvReadError(NOT_A_CSV)
    else:
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = data.decode("cp1252", errors="replace")
    if "\x00" in text:
        raise CsvReadError(NOT_A_CSV)
    return text


def detect_separator(text):
    """
    Guess whether the file uses commas, semicolons, tabs or pipes (|).

    Why: European Excel saves "CSV" with semicolons, and database exports often
    use tabs or pipes. Read with the wrong separator, every row would become one
    long column and nothing would be classified.

    How: Python's csv.Sniffer looks at the start of the file and picks the
    separator that splits the lines into the same number of cells most
    consistently. It understands quotes, so a comma inside "Carter, Emily" does
    not fool it. We only let it choose from our four separators.
    If it can't decide (for example a file with a single column), we use commas.

    The sample is cut at the last line break, so the Sniffer never sees half a line.
    Only the separator is taken from the Sniffer; its other guesses (quote
    character, etc.) are ignored because they are less reliable, and the
    standard CSV quoting rules work for almost every real file.
    """
    sample = text[:SNIFF_SAMPLE_CHARS]
    if len(text) > SNIFF_SAMPLE_CHARS and "\n" in sample:
        sample = sample[: sample.rindex("\n")]
    try:
        return csv.Sniffer().sniff(sample, delimiters=SEPARATORS).delimiter
    except csv.Error:
        return DEFAULT_SEPARATOR


def unique_labels(headers):
    """
    Give every column a label that is unique and never blank.

    Why: the UI, the export and Test results find columns by their label. Two
    columns both called "name" would be confused with each other, and a column
    with no header would show as an empty line.
      - A blank header is labeled by its position: "(no header, column 5)".
      - A repeated header gets a number: "name", "name (2)", "name (3)".
    The first column with a name keeps it unchanged. If a label is already
    taken (a file that really has a column called "name (2)"), the number
    keeps going up until the label is free.

    Only the label changes. The original header text is kept separately and is
    what the header-keyword rules look at, so classification is not affected.
    """
    labels = []
    taken = set(header for header in headers if header)  # real names are reserved first
    seen = set()
    for position, header in enumerate(headers, start=1):
        if not header:
            label = f"(no header, column {position})"
        elif header not in seen:
            label = header
        else:
            number = 2
            while f"{header} ({number})" in taken:
                number += 1
            label = f"{header} ({number})"
        seen.add(header)
        taken.add(label)
        labels.append(label)
    return labels


def read_csv(data):
    """
    Read CSV bytes into (headers, labels, rows), every value a cleaned string.
      headers  the original header text (used by the header-keyword rules)
      labels   unique, never-blank names for display (see unique_labels)
      rows     lists of cleaned values, exactly one per header

    Every value stays a string: nothing is converted to a number, so an SSN
    like "012-34-5678" or a ZIP like "02134" keeps its leading zero.

    Unusual rows never cause a crash:
      - rows with fewer values than the header: the missing cells are empty
      - rows with more values than the header: the extra cells are ignored
      - line breaks inside a quoted cell (multi-line notes): csv.reader reads the
        whole quoted text as one value. This works because the text is passed
        in whole (io.StringIO, no line splitting of our own beforehand).

    Raises CsvReadError with a user-facing message for an empty file, a file
    with only a header row, or a file that isn't a readable CSV.

    Python note: csv.reader needs a file-like object. io.StringIO wraps a string
    so it can be read like a file.
    """
    text = decode_text(data)
    if not text.strip():
        raise CsvReadError(EMPTY_FILE)

    reader = csv.reader(io.StringIO(text), delimiter=detect_separator(text))
    try:
        # The first non-blank line is the header. Blank lines before it (some
        # exports start with one) are skipped instead of being taken as an empty header.
        headers = []
        for row in reader:
            if any(cell.strip() for cell in row):
                headers = [h.strip() for h in row]
                break
        if not headers:
            raise CsvReadError(EMPTY_FILE)

        rows = []
        for row in reader:
            if len(rows) >= MAX_ROWS:
                break
            if not any(cell.strip() for cell in row):
                continue  # skip completely blank lines
            cleaned = [clean_value(cell) for cell in row[: len(headers)]]  # drop extra cells
            cleaned += [""] * (len(headers) - len(cleaned))  # pad short rows
            rows.append(cleaned)
    except csv.Error:
        # csv.Error is what the csv module raises on text it can't parse, for
        # example an unclosed quote that swallows the rest of the file into one
        # giant cell. We show a plain message instead of the technical one.
        raise CsvReadError(NOT_A_CSV)

    if not rows:
        raise CsvReadError(HEADER_ONLY)
    return headers, unique_labels(headers), rows
