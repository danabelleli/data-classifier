"""
Vercel serverless function: POST /api/classify

Receives a CSV file as a multipart upload (form field "file"), classifies every
column, and returns the results as JSON (spec 6).

Vercel runs any api/*.py file that defines a class named `handler` based on
Python's built-in BaseHTTPRequestHandler. The same class also runs locally:
    python3 api/classify.py      (serves http://localhost:8000/api/classify)
"""

import json
import sys
from email.parser import BytesParser
from email.policy import HTTP
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

# Make the project root importable so "from classifier ..." works, both on
# Vercel and locally. sys.path is the list of folders Python searches for
# imports (similar to NODE_PATH).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from classifier.decide import classify_file  # noqa: E402  (import after the path fix)

# Vercel rejects request bodies above ~4.5 MB before they reach this code;
# we check too so local runs behave the same way.
MAX_UPLOAD_BYTES = int(4.5 * 1024 * 1024)


def extract_file(content_type, body):
    """
    Pull the uploaded file out of a multipart/form-data body.
    Returns (file_name, file_bytes), or (None, None) if no file was sent.

    Why the email module: a multipart upload uses the same MIME format as email
    attachments, and Python's standard library can parse it. (The older `cgi`
    module was removed in Python 3.13.) We glue the Content-Type header onto the
    body so the parser sees a complete MIME message.
    """
    message = BytesParser(policy=HTTP).parsebytes(
        b"Content-Type: " + content_type.encode() + b"\r\n\r\n" + body
    )
    if not message.is_multipart():
        return None, None
    for part in message.iter_parts():
        if part.get_param("name", header="content-disposition") == "file":
            return part.get_filename() or "upload.csv", part.get_payload(decode=True) or b""
    return None, None


class handler(BaseHTTPRequestHandler):
    """
    The request handler. Python calls do_POST for POST requests.
    The lowercase class name `handler` is what Vercel looks for.
    """

    def send_json(self, status, payload):
        """Send a JSON response with the given HTTP status code."""
        body = json.dumps(payload).encode("utf-8")  # json.dumps = JSON.stringify
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        """Read the upload, classify it, reply with JSON (or a JSON error)."""
        length = int(self.headers.get("Content-Length", 0))
        if length > MAX_UPLOAD_BYTES:
            self.send_json(413, {"error": "File is too large. The limit is about 4.5 MB."})
            return
        body = self.rfile.read(length)
        file_name, data = extract_file(self.headers.get("Content-Type", ""), body)
        if file_name is None:
            self.send_json(400, {"error": "No file received. Send the CSV in a form field named \"file\"."})
            return
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


if __name__ == "__main__":
    # Local development only. Vite forwards /api requests here (see vite.config.js).
    print("Classifier API on http://localhost:8000/api/classify")
    HTTPServer(("127.0.0.1", 8000), handler).serve_forever()
