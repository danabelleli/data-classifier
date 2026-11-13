"""
Email Address rule (spec 4.1).
"""

import re

# re.compile turns the pattern into a reusable regex object, like new RegExp(...).
# re.IGNORECASE is the JS "i" flag.
EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", re.IGNORECASE)

HEADER_KEYWORDS = ["email", "e-mail", "mail"]


def check_email(value):
    """
    Return (matched, note) for one value.

    Why fullmatch: the WHOLE value must be an email. fullmatch is like a JS regex
    with ^ and $ around it. A notes column containing "write to a@b.com" does not
    match, because we classify what a column IS, not what is mentioned in it.
    """
    if EMAIL_PATTERN.fullmatch(value):
        return True, "Match"
    return False, "No match · not an email address"
