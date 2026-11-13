"""
Vercel serverless function: POST /api/evaluate

Receives two CSV files as a multipart upload:
  "file"     the test CSV
  "answers"  the answers CSV (column,correct_class)
and returns precision/recall per class plus the list of mistakes as JSON.
Nothing is stored: both files only live for the duration of the request.
"""

import sys
from pathlib import Path

# Make the project root importable (same as api/classify.py).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from classifier.evaluate import TestSetupError, evaluate_files  # noqa: E402
from classifier.upload import JsonHandler  # noqa: E402


class handler(JsonHandler):
    """The request handler Vercel looks for. do_POST runs one test."""

    def do_POST(self):
        """Read both uploads, run the test, reply with JSON (or a JSON error)."""
        uploads = self.read_uploads()
        if uploads is None:
            return  # read_uploads already sent the "too large" error
        missing = [label for field, label in [("file", "test CSV"), ("answers", "answers CSV")]
                   if field not in uploads]
        if missing:
            self.send_json(400, {"error": f"Missing upload: {' and '.join(missing)}."})
            return

        test_name, test_data = uploads["file"]
        _, answers_data = uploads["answers"]  # "_" = the answers file name is not needed
        try:
            result = evaluate_files(test_data, test_name, answers_data)
        except TestSetupError as error:
            # Expected problems (unmatched columns, unknown class names): list them all.
            self.send_json(400, {"error": str(error), "problems": error.problems})
            return
        except Exception as error:  # a broken file should give a readable error, not a crash
            self.send_json(400, {"error": f"Could not read the files as CSV: {error}"})
            return
        self.send_json(200, result)

    def do_GET(self):
        """A GET just explains how to use the endpoint."""
        self.send_json(405, {"error": "Use POST with form fields \"file\" (test CSV) and \"answers\" (answers CSV)."})
