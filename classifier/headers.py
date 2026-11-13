"""
Header keyword matching (spec 3.4).

The header is supporting evidence only: it can lower the threshold for a class,
but it never classifies a column on its own and never blocks a class.
"""

import re


def split_header_words(header):
    """
    Split a header into lowercase words.

    Splits on "_", "-", spaces (and any other non-letter/digit character) and on
    camelCase boundaries, so these all become the same words:
        "date_of_birth", "Date of Birth", "dateOfBirth"  ->  ["date", "of", "birth"]
        "employeeSSN"                                   ->  ["employee", "ssn"]

    Python note: re.sub(pattern, replacement, text) is JS text.replace(/pattern/g, ...).
    r"..." is a "raw string": backslashes are kept as-is, which is what regex needs.
    """
    # "employeeSSN" -> "employee SSN": put a space between a lowercase letter
    # (or digit) and the uppercase letter that follows it.
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", header)
    # "SSNNumber" -> "SSN Number": split a run of capitals before a capitalized word.
    spaced = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", spaced)
    # re.split cuts the text wherever the pattern matches. [^A-Za-z0-9]+ means
    # "one or more characters that are not letters or digits".
    words = re.split(r"[^A-Za-z0-9]+", spaced.lower())
    return [word for word in words if word]  # drop empty strings


def find_keyword(header, keywords):
    """
    Return the first keyword that matches the header, or None if none match.

    A single-word keyword ("ssn") matches if it equals one of the header's words.
    A multi-word keyword ("date_of_birth") matches if its words appear next to
    each other, in order, in the header ("patient_date_of_birth" matches).
    Matching whole words avoids false hits like "tel" inside "hotel".
    """
    header_words = split_header_words(header)
    for keyword in keywords:
        keyword_words = split_header_words(keyword)
        size = len(keyword_words)
        # range(n) counts 0, 1, ..., n-1 (like a JS for loop with i < n).
        for start in range(len(header_words) - size + 1):
            # header_words[start : start + size] is a slice: a sub-list.
            if header_words[start : start + size] == keyword_words:
                return keyword
    return None  # None is Python's null
