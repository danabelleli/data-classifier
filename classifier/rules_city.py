"""
City and US state detection, US only (spec 4.5).

State is checked first: a column of "TX", "CA" is a state column, not a city
column. State is not one of the 6 classes, so it ends up Not classified, but it
is remembered so City can check (city, state) pairs row by row.
"""

import csv
import re
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

HEADER_KEYWORDS = ["city", "town", "municipality", "locality"]

# Cities with at least this many people are recognized without a state column.
# Smaller places need a matching state in the same row, because tiny places
# share names with ordinary words and first names.
BIG_CITY_POPULATION = 10_000  # Python allows "_" in numbers for readability


def load_states():
    """
    Read data/us_states.csv (from the Census) into a dict mapping both the
    lowercase full name and the lowercase abbreviation to the abbreviation:
    {"texas": "TX", "tx": "TX", ...}. One lookup then handles both spellings.
    """
    states = {}
    with open(DATA_DIR / "us_states.csv", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            states[row["name"].lower()] = row["abbreviation"]
            states[row["abbreviation"].lower()] = row["abbreviation"]
    return states


STATES = load_states()


def normalize_city(text):
    """
    Put a city name into a standard form so different spellings compare equal.

    Lowercase, collapse spaces, and expand common abbreviations:
    "St. Louis" -> "saint louis", "Ft. Worth" -> "fort worth", "Mt. Vernon" -> "mount vernon".
    The same function is applied to the Census names and to the uploaded values.
    """
    text = re.sub(r"\s+", " ", text.lower()).strip()
    # \b is a word boundary, so "st" inside "west" is not touched.
    # \.? means "an optional dot".
    text = re.sub(r"\bst\b\.?", "saint", text)
    text = re.sub(r"\bft\b\.?", "fort", text)
    text = re.sub(r"\bmt\b\.?", "mount", text)
    return re.sub(r"\s+", " ", text).strip()


def split_trailing_state(value):
    """
    Split "Austin, TX" or "Austin, Texas" into ("Austin", "TX").
    Returns (value, None) when there is no trailing state.
    """
    if "," in value:
        # rsplit(",", 1) splits once, starting from the right.
        city_part, state_part = value.rsplit(",", 1)
        state = STATES.get(state_part.strip().lower())
        if state:
            return city_part.strip(), state
    return value, None


def load_places():
    """
    Read data/us_places.csv (Census Gazetteer) and build two lookups:

    places_by_pair: {("austin", "TX"): ("Austin", 790390), ...}  every place, any size
    big_cities:     {"austin": ("Austin", "TX", 790390), ...}     population >= 10,000;
                    if several states have a big city with that name, keep the largest.

    Python note: a tuple like ("austin", "TX") can be a dict key. JS objects
    only allow string keys, so this has no direct JS equivalent besides a Map
    with a joined string key.
    """
    places_by_pair = {}
    big_cities = {}
    with open(DATA_DIR / "us_places.csv", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            name, state, population = row["name"], row["state"], int(row["population"])
            key = normalize_city(name)
            places_by_pair[(key, state)] = (name, population)
            if population >= BIG_CITY_POPULATION:
                current = big_cities.get(key)
                if current is None or population > current[2]:
                    big_cities[key] = (name, state, population)
    return places_by_pair, big_cities


PLACES_BY_PAIR, BIG_CITIES = load_places()


def check_state(value):
    """
    Return (matched, note) for the state guard: is this value a US state name or
    2-letter abbreviation? Case-insensitive: "tx", "TX", "Texas" all match.
    """
    abbreviation = STATES.get(value.strip().lower())
    if abbreviation:
        return True, f"State · {abbreviation}"
    return False, "Not a US state"


def is_city_state_pair(value, row_state):
    """
    True when (city, state) from the same row exists in the FULL Census list.
    row_state is the state column's value in this row (or None).
    This is what lets small towns count: "Marfa" alone is unknown, but
    ("Marfa", "TX") is a real place.
    """
    city_text, state_in_value = split_trailing_state(value)
    state = state_in_value or (STATES.get(row_state.strip().lower()) if row_state else None)
    if not state:
        return False
    return (normalize_city(city_text), state) in PLACES_BY_PAIR


def check_city(value, row_state=None):
    """
    Return (matched, note) for one value.

    A value counts as a city if it is a US place with >= 10,000 people, or if it
    forms a real (city, state) pair with the state in the same row.
    A state written in the value itself ("Austin, TX") is used like a state column.
    """
    city_text, state_in_value = split_trailing_state(value)
    key = normalize_city(city_text)
    state = state_in_value or (STATES.get(row_state.strip().lower()) if row_state else None)

    if state and (key, state) in PLACES_BY_PAIR:
        name, _ = PLACES_BY_PAIR[(key, state)]  # "_" is a conventional name for "unused"
        return True, f"Match · {name}, {state}"
    if key in BIG_CITIES:
        name, big_state, _ = BIG_CITIES[key]
        return True, f"Match · {name}, {big_state}"
    return False, "No match · not a US city with 10,000+ people or a known city/state pair"
