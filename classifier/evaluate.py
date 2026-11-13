"""
Test results: compare the app's decisions with correct answers written by a
person, and measure precision and recall for each class.

This file does not classify anything itself. It calls classify_file(), the
exact same function the Classifier page uses, so the test results always
measure the real rules.

Inputs
  test CSV     the file to test
  answers CSV  one row per column of the test CSV:
                   column,correct_class
                   full_name,Person Name
                   title,Not classified

Counting, for each of the 6 classes (C = the class being counted):
  True positive  (TP)  app said C, correct answer is C
  False positive (FP)  app said C, correct answer is something else
  False negative (FN)  correct answer is C, app said something else
  True negative  (TN)  neither the app nor the correct answer is C
A column given the wrong class (app says City, correct answer is Person Name)
counts as an FP for City AND an FN for Person Name.

  Precision = TP / (TP + FP)   of the columns labeled C, how many were right
  Recall    = TP / (TP + FN)   of the columns that really are C, how many were found
"""

import csv
import io
from collections import Counter

from classifier.cleaning import decode_text
from classifier.decide import CITY, DOB, EMAIL, NAME, PHONE, SSN, classify_file

NOT_CLASSIFIED = "Not classified"

# The 6 classes in the order the table shows them (same order as the spec).
CLASSES = [SSN, CITY, NAME, PHONE, EMAIL, DOB]

# Every name allowed in the correct_class column.
ALLOWED_ANSWERS = CLASSES + [NOT_CLASSIFIED]

FP_LABEL = "False positive (FP)"
FN_LABEL = "False negative (FN)"


class TestSetupError(Exception):
    """
    Raised when the two files cannot be compared (missing answers, unknown class
    names, ...). It carries the full list of problems so the user can fix them
    all at once instead of one per run.

    Python note: defining a class that inherits from Exception is how you make
    a custom error type, like `class TestSetupError extends Error` in JS.
    """

    def __init__(self, message, problems):
        super().__init__(message)  # super() calls the parent class, as in JS
        self.problems = problems


def read_answers(data):
    """
    Read the answers CSV into a list of (row number, column name, correct class).
    Also returns a list of problems found while reading.
    A row with an unknown class name is reported as a problem but still kept
    (with correct class None), so its column is not ALSO reported as "has no answer".

    Rules (decided with Dana):
      - the header must be exactly "column,correct_class" (spaces around it are ignored)
      - spaces around values are ignored, but capitalization must match exactly:
        "Person Name" is accepted, "person name" is a problem
    Row numbers count the header as row 1, so they match what a spreadsheet shows.
    """
    reader = csv.reader(io.StringIO(decode_text(data)))
    header = [cell.strip() for cell in next(reader, [])]
    if header[:2] != ["column", "correct_class"]:
        found = ",".join(header) if header else "nothing"
        raise TestSetupError("The answers CSV has the wrong header.",
                             [f"The first row must be \"column,correct_class\" (found \"{found}\")."])

    answers = []
    problems = []
    # enumerate(reader, start=2): count rows from 2, because row 1 is the header.
    for row_number, row in enumerate(reader, start=2):
        if not any(cell.strip() for cell in row):
            continue  # skip blank lines
        column = row[0].strip() if len(row) > 0 else ""
        correct = row[1].strip() if len(row) > 1 else ""
        if not column:
            problems.append(f"Answers row {row_number}: the column name is empty.")
            continue
        if correct not in ALLOWED_ANSWERS:
            problems.append(
                f"Answers row {row_number}: \"{correct}\" for column \"{column}\" is not a class name. "
                f"Use one of: {', '.join(ALLOWED_ANSWERS)}."
            )
            correct = None
        answers.append((row_number, column, correct))
    return answers, problems


def match_answers(column_names, answers):
    """
    Check that the test file and the answers line up one-to-one, and return
    {column name: correct class}. Raises TestSetupError listing every problem.

    Decided with Dana: if anything does not line up, stop instead of skipping,
    so precision and recall are never based on a partial comparison.
    """
    problems = []

    # Counter counts how often each name appears: Counter(["a", "a"]) -> {"a": 2}
    for name, count in Counter(column_names).items():
        if count > 1:
            problems.append(f"Test CSV: column \"{name}\" appears {count} times, so it cannot be matched to one answer.")

    answer_counts = Counter(column for _, column, _ in answers)
    for name, count in answer_counts.items():
        if count > 1:
            problems.append(f"Answers CSV: column \"{name}\" has {count} answers; give it exactly one.")

    answer_names = set(answer_counts)  # set(...) of a Counter = its keys
    for name in column_names:
        if name not in answer_names:
            problems.append(f"Column \"{name}\" is in the test CSV but has no answer.")
    for name in answer_counts:
        if name not in column_names:
            problems.append(f"Column \"{name}\" has an answer but is not in the test CSV.")

    if problems:
        raise TestSetupError("The test CSV and the answers CSV do not line up.", problems)
    return {column: correct for _, column, correct in answers}


def ratio_percent(top, bottom):
    """Return top / bottom as a percentage, or None when bottom is 0 (shown as "—")."""
    if bottom == 0:
        return None
    return round(100 * top / bottom, 1)


def count_by_class(pairs):
    """
    pairs: list of (app said, correct answer) for every column.
    Returns one dict per class with TP, FP, FN, TN, precision and recall.
    """
    rows = []
    for data_class in CLASSES:
        tp = sum(1 for said, correct in pairs if said == data_class and correct == data_class)
        fp = sum(1 for said, correct in pairs if said == data_class and correct != data_class)
        fn = sum(1 for said, correct in pairs if said != data_class and correct == data_class)
        tn = sum(1 for said, correct in pairs if said != data_class and correct != data_class)
        rows.append({
            "data_class": data_class,
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "tn": tn,
            "precision": ratio_percent(tp, tp + fp),
            "recall": ratio_percent(tp, tp + fn),
        })
    return rows


def mistake_types(said, correct):
    """
    Which kinds of mistake a wrong column is.
    App said a class      -> an FP for that class.
    Correct answer a class -> an FN for that class.
    A wrong class (City instead of Person Name) is both.
    """
    types = []
    if said != NOT_CLASSIFIED:
        types.append(FP_LABEL)
    if correct != NOT_CLASSIFIED:
        types.append(FN_LABEL)
    return types


def evaluate_files(test_data, test_name, answers_data):
    """
    Run the whole test: classify the test CSV, check the answers, compare.
    Returns the JSON-ready dict for the Test results page.
    """
    answers, problems = read_answers(answers_data)
    classified = classify_file(test_data, test_name)  # the same call the Classifier page makes
    column_names = [column["name"] for column in classified["columns"]]
    try:
        correct_by_column = match_answers(column_names, answers)
    except TestSetupError as error:
        problems += error.problems
    if problems:
        raise TestSetupError("The test could not run. Fix these problems and try again.", problems)

    pairs = []
    mistakes = []
    for column in classified["columns"]:
        said = column["data_class"] or NOT_CLASSIFIED  # data_class is None for Not classified
        correct = correct_by_column[column["name"]]
        pairs.append((said, correct))
        if said != correct:
            mistakes.append({
                "file": test_name,
                "column": column["name"],
                "app_said": said,
                "correct_class": correct,
                "types": mistake_types(said, correct),
                "reason": column["reason"],
            })

    return {
        "file_name": test_name,
        "column_count": len(pairs),
        "classes": count_by_class(pairs),
        "mistakes": mistakes,
    }
