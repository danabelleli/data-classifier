"""
Build the files in data/ from the raw files downloaded from official sources.

WHY THIS SCRIPT EXISTS
The spec says every reference list must come from an official source, never
from memory or AI. This script is the only thing that touches the raw downloads:
it reads them, keeps the columns we need, and writes the small files in data/.
Anyone can re-download the sources (URLs in data/README.md) and re-run it to
check that data/ really matches the official data.

HOW TO RUN (from the project root):
    python3 scripts/build_reference_data.py <folder with the raw downloads>

The folder is expected to contain (any missing file is skipped with a warning):
    npa_report.csv                  NANPA area code report
    state.txt                       Census state codes
    Gaz_places_national.txt         Census 2010 Gazetteer, Places
    Names_2010Census.csv            Census 2010 surnames
    ssa_names/yob*.txt              SSA national baby names, one file per year
"""

import csv
import sys
from pathlib import Path

# Path(__file__) is this script's own path. .parent goes up one folder.
# Similar to path.dirname(__dirname) in Node.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"  # the "/" operator joins paths in pathlib


def build_states(raw_dir):
    """
    Write data/us_states.csv: the 50 states + DC, full name and 2-letter code.

    The Census file also lists territories (Puerto Rico, Guam, ...). The spec
    asks for 50 states + DC only, so we skip anything with a state code above 56
    (territory codes are 60 and up) and keep DC (code 11).
    Returns a dict {"TX": "Texas", ...} that the other builders reuse.
    """
    source = raw_dir / "state.txt"
    if not source.exists():
        print("WARNING: state.txt not found, skipping us_states.csv")
        return {}

    states = {}  # a Python dict is like a JS object used as a map
    # "with open(...) as f" opens the file and closes it automatically when the
    # indented block ends, even if an error happens (like try/finally in JS).
    with open(source, encoding="utf-8") as f:
        for row in csv.DictReader(f, delimiter="|"):
            if int(row["STATE"]) <= 56:
                states[row["STUSAB"]] = row["STATE_NAME"]

    with open(DATA_DIR / "us_states.csv", "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["name", "abbreviation"])
        for abbreviation, name in sorted(states.items()):
            writer.writerow([name, abbreviation])
    print(f"us_states.csv: {len(states)} rows")
    return states


def all_state_names(raw_dir):
    """
    Return {"PR": "Puerto Rico", ...} for every code in the Census state file,
    territories included. Only used to label area-code regions, because NANPA
    lists US territories (Puerto Rico 787, Guam 671) as US area codes.
    """
    source = raw_dir / "state.txt"
    if not source.exists():
        return {}
    with open(source, encoding="utf-8") as f:
        # This is a "dict comprehension": it builds a dict in one expression.
        # JS equivalent: Object.fromEntries(rows.map(r => [r.STUSAB, r.STATE_NAME]))
        return {row["STUSAB"]: row["STATE_NAME"] for row in csv.DictReader(f, delimiter="|")}


def build_area_codes(raw_dir, state_names):
    """
    Write data/area_codes.csv: US area codes that are in service, with a region.

    Kept from the NANPA report:
      - geographic codes whose COUNTRY is "US" and IN_SERVICE is "Y"
        (this includes US territories such as Puerto Rico)
      - toll-free codes (800, 888, 877, 866, 855, 844, 833) that are in service
    Canada and the Caribbean countries also use +1, but the spec is US only.
    """
    source = raw_dir / "npa_report.csv"
    if not source.exists():
        print("WARNING: npa_report.csv not found, skipping area_codes.csv")
        return

    with open(source, encoding="utf-8-sig") as f:
        lines = f.read().splitlines()
    # The first line is "File Date,<date>", the real header is on line 2.
    rows = csv.DictReader(lines[1:])

    kept = []
    for row in rows:
        if row["IN_SERVICE"] != "Y":
            continue
        is_us_geographic = row["COUNTRY"] == "US" and row["USE"] == "G"
        is_toll_free = row["SERVICE"] == "Toll-Free"
        if is_us_geographic:
            # LOCATION holds the 2-letter state code; turn it into a full name.
            region = state_names.get(row["LOCATION"], row["LOCATION"])
            kept.append([row["NPA_ID"], region, "geographic"])
        elif is_toll_free:
            kept.append([row["NPA_ID"], "Toll-free", "toll-free"])

    with open(DATA_DIR / "area_codes.csv", "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["area_code", "region", "type"])
        writer.writerows(sorted(kept))
    print(f"area_codes.csv: {len(kept)} rows")


# Census place names end with a word describing the kind of place
# ("Austin city", "Honolulu CDP"). We strip it so "Austin" can match.
# Longer descriptors come first so "city and borough" is removed whole
# instead of only removing "borough".
PLACE_SUFFIXES = [
    "consolidated government",
    "metropolitan government",
    "unified government",
    "metro government",
    "city and borough",
    "urban county",
    "municipality",
    "corporation",
    "borough",
    "village",
    "city",
    "town",
    "CDP",
]

# Census "LSAD" codes for city-county governments, for example
# "Nashville-Davidson metropolitan government (balance)". People write
# "Nashville", so for these we also store the part before "-", "/" or ",".
CONSOLIDATED_LSAD_CODES = {"00", "UG", "UC", "MG"}


def strip_place_suffix(census_name):
    """Turn "Austin city" into "Austin" and "Indianapolis city (balance)" into "Indianapolis"."""
    name = census_name.replace(" (balance)", "").strip()
    for suffix in PLACE_SUFFIXES:
        if name.endswith(" " + suffix):
            # name[: -n] is slicing: everything except the last n characters.
            # Same as name.slice(0, -n) in JS.
            return name[: -(len(suffix) + 1)].strip()
    return name


def short_consolidated_name(name):
    """For "Nashville-Davidson" return "Nashville"; None if there is nothing to shorten."""
    for separator in ["-", "/", ","]:
        if separator in name:
            return name.split(separator)[0].strip()
    return None


def build_places(raw_dir, states):
    """
    Write data/us_places.csv: place name (suffix stripped), state code, population.

    Source: Census 2010 Gazetteer, Places. We use the 2010 edition because it is
    the latest Gazetteer that includes a population column (POP10); newer
    Gazetteer files only have land area and coordinates.
    Only places in the 50 states + DC are kept.
    """
    source = raw_dir / "Gaz_places_national.txt"
    if not source.exists():
        print("WARNING: Gaz_places_national.txt not found, skipping us_places.csv")
        return

    # The 2010 Gazetteer is saved in Latin-1, not UTF-8 (for example "Cañon City").
    with open(source, encoding="latin-1") as f:
        reader = csv.DictReader(f, delimiter="\t")
        # Header cells have trailing spaces; strip them so row["POP10"] works.
        reader.fieldnames = [name.strip() for name in reader.fieldnames]
        rows = []
        for row in reader:
            state = row["USPS"].strip()
            if state not in states:
                continue
            name = strip_place_suffix(row["NAME"].strip())
            population = int(row["POP10"])
            rows.append([name, state, population])
            if row["LSAD"].strip() in CONSOLIDATED_LSAD_CODES:
                short_name = short_consolidated_name(name)
                if short_name:
                    rows.append([short_name, state, population])

    with open(DATA_DIR / "us_places.csv", "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["name", "state", "population"])
        writer.writerows(rows)
    print(f"us_places.csv: {len(rows)} rows")


# Keep only surnames shared by at least this many people (the "count" column).
# Why: the full Census list (every surname with 100+ people, 162,253 names)
# includes rare surnames that are also ordinary words, such as TABLE (134 people)
# and CHAIR (139 people). Those let a "product_name" column (Austin Table,
# Boston Chair) pass the "at least 50% of last words are known surnames" check.
# Surnames with a count of 1,000+ are only 15% of the names (24,889), but they
# still cover 77.3% of all people counted, so real name columns stay well above
# the 50% surname threshold while the rare word-like surnames are dropped.
MIN_SURNAME_COUNT = 1_000


def build_surnames(raw_dir):
    """
    Write data/surnames.txt: one lowercase surname per line, from the Census 2010
    list, keeping only surnames with a count of MIN_SURNAME_COUNT or more.
    The list ends with an "ALL OTHER NAMES" summary row, which is not a name.
    """
    source = raw_dir / "Names_2010Census.csv"
    if not source.exists():
        print("WARNING: Names_2010Census.csv not found, skipping surnames.txt")
        return
    with open(source, encoding="utf-8-sig") as f:
        names = sorted(
            {row["name"].strip().lower() for row in csv.DictReader(f)
             if int(row["count"]) >= MIN_SURNAME_COUNT}  # drop rare surnames (see above)
            - {"all other names"}
        )
    (DATA_DIR / "surnames.txt").write_text("\n".join(names) + "\n", encoding="utf-8")
    print(f"surnames.txt: {len(names)} names")


def build_first_names(raw_dir):
    """
    Write data/first_names.txt: every name in the SSA national baby names data,
    all years merged, deduplicated and lowercased.
    Each yobYYYY.txt line looks like "Emily,F,25952" (name, sex, count).
    """
    source_dir = raw_dir / "ssa_names"
    year_files = sorted(source_dir.glob("yob*.txt"))
    if not year_files:
        print("WARNING: ssa_names/yob*.txt not found, skipping first_names.txt")
        return
    names = set()  # a set keeps only unique values, like a JS Set
    for path in year_files:
        with open(path, encoding="utf-8") as f:
            for row in csv.reader(f):
                if row:
                    names.add(row[0].strip().lower())
    (DATA_DIR / "first_names.txt").write_text("\n".join(sorted(names)) + "\n", encoding="utf-8")
    print(f"first_names.txt: {len(names)} names from {len(year_files)} year files")


def main():
    """Run every builder. sys.argv is the list of command-line words, like process.argv."""
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    raw_dir = Path(sys.argv[1])
    DATA_DIR.mkdir(exist_ok=True)
    states = build_states(raw_dir)
    build_area_codes(raw_dir, all_state_names(raw_dir))
    build_places(raw_dir, states)
    build_surnames(raw_dir)
    build_first_names(raw_dir)


# This block only runs when the file is executed directly, not when imported.
if __name__ == "__main__":
    main()
