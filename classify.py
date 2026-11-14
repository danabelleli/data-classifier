"""
Command-line way to run the classifier, without the web app.

Usage (from the project root):
    python3 classify.py path/to/file.csv          one line per column + its reason
    python3 classify.py path/to/file.csv --json   the full results as JSON

It calls classify_file(), the exact same function the web app's API calls, so
the results and reasons are always identical to what the web app shows. No
rules are copied here. Standard library only: nothing to install.
"""

import argparse
import json
import sys

from classifier.cleaning import NOT_A_CSV, CsvReadError
from classifier.decide import classify_file
from classifier.upload import MAX_UPLOAD_BYTES

# Same wording as the web app (classifier/upload.py and src/ClassifierPage.jsx).
TOO_LARGE = "This file is larger than 4.5 MB, the upload limit."


def fail(message):
    """
    Print an error message and stop with exit code 1 (the usual "something went
    wrong" signal for command-line tools). Errors go to stderr so that
    `--json > out.json` never writes an error into the JSON file.
    """
    print(message, file=sys.stderr)
    sys.exit(1)


def read_file(path):
    """
    Read the file as raw bytes, exactly as the web app receives an upload.
    A missing or unreadable path gives a plain message instead of a Python error.
    """
    try:
        with open(path, "rb") as f:  # "rb" = read bytes; classify_file decodes them itself
            return f.read()
    except FileNotFoundError:
        fail(f"File not found: {path}")
    except IsADirectoryError:
        fail(f"This is a folder, not a file: {path}")
    except OSError as error:  # no permission, disk error, ...
        fail(f"Could not open {path}: {error.strerror}")


def print_text(result):
    """
    Print each column as:
        Column "full_name" -> Person Name
        Reason: <reason>
    with a blank line between columns. data_class is None for Not classified.
    """
    for column in result["columns"]:
        data_class = column["data_class"] or "Not classified"
        print(f'Column "{column["name"]}" -> {data_class}')
        print(f"Reason: {column['reason']}")
        print()


def main():
    # argparse reads the command-line arguments and prints a usage message
    # (and --help) automatically when they are wrong.
    parser = argparse.ArgumentParser(description="Classify the columns of a CSV file.")
    parser.add_argument("path", help="the CSV file to classify")
    parser.add_argument("--json", action="store_true", help="print the results as JSON")
    args = parser.parse_args()

    data = read_file(args.path)

    # The web app refuses files over 4.5 MB. The same limit applies here so the
    # command line always gives the same answer as the web app for a file.
    if len(data) > MAX_UPLOAD_BYTES:
        fail(TOO_LARGE)

    # Same error handling as api/classify.py: known file problems show their
    # user-facing message, anything unexpected shows the general CSV message.
    try:
        result = classify_file(data, args.path)
    except CsvReadError as error:
        fail(str(error))
    except Exception:
        fail(NOT_A_CSV)

    if args.json:
        # ensure_ascii=False keeps accented letters readable (José, not José).
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print_text(result)


# Runs main() only when the file is run directly (python3 classify.py ...),
# not when another file imports it.
if __name__ == "__main__":
    main()
