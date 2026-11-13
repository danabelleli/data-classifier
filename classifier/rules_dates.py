"""
Date parsing and Date of Birth logic (spec 4.4).

Step 1 (per value): is it a valid past date?
Step 2 (per column): is a date column a birth date column? Either the header says
so (Path 1) or, in a file about people, it is the earliest date in each row (Path 2).
"""

from datetime import date, datetime

# Formats tried, in order. Codes used by datetime.strptime:
#   %Y = 4-digit year, %y = 2-digit year, %m = month number, %d = day,
#   %B = full month name (March), %b = short month name (Mar).
# Month-first (US) formats come before day-first ones, so an ambiguous value
# such as 03/04/1990 is read as March 4. Either reading makes it a valid date,
# which is all Step 1 needs; the order only affects Path 2 comparisons.
DATE_FORMATS = [
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%m/%d/%Y",
    "%d/%m/%Y",
    "%m-%d-%Y",
    "%m/%d/%y",
    "%d/%m/%y",
    "%B %d, %Y",
    "%b %d, %Y",
    "%d-%b-%Y",
]

BIRTH_KEYWORDS = ["dob", "birth", "birthday", "birth_date", "date_of_birth", "bday", "born"]

MAX_AGE_YEARS = 120


def years_before(day, years):
    """
    Return the same calendar day `years` years earlier.
    Feb 29 has no match in a non-leap year, so it becomes Feb 28.
    """
    try:
        return day.replace(year=day.year - years)
    except ValueError:  # Python's try/except is JS try/catch
        return day.replace(year=day.year - years, day=28)


def parse_with_format(value, date_format, today):
    """
    Try one format. Return a date, or None if the value does not fit it.

    datetime.strptime raises ValueError when the text does not match the format
    completely, including impossible dates such as Feb 30 and values with a
    time part ("1990-03-14 00:00:00"), so those are rejected for free.
    """
    try:
        parsed = datetime.strptime(value, date_format).date()
    except ValueError:
        return None
    # Two-digit years: Python reads "45" as 2045. A date in the future cannot be
    # a past date, so move it to the 1900s instead ("45" -> 1945, "10" stays 2010).
    if "%y" in date_format and parsed > today:
        parsed = years_before(parsed, 100)
    return parsed


def check_date(value, today=None):
    """
    Return (matched, note, parsed_date) for one value.

    A value is a valid date if it parses with one of DATE_FORMATS, is not in
    the future, and is not more than 120 years ago (older than any living person).
    `today=None` is a default argument, like `today = null` in a JS function.
    """
    today = today or date.today()
    for date_format in DATE_FORMATS:
        parsed = parse_with_format(value, date_format, today)
        if parsed is None:
            continue
        if parsed > today:
            return False, "No match · date is in the future", None
        if parsed < years_before(today, MAX_AGE_YEARS):
            return False, "No match · more than 120 years ago", None
        return True, f"Match · {parsed.isoformat()}", parsed
    return False, "No match · not a date in a supported format", None


def count_earliest(dates, other_columns):
    """
    Path 2 helper: in how many rows is this column's date earlier than the date
    in every other date column?

    dates:          {row_index: date} for this column
    other_columns:  list of (column_name, {row_index: date}) for the other date columns

    Returns (earliest_rows, compared_rows, later_than) where later_than is
    {column_name: number of rows where that column is earlier than this one},
    used to explain a "no" ("later than \"dob\" in 4 of 4 rows").
    Only rows where this column and at least one other date column both have a
    date can be compared.
    """
    earliest_rows = 0
    compared_rows = 0
    later_than = {name: 0 for name, _ in other_columns}
    # dates.items() gives (key, value) pairs, like Object.entries(dates) in JS.
    for row_index, this_date in dates.items():
        others = [(name, column[row_index]) for name, column in other_columns if row_index in column]
        if not others:
            continue
        compared_rows += 1
        # all(...) is true when every item is true, like JS array.every(...).
        if all(this_date < other_date for _, other_date in others):
            earliest_rows += 1
        for name, other_date in others:
            if other_date < this_date:
                later_than[name] += 1
    return earliest_rows, compared_rows, later_than
