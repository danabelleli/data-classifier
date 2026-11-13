"""
Person Name rule (spec 4.6).

A value counts as a name when it has the shape of a name AND its first word is a
known first name (SSA baby names), or it is a single known surname (Census).
"""

import re
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

HEADER_KEYWORDS = [
    "name",  # also covers "<something>_name" such as employee_name, patient_name
    "full_name",
    "first_name",
    "last_name",
    "surname",
    "given_name",
    "fname",
    "lname",
]

# Headers that name a PERSON's name specifically. Used as "person evidence"
# (see decide.name_candidate). The generic "name" keyword and "<something>_name"
# are left out on purpose: "merchant_name", "product_name" or "company_name"
# also contain "name" but do not hold people. (They still lower the threshold
# as header support, through HEADER_KEYWORDS above.)
PERSON_HEADER_KEYWORDS = [
    "first_name",
    "last_name",
    "full_name",
    "surname",
    "given_name",
    "fname",
    "lname",
]

# Headers that only make sense in a file about people. Matched on the header
# alone (values are not checked) as file-level person evidence.
GENDER_HEADER_KEYWORDS = ["gender", "sex"]

TITLES = {"mr", "mrs", "ms", "dr", "prof"}
SUFFIXES = {"jr", "sr", "ii", "iii", "iv"}

# One word of a name: letters, with hyphens or apostrophes allowed
# (O'Brien, Smith-Jones, Mary-Jane). [^\W\d_] means "a letter in any alphabet":
# \W is "not a word character", so [^\W\d_] is "a word character that is not a
# digit or underscore", which leaves letters, including accented ones like é.
NAME_WORD = re.compile(r"[^\W\d_]+(?:['’-][^\W\d_]+)*")
# A middle initial: one letter followed by a dot ("J.").
INITIAL = re.compile(r"[^\W\d_]\.")


def load_word_list(file_name):
    """
    Read a one-name-per-line file into a set of lowercase names.
    A set makes "is this word a first name?" a fast lookup even with 100,000 names.
    Returns an empty set if the file is missing, so the app still starts
    (Person Name will then simply never match).
    """
    path = DATA_DIR / file_name
    if not path.exists():
        return set()
    # read_text() reads the whole file; splitlines() splits it into lines.
    return {line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()}


FIRST_NAMES = load_word_list("first_names.txt")
SURNAMES = load_word_list("surnames.txt")


def bare(word):
    """Lowercase a word and drop a trailing dot or comma: "Jr." -> "jr"."""
    return word.lower().rstrip(".,")


def name_words(value):
    """
    Normalize a value into its list of name words, or return None if the value
    does not have the shape of a person's name.

    Steps:
      1. "Carter, Emily" -> "Emily Carter" (one comma = "Last, First").
         "Carter Jr., Emily" and "Emily Carter, Jr." are handled too.
      2. Remove titles at the start (Mr, Dr...) and suffixes at the end (Jr, III...).
      3. Shape filter: 1 to 4 words, each made of letters/hyphens/apostrophes or
         a single-letter initial like "J.". No digits.
    """
    if value.count(",") > 1:
        return None
    if "," in value:
        left, right = [part.strip() for part in value.split(",")]
        if bare(right) in SUFFIXES:
            value = f"{left} {right}"  # "Emily Carter, Jr." -> "Emily Carter Jr."
        else:
            value = f"{right} {left}"  # "Carter, Emily" -> "Emily Carter"

    words = value.split()  # split() with no argument splits on any whitespace
    while words and bare(words[0]) in TITLES:
        words = words[1:]  # drop the first word
    while words and bare(words[-1]) in SUFFIXES:
        words = words[:-1]  # drop the last word ([-1] is the last item in Python)
    # Suffixes in the middle can appear after the comma swap ("Emily Carter Jr.").
    words = [word for word in words if bare(word) not in SUFFIXES]

    if not 1 <= len(words) <= 4:  # Python allows chained comparisons like 1 <= x <= 4
        return None
    for word in words:
        if not (NAME_WORD.fullmatch(word) or INITIAL.fullmatch(word)):
            return None
    return [word.lower() for word in words]


def is_first_name(word):
    """
    True if the word is in the SSA first-name list.
    The SSA list stores "Mary-Jane" as "maryjane", so we also try the word without
    hyphens/apostrophes, and the part before the first hyphen ("mary").
    """
    plain = re.sub(r"['’-]", "", word)
    first_part = re.split(r"['’-]", word)[0]
    return word in FIRST_NAMES or plain in FIRST_NAMES or first_part in FIRST_NAMES


def is_surname(word):
    """
    True if the word is in the Census surname list.
    The Census list stores "O'Brien" as "obrien" and has no hyphenated names,
    so we also try the word without apostrophes, and each part of a hyphenated
    name ("smith-jones" counts if "smith" or "jones" is a surname).
    """
    plain = re.sub(r"['’]", "", word)
    parts = plain.split("-")
    return plain in SURNAMES or any(part in SURNAMES for part in parts)


def last_word_is_surname(value):
    """
    True if the last word of a full name is a known surname
    ("Emily Carter" -> "carter" -> yes; "Austin Lamp" -> "lamp" -> no).
    A trailing initial with a dot ("Emily J.") is not a surname.
    """
    words = name_words(value)
    if not words or len(words) < 2:
        return False
    return is_surname(words[-1])


def check_name(value):
    """
    Return (kind, note) for one value. kind is one of:
      "full"     2-4 words and the first word is a known first name ("Emily Carter")
      "first"    1 word that is a known first name ("Emily")
      "surname"  1 word in the surname list but not the first-name list ("Gonzalez")
      None       not a name (wrong shape, or words not in either list)
    """
    words = name_words(value)
    if words is None:
        return None, "No match · not shaped like a name"
    if len(words) >= 2:
        if is_first_name(words[0]):
            return "full", "Match · full name"
        return None, f"No match · \"{words[0]}\" is not a known first name"
    word = words[0]
    if is_first_name(word):
        return "first", "Match · first name"
    if word in SURNAMES:
        return "surname", "Surname only"
    return None, "No match · not a known first name or surname"


def email_contains_name(value, email):
    """
    True if a word of the name (2+ letters) appears in the part of the email
    before "@". Example: "Emily Carter" and "emily.carter@example.com".
    Used as relational supporting evidence for the name column.
    """
    words = name_words(value)
    if not words or "@" not in email:
        return False
    local_part = email.split("@")[0].lower()
    # A generator inside any(): any(... for ...) is like JS words.some(word => ...).
    plain_words = [word.rstrip(".") for word in words]
    return any(len(word) >= 2 and word in local_part for word in plain_words)
