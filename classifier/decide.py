"""
Thresholds, the two evaluation passes, conflict resolution, and the final
decision + reason for every column (spec 3.2, 3.3, 3.5, 3.6 and 5).

Vocabulary used in this file:
  column     a dict describing one CSV column: its name, cleaned values,
             non-empty values and, after Pass 1, a few extra facts.
  candidate  a dict describing how well ONE class fits ONE column: how many
             values matched, which supporting evidence exists, and whether
             it passes the threshold. A column gets one candidate per class.

Python note: dicts are used like plain JS objects here. The difference: keys are
read with column["name"], never column.name.
"""

from collections import Counter

from classifier import rules_city, rules_dates, rules_email, rules_name, rules_phone, rules_ssn
from classifier.cleaning import non_empty, read_csv
from classifier.headers import find_keyword

# The 6 classes, with the label shown to users.
SSN = "National ID (SSN)"
PHONE = "Phone Number"
EMAIL = "Email Address"
DOB = "Date of Birth"
NAME = "Person Name"
CITY = "City"

# Tie-break order when two classes are equally good (spec 3.5, step 3).
PRIORITY = [SSN, PHONE, EMAIL, DOB, NAME, CITY]

# Minimum non-empty values a column needs to be classified. Only an empty
# column (0 values) is skipped; 1-2 values use the same 80% rule as 3-9 values.
# Why there is no longer a minimum of 3: it was meant to stop coincidental
# matches in tiny columns, but the ambiguous cases (raw digits, single-word
# names, City, Date of Birth) already require supporting evidence. So the
# minimum mostly caused false negatives: a 2-row file with name, email, phone
# and ssn columns had every column Not classified.
MIN_VALUES = 1
SMALL_COLUMN = 10         # below this many values the threshold is 80%, else 90%
CLOSE_POINTS = 5          # "within 5 percentage points" for conflict resolution
MAX_VALUES_SHOWN = 20     # how many values the UI lists per column (OPEN: Dana to decide)


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def threshold_for(value_count, has_support):
    """
    Percentage of values that must match for a class to pass (spec 3.2).
    Supporting evidence lowers it to 50%, but values are always required.
    """
    if has_support:
        return 50
    if value_count < SMALL_COLUMN:
        return 80
    return 90


def format_percent(percent):
    """Show 100.0 as "100%" and 87.5 as "87.5%" (no ".0" for whole numbers)."""
    rounded = round(percent, 1)
    if rounded == int(rounded):
        return f"{int(rounded)}%"
    return f"{rounded}%"


def count_of(count, total):
    """ "1 of 4 values is" or "3 of 4 values are", so reason sentences read correctly."""
    return f"{count} of {total} values {'is' if count == 1 else 'are'}"


def evidence(label, status, text):
    """One row of the "Why" table in the UI. status is "Yes", "No" or "Not used"."""
    return {"label": label, "status": status, "text": text}


def not_used(text="Not used for this class"):
    """Relational evidence for classes that have none (Email, SSN, Phone)."""
    return {"status": "Not used", "text": text, "support": False}


def make_candidate(data_class, column, results, keywords, keyword_label, predicate,
                   detail="", relational=None):
    """
    Build the candidate dict for one class on one column.

    results:        {row_index: (matched, note)} for every non-empty value
    keywords:       header keywords for this class
    keyword_label:  how the keywords are named in text ("SSN", "email", ...)
    predicate:      what a matching value is, e.g. "match the email pattern"
    detail:         optional extra fact for the reason, e.g. "4 with dashes"
    relational:     {"status", "text", "support"} for the "Other columns" row

    Python note: parameters with "=" have default values, like JS
    function f(detail = "", relational = null).
    """
    relational = relational or not_used()
    header_keyword = find_keyword(column["name"], keywords)
    # sum(1 for ...) counts the items that pass the check, like
    # Object.values(results).filter(([ok]) => ok).length in JS.
    matched = sum(1 for ok, _ in results.values() if ok)
    total = len(results)
    has_support = header_keyword is not None or relational["support"]
    threshold = threshold_for(total, has_support)
    percent = 100 * matched / total if total else 0
    return {
        "data_class": data_class,
        "results": results,
        "matched": matched,
        "total": total,
        "percent": percent,
        "header_keyword": header_keyword,
        "keyword_label": keyword_label,
        "predicate": predicate,
        "detail": detail,
        "relational": relational,
        "threshold": threshold,
        "base_threshold": threshold_for(total, False),
        # Values are always required: at least one match AND the threshold.
        "passes": matched > 0 and percent >= threshold,
    }


# ---------------------------------------------------------------------------
# Pass 1: value-only checks (Email, SSN, Phone, State guard, dates)
# ---------------------------------------------------------------------------

def email_candidate(column):
    """Email: every non-empty value checked with the email pattern."""
    results = {i: rules_email.check_email(v) for i, v in column["non_empty"]}
    return make_candidate(EMAIL, column, results, rules_email.HEADER_KEYWORDS, "email",
                          "match the email pattern")


def ssn_candidate(column):
    """
    SSN: pattern + validation. The detail counts the separator styles found.
    Raw 9-digit values (no dashes or spaces) only count when the header matches
    an SSN keyword (see rules_ssn.check_ssn for why).
    """
    raw_allowed = find_keyword(column["name"], rules_ssn.HEADER_KEYWORDS) is not None
    results = {i: rules_ssn.check_ssn(v, raw_allowed) for i, v in column["non_empty"]}
    # Counter counts how often each item appears: Counter(["a", "a", "b"]) -> {"a": 2, "b": 1}
    styles = Counter(note.split(" · ")[1] for ok, note in results.values() if ok)
    detail = ", ".join(f"{count} with {style}" for style, count in styles.most_common())
    candidate = make_candidate(SSN, column, results, rules_ssn.HEADER_KEYWORDS, "SSN",
                               "match the SSN pattern and pass SSN validation", detail)
    # Explain raw values that were valid SSN digits but not counted.
    raw_count = sum(1 for _, note in results.values() if note == rules_ssn.RAW_DIGITS_NOTE)
    if raw_count:
        candidate["uncounted_note"] = (
            f"{count_of(raw_count, candidate['total'])} written as raw 9-digit numbers with no dashes "
            f"or spaces; raw digits need an SSN header, and \"{column['name']}\" has none."
        )
    return candidate


def phone_candidate(column):
    """
    Phone: US format + real area code. The detail names the most common area code.
    Raw digit values (2125550101) only count when the header matches a phone
    keyword (see rules_phone.check_phone for why).
    """
    raw_allowed = find_keyword(column["name"], rules_phone.HEADER_KEYWORDS) is not None
    results = {}
    area_codes = Counter()
    for i, v in column["non_empty"]:
        matched, note, area_code = rules_phone.check_phone(v, raw_allowed)
        results[i] = (matched, note)
        if area_code:
            area_codes[area_code] += 1
    detail = ""
    if area_codes:
        top_code, _ = area_codes.most_common(1)[0]
        detail = f"most common area code {top_code} = {rules_phone.region_of(top_code)}"
    candidate = make_candidate(PHONE, column, results, rules_phone.HEADER_KEYWORDS, "phone",
                               "match a US phone format with a real area code", detail)
    # Explain raw values that were valid phone digits but not counted.
    raw_count = sum(1 for _, note in results.values() if note == rules_phone.RAW_DIGITS_NOTE)
    if raw_count:
        candidate["uncounted_note"] = (
            f"{count_of(raw_count, candidate['total'])} written as raw digits with no formatting "
            f"(like 2125550101); raw digits need a phone header, and \"{column['name']}\" has none."
        )
    return candidate


def state_candidate(column):
    """
    State guard (spec 4.5). Not one of the 6 classes; uses the plain threshold
    (no supporting evidence) to decide if this is a state column.
    """
    results = {i: rules_city.check_state(v) for i, v in column["non_empty"]}
    return make_candidate("State", column, results, [], "state",
                          "are US state names/abbreviations")


def date_candidate(column):
    """
    Date of Birth, Step 1: how many values are valid past dates?
    Stores the parsed dates on the column for the Path 2 comparison later.
    The DOB candidate only passes here through Path 1 (birth keyword in header);
    Path 2 is decided in Pass 2.
    """
    results = {}
    column["dates"] = {}
    for i, v in column["non_empty"]:
        matched, note, parsed = rules_dates.check_date(v)
        results[i] = (matched, note)
        if parsed:
            column["dates"][i] = parsed
    candidate = make_candidate(DOB, column, results, rules_dates.BIRTH_KEYWORDS, "birth",
                               "are valid past dates")
    # A date column: enough valid dates (the header lowers the bar only if it is a birth keyword).
    column["is_date_column"] = candidate["passes"]
    candidate["passes"] = column["is_date_column"] and candidate["header_keyword"] is not None
    return candidate


def run_pass_1(column):
    """Run every value-only check for one column and store the candidates on it."""
    column["candidates"] = {
        EMAIL: email_candidate(column),
        SSN: ssn_candidate(column),
        PHONE: phone_candidate(column),
        DOB: date_candidate(column),
    }
    column["state"] = state_candidate(column)
    column["is_state_column"] = column["state"]["passes"]


# ---------------------------------------------------------------------------
# Pass 2: relational checks (City, Person Name, Date of Birth Path 2)
# ---------------------------------------------------------------------------

def city_candidate(column, state_column):
    """
    City: value rule + (city, state) pairs with the state column, if there is one.
    Relational support: at least 50% of rows are real (city, state) pairs.

    City REQUIRES supporting evidence: the values must match (same thresholds
    as every class) AND the column must have a city header keyword or 50%+
    real city/state pairs. Without it the column is Not classified.
    Why: many products, brands and collections are named after US cities. A
    "collection" column of product lines (Austin, Boston, Denver, Madison) was
    classified as City on values alone. A city word by itself cannot tell a
    place from a product name; a city header or a matching state in the same
    row can.
    """
    results = {}
    pairs = 0
    for i, v in column["non_empty"]:
        row_state = state_column["values"][i] if state_column else None
        results[i] = rules_city.check_city(v, row_state)
        if rules_city.is_city_state_pair(v, row_state):
            pairs += 1

    total = len(column["non_empty"])
    if state_column:
        share = pairs / total
        relational = {
            "status": "Yes" if share >= 0.5 else "No",
            "text": f"{pairs} of {total} rows are real city/state pairs with \"{state_column['name']}\"",
            "support": share >= 0.5,
        }
    else:
        relational = not_used("No state column in the file to pair cities with")
    candidate = make_candidate(CITY, column, results, rules_city.HEADER_KEYWORDS, "city",
                               "are US cities", relational=relational)

    has_support = candidate["header_keyword"] is not None or relational["support"]
    if candidate["passes"] and not has_support:
        # The values are enough, but City also needs support: block it and say why.
        candidate["passes"] = False
        if state_column:
            pairs_text = f"only {pairs} of {total} rows pair with a state column"
        else:
            pairs_text = "the file has no state column to pair with"
        candidate["blocked_note"] = (
            f"{candidate['matched']} of {total} values are US cities "
            f"({format_percent(candidate['percent'])}), but city needs a city header or "
            f"city/state pairs: \"{column['name']}\" has no city keyword and {pairs_text}."
        )
    return candidate


def email_cross_reference(column, email_column):
    """
    Person Name relational evidence: in how many rows does a word of the name
    appear before the "@" of the email in the same row?
    """
    if not email_column:
        return not_used("No email column to compare names with")
    total = len(column["non_empty"])
    hits = sum(
        1 for i, v in column["non_empty"]
        if rules_name.email_contains_name(v, email_column["values"][i])
    )
    share = hits / total
    return {
        "status": "Yes" if share >= 0.5 else "No",
        "text": f"{hits} of {total} names appear in \"{email_column['name']}\" in the same row",
        "support": share >= 0.5,
    }


def name_candidate(column, email_column):
    """
    Person Name (spec 4.6).

    Full names (2-4 words, first word a known first name) count on values alone.

    Single-word values (a first name only, or a surname only) count ONLY when
    the column itself has support: its header matches a name keyword, or the
    email cross-reference passes (a name word appears in the email in the same
    row, in at least 50% of rows).
    Why: the SSA first-name list and the Census surname list both contain
    ordinary words. A "loyalty_tier" column of Bronze / Silver / Gold was
    classified as Person Name because all three are in the SSA list. A single
    word alone cannot tell a name from a word; a name header or a matching
    email can.
    File-level people data (another column with SSN, email, phone or date of
    birth) is NOT support here: it says the file is about people, not that this
    column holds their names.

    Full names also need real surnames: at least 50% of the column's full-name
    values must end with a word from the Census surname list. If not, none of
    the full names count. This applies even when the header is a name keyword.
    Why: a first-name start is not enough. A "product_name" column (Austin Lamp,
    Boston Table, Denver Sofa) was classified as Person Name because Austin,
    Boston and Denver are in the SSA first-name list. Real people's last words
    are surnames; product words (Lamp, Table, Sofa) are not. The check is done
    for the column as a whole (50%), not per value, so a few rare surnames
    missing from the Census list do not break a real name column.
    """
    kinds = {i: rules_name.check_name(v) for i, v in column["non_empty"]}

    # Column-level surname check on the full-name values (see docstring).
    full_values = [v for i, v in column["non_empty"] if kinds[i][0] == "full"]
    surname_hits = sum(1 for v in full_values if rules_name.last_word_is_surname(v))
    full_names_allowed = bool(full_values) and surname_hits / len(full_values) >= 0.5
    relational = email_cross_reference(column, email_column)
    has_header = find_keyword(column["name"], rules_name.HEADER_KEYWORDS) is not None
    single_words_allowed = has_header or relational["support"]

    results = {}
    single_words_skipped = 0
    # dict.items() gives (key, value) pairs; each value here is a (kind, note) pair,
    # unpacked in the loop header like JS: for (const [i, [kind, note]] of ...)
    for i, (kind, note) in kinds.items():
        if kind == "full":
            if full_names_allowed:
                results[i] = (True, note)
            else:
                results[i] = (False, "No match · full names need known surnames as last words")
        elif kind in ("first", "surname"):
            if single_words_allowed:
                results[i] = (True, "Match · first name" if kind == "first" else "Match · surname")
            else:
                results[i] = (False, "No match · single word (needs a name header or an email match)")
                single_words_skipped += 1
        else:
            results[i] = (False, note)

    if single_words_allowed:
        predicate = "are names (full names, or single first names or surnames)"
    else:
        predicate = "are full names starting with a known first name"
    surname_text = ""
    if full_values:
        surname_share = 100 * surname_hits / len(full_values)
        surname_text = (f"{surname_hits} of {len(full_values)} last words are known surnames "
                        f"({format_percent(surname_share)})")
    candidate = make_candidate(NAME, column, results, rules_name.HEADER_KEYWORDS, "name",
                               predicate, detail=surname_text, relational=relational)

    notes = []
    if full_values and not full_names_allowed:
        notes.append(
            f"{len(full_values)} of {candidate['total']} values start with a known first name, "
            f"but only {surname_text}; full names need at least 50%."
        )
    if single_words_skipped:
        notes.append(
            f"{count_of(single_words_skipped, candidate['total'])} "
            f"{'a single word' if single_words_skipped == 1 else 'single words'}; single words "
            "need a name header or an email match, and this column has neither."
        )
    if notes:
        candidate["uncounted_note"] = " ".join(notes)
    return candidate


def birth_order(column, date_columns):
    """
    Date of Birth Path 2, condition 3: is this column the earliest date in at
    least 90% of rows, compared with every other date column?
    Returns (is_earliest, relational evidence dict).
    """
    others = [(c["name"], c["dates"]) for c in date_columns if c is not column]
    if not others:
        return False, not_used("No other date column to compare with")
    earliest, compared, later_than = rules_dates.count_earliest(column["dates"], others)
    if compared == 0:
        return False, not_used("No rows where this date and another date can be compared")
    is_earliest = earliest / compared >= 0.9
    if is_earliest:
        text = f"Earliest date in {earliest} of {compared} rows (a person is born before other events)"
    else:
        # Name the column that is most often earlier, to explain the "no".
        # max(..., key=...) picks the item with the largest key, like a reduce in JS.
        rival = max(later_than, key=later_than.get)
        text = (f"Later than \"{rival}\" in {later_than[rival]} of {compared} rows "
                "(a person is born before other events)")
    return is_earliest, {"status": "Yes" if is_earliest else "No", "text": text, "support": False}


# ---------------------------------------------------------------------------
# Conflict resolution (spec 3.5)
# ---------------------------------------------------------------------------

def resolve(candidates):
    """
    Pick the winning class among the candidates that pass.
    Returns (winner or None, note about the runner-up or "").

      1. Highest match % wins.
      2. Within 5 points of the best: a class with a header match wins.
      3. Still tied: priority SSN > Phone > Email > Date of Birth > Person Name > City.
    """
    passing = [c for c in candidates if c["passes"]]
    if not passing:
        return None, ""

    best_percent = max(c["percent"] for c in passing)
    close = [c for c in passing if best_percent - c["percent"] <= CLOSE_POINTS]
    with_header = [c for c in close if c["header_keyword"]]
    pool = with_header or close  # "or" returns the first non-empty list, like JS ||
    winner = min(pool, key=lambda c: PRIORITY.index(c["data_class"]))  # lambda = arrow function

    others = sorted((c for c in passing if c is not winner), key=lambda c: -c["percent"])
    if not others:
        return winner, ""
    runner = others[0]
    win_pct, run_pct = format_percent(winner["percent"]), format_percent(runner["percent"])
    if winner["percent"] - runner["percent"] > CLOSE_POINTS:
        why = f"{win_pct} > {run_pct}"
    elif winner["header_keyword"] and not runner["header_keyword"]:
        why = f"the header matches {winner['keyword_label']} keywords and the scores are within {CLOSE_POINTS} points"
    else:
        why = "of the priority order SSN > Phone > Email > Date of Birth > Person Name > City"
    note = f"Also {run_pct} {runner['data_class']}; {winner['data_class']} chosen because {why}."
    return winner, note


def closest_candidate(candidates):
    """
    For a Not classified column, the class that came closest (highest %, then a
    header match, then a class with values that matched its rule but were not
    counted, then priority). Used to explain why it was not classified.
    The "not counted" tie-break makes an order_id column of raw 10-digit numbers
    explain the phone rule instead of saying that nothing matched.
    """
    return min(candidates, key=lambda c: (-c["percent"], c["header_keyword"] is None,
                                          not c.get("uncounted_note"),
                                          PRIORITY.index(c["data_class"])))


# ---------------------------------------------------------------------------
# Reasons and the JSON shape returned to the UI
# ---------------------------------------------------------------------------

def header_evidence(candidate, header):
    """The "Header" row of the Why table."""
    label = candidate["keyword_label"]
    if candidate["header_keyword"]:
        return evidence("Header", "Yes", f"\"{header}\" matches {label} keywords")
    return evidence("Header", "No", f"\"{header}\" has no {label} keyword")


def values_evidence(candidate):
    """The "Values" row of the Why table, e.g. "4 of 4 match the email pattern"."""
    text = f"{candidate['matched']} of {candidate['total']} {candidate['predicate']}"
    if candidate["detail"]:
        text += f" ({candidate['detail']})"
    # A blocked candidate's values DID meet the threshold (only support was
    # missing), so its Values row is a "Yes".
    values_ok = candidate["passes"] or bool(candidate.get("blocked_note"))
    return evidence("Values", "Yes" if values_ok else "No", text)


def support_sentences(candidate, header):
    """Sentences naming the supporting evidence used, or saying none was."""
    sentences = []
    if candidate["relational"]["support"]:
        sentences.append(candidate["relational"]["text"] + ".")
    if candidate["header_keyword"]:
        sentences.append(f"Header \"{header}\" matches {candidate['keyword_label']} keywords.")
    if not sentences:
        sentences.append("No supporting evidence used.")
    return sentences


def values_sentence(candidate):
    """
    The opening sentence of a reason:
    "4 of 4 non-empty values match the email pattern (100%)."
    """
    sentence = (f"{candidate['matched']} of {candidate['total']} non-empty values "
                f"{candidate['predicate']} ({format_percent(candidate['percent'])})")
    if candidate["detail"]:
        sentence += f"; {candidate['detail']}"
    return sentence + "."


def classified_reason(candidate, header, conflict_note):
    """Full reason for a classified column."""
    parts = [values_sentence(candidate)] + support_sentences(candidate, header)
    if candidate["percent"] < candidate["base_threshold"]:
        parts.append(f"Supporting evidence lowered the threshold from "
                     f"{candidate['base_threshold']}% to {candidate['threshold']}%.")
    if candidate["data_class"] == DOB and not candidate["header_keyword"]:
        parts.append("Birth date by position: the file is about people and this is the earliest date in the row.")
    if candidate.get("uncounted_note"):  # .get returns None instead of raising if the key is missing
        parts.append(candidate["uncounted_note"])
    if conflict_note:
        parts.append(conflict_note)
    return " ".join(parts)


def date_not_birth_reason(column, candidate, has_people_column):
    """Reason for a date column with no evidence that it holds birth dates."""
    problems = ["no birth keyword in header"]
    relational = candidate["relational"]
    if relational["status"] == "Not used":
        problems.append(relational["text"][0].lower() + relational["text"][1:])
    elif relational["status"] == "No":
        problems.append("the column is " + relational["text"][0].lower() + relational["text"][1:])
    if not has_people_column:
        problems.append("the file has no Person Name or SSN column")
    return (f"{candidate['matched']} of {candidate['total']} values are valid past dates, "
            f"but no evidence they are birth dates: {', and '.join(problems)}.")


def value_rows(column, candidate, override=None):
    """
    The "Values" list for the UI: the first MAX_VALUES_SHOWN rows, each with its
    result for the class shown. override(matched, note) can rewrite a note.
    """
    rows = []
    # values[:MAX_VALUES_SHOWN] is a slice: the first N items (JS .slice(0, N)).
    for i, raw in enumerate(column["values"][:MAX_VALUES_SHOWN]):
        if raw == "":
            rows.append({"value": "(empty)", "result": "Empty"})
        elif candidate is None:
            rows.append({"value": raw, "result": "—"})
        else:
            matched, note = candidate["results"][i]
            rows.append({"value": raw, "result": override(matched, note) if override else note})
    return rows


def build_result(column, winner, conflict_note, context):
    """
    Turn a column's decision into the JSON shape the UI expects (spec 6).
    `context` holds file-level facts needed for the wording of some reasons.
    """
    header = column["name"]
    base = {"name": header, "data_class": None, "match_percent": None, "checked_class": None}

    if winner:
        base.update({  # dict.update merges keys in, like Object.assign(base, {...})
            "data_class": winner["data_class"],
            "match_percent": round(winner["percent"], 1),
            "checked_class": winner["data_class"],
            "reason": classified_reason(winner, header, conflict_note),
            "evidence": [values_evidence(winner), header_evidence(winner, header),
                         evidence("Other columns", winner["relational"]["status"],
                                  winner["relational"]["text"])],
            "values": value_rows(column, winner),
        })
        return base

    count = len(column["non_empty"])
    if count < MIN_VALUES:
        # With MIN_VALUES = 1 this only happens for an empty column.
        text = "0 non-empty values; the column is empty"
        base.update({
            "reason": "Not enough data: the column has no non-empty values to classify.",
            "evidence": [evidence("Values", "No", text), evidence("Header", "Not used", ""),
                         evidence("Other columns", "Not used", "")],
            "values": value_rows(column, None),
        })
        return base

    if column["is_state_column"]:
        state = column["state"]
        used_by = context["cities_paired_with"].get(header)
        # values_sentence ends with "."; [:-1] slices that last character off.
        reason = (f"{values_sentence(state)[:-1]}, so this is a state column. "
                  "State is not one of the 6 classes, so it is Not classified.")
        other = evidence("Other columns", "Not used", "Not paired with a city column")
        if used_by:
            reason += f" Used to check city/state pairs for \"{used_by}\"."
            other = evidence("Other columns", "Yes", f"Confirms the city/state pairs for \"{used_by}\"")
        base.update({
            "checked_class": "State",
            "reason": reason,
            "evidence": [evidence("Values", "Yes", f"{state['matched']} of {state['total']} are US "
                                  "state names/abbreviations; State is not one of the 6 classes"),
                         evidence("Header", "Not used", "Not needed for the state check"), other],
            "values": value_rows(column, state),
        })
        return base

    candidates = list(column["candidates"].values())
    if column["is_date_column"]:
        dob = column["candidates"][DOB]
        base.update({
            "checked_class": DOB,
            "reason": date_not_birth_reason(column, dob, context["has_people_column"]),
            "evidence": [evidence("Values", "Yes", f"{dob['matched']} of {dob['total']} are valid past dates"),
                         header_evidence(dob, header),
                         evidence("Other columns", dob["relational"]["status"], dob["relational"]["text"])],
            "values": value_rows(column, dob, lambda ok, note: "Valid date, not a birth date" if ok else note),
        })
        return base

    closest = closest_candidate(candidates)
    if closest["matched"] == 0 and not closest["header_keyword"] and not closest.get("uncounted_note"):
        base.update({
            "reason": f"None of the 6 classes match: 0 of {count} non-empty values fit any class rule.",
            "evidence": [evidence("Values", "No", f"0 of {count} fit any class rule"),
                         evidence("Header", "No", f"\"{header}\" has no class keyword"),
                         evidence("Other columns", "Not used", "")],
            "values": value_rows(column, None),
        })
        return base

    if closest.get("blocked_note"):
        # Values met the threshold but required support was missing (City).
        reason = f"Closest class: {closest['data_class']}. {closest['blocked_note']}"
    else:
        reason = (f"Closest class: {closest['data_class']}. {values_sentence(closest)[:-1]}, "
                  f"below the {closest['threshold']}% needed. ")
        reason += " ".join(support_sentences(closest, header))
    if closest.get("uncounted_note"):  # .get returns None instead of raising if the key is missing
        reason += " " + closest["uncounted_note"]
    base.update({
        "checked_class": closest["data_class"],
        "reason": reason,
        "evidence": [values_evidence(closest), header_evidence(closest, header),
                     evidence("Other columns", closest["relational"]["status"], closest["relational"]["text"])],
        "values": value_rows(column, closest),
    })
    return base


# ---------------------------------------------------------------------------
# The whole file
# ---------------------------------------------------------------------------

def make_columns(headers, rows):
    """
    Turn the header list and the rows (lists of already-cleaned strings) into
    one column dict per header. Blank headers get a placeholder name.
    """
    columns = []
    for index, header in enumerate(headers):
        values = [row[index] if index < len(row) else "" for row in rows]
        columns.append({
            "index": index,  # position in the file; headers can repeat, positions cannot
            "name": header or f"column_{index + 1}",
            "values": values,
            "non_empty": non_empty(values),
        })
    return columns


def classify_columns(headers, rows):
    """
    Classify every column. Returns a list of result dicts (spec 6, "columns").

    Order of evaluation (spec 5):
      Pass 1  value-only checks; decide Email, SSN, Phone, State, DOB Path 1.
      Pass 2  City (with state pairs), Person Name (with email cross-reference),
              then DOB Path 2. Conflict resolution last.
    """
    columns = make_columns(headers, rows)
    # Empty columns are never classified, so they are skipped
    # (and cannot act as a state, email or date column for other columns).
    usable = [c for c in columns if len(c["non_empty"]) >= MIN_VALUES]

    # ---- Pass 1 ----
    for column in usable:
        run_pass_1(column)

    def passes(column, data_class):
        return column["candidates"][data_class]["passes"]

    state_column = next((c for c in usable if c["is_state_column"]), None)  # first match, or None
    email_column = next((c for c in usable if passes(c, EMAIL)), None)

    # ---- Pass 2: City and Person Name ----
    for column in usable:
        if column["is_state_column"]:
            continue
        column["candidates"][CITY] = city_candidate(column, state_column)
        column["candidates"][NAME] = name_candidate(
            column, email_column if email_column is not column else None)

    winners = {}
    for column in usable:
        if not column["is_state_column"]:
            winners[column["index"]] = resolve(column["candidates"].values())

    # ---- Pass 2: Date of Birth Path 2 ----
    has_people_column = any(w and w["data_class"] in (NAME, SSN) for w, _ in winners.values())
    date_columns = [c for c in usable if c.get("is_date_column")]
    for column in date_columns:
        is_earliest, relational = birth_order(column, date_columns)
        dob = column["candidates"][DOB]
        dob["relational"] = relational
        if not dob["passes"] and has_people_column and len(date_columns) >= 2 and is_earliest:
            dob["passes"] = True
            winners[column["index"]] = resolve(column["candidates"].values())

    context = {
        "has_people_column": has_people_column,
        "cities_paired_with": {},
    }
    if state_column:
        for column in usable:
            winner = winners.get(column["index"], (None, ""))[0]
            if winner and winner["data_class"] == CITY and winner["relational"]["status"] != "Not used":
                context["cities_paired_with"][state_column["name"]] = column["name"]

    results = []
    for column in columns:
        winner, note = winners.get(column["index"], (None, ""))
        results.append(build_result(column, winner, note, context))
    return results


def classify_file(data, file_name):
    """
    Classify an uploaded CSV file (raw bytes). Returns the JSON-ready dict of spec 6.
    This is the one function the API calls.
    """
    headers, rows = read_csv(data)
    return {
        "file_name": file_name,
        "row_count": len(rows),
        "column_count": len(headers),
        "columns": classify_columns(headers, rows),
    }
