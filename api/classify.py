"""
Vercel serverless function: POST /api/classify

Receives a CSV file as a multipart upload (form field "file"), classifies every
column, and returns the results as JSON (spec 6).

Vercel runs any api/*.py file that defines a class named `handler` based on
Python's built-in BaseHTTPRequestHandler. To run it locally, use
`python3 dev_server.py` from the project root (see README).
"""

import sys
from pathlib import Path

# Make the project root importable so "from classifier ..." works, both on
# Vercel and locally. sys.path is the list of folders Python searches for
# imports (similar to NODE_PATH).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from classifier.decide import classify_file  # noqa: E402  (import after the path fix)
from classifier.upload import JsonHandler  # noqa: E402


class handler(JsonHandler):
    """
    The request handler. Python calls do_POST for POST requests.
    The lowercase class name `handler` is what Vercel looks for.
    """

    def do_POST(self):
        """Read the upload, classify it, reply with JSON (or a JSON error)."""
        uploads = self.read_uploads()
        if uploads is None:
            return  # read_uploads already sent the "too large" error
        if "file" not in uploads:
            self.send_json(400, {"error": "No file received. Send the CSV in a form field named \"file\"."})
            return
        file_name, data = uploads["file"]
        try:
            result = classify_file(data, file_name)
        except Exception as error:  # a broken file should give a readable error, not a crash
            self.send_json(400, {"error": f"Could not read this file as CSV: {error}"})
            return
        if result["column_count"] == 0:
            self.send_json(400, {"error": "The file is empty."})
            return
        self.send_json(200, result)

    def do_GET(self):
        """A GET (for example opening the URL in a browser) just explains how to use the endpoint."""
        self.send_json(405, {"error": "Use POST with a CSV file in a form field named \"file\"."})
