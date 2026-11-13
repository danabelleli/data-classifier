"""
Reading uploaded files out of an HTTP request.

Shared by both API endpoints (api/classify.py and api/evaluate.py), so they read
uploads exactly the same way.
"""

import json
from email.parser import BytesParser
from email.policy import HTTP
from http.server import BaseHTTPRequestHandler

# Vercel rejects request bodies above ~4.5 MB before they reach our code;
# the endpoints check too so local runs behave the same way.
MAX_UPLOAD_BYTES = int(4.5 * 1024 * 1024)


def extract_files(content_type, body):
    """
    Pull every uploaded file out of a multipart/form-data body.
    Returns a dict {form field name: (file name, file bytes)}, empty if none.

    Why the email module: a multipart upload uses the same MIME format as email
    attachments, and Python's standard library can parse it. (The older `cgi`
    module was removed in Python 3.13.) We glue the Content-Type header onto the
    body so the parser sees a complete MIME message.
    """
    message = BytesParser(policy=HTTP).parsebytes(
        b"Content-Type: " + content_type.encode() + b"\r\n\r\n" + body
    )
    files = {}
    if not message.is_multipart():
        return files
    for part in message.iter_parts():
        field = part.get_param("name", header="content-disposition")
        file_name = part.get_filename()
        if field and file_name is not None:
            files[field] = (file_name or "upload.csv", part.get_payload(decode=True) or b"")
    return files


class JsonHandler(BaseHTTPRequestHandler):
    """
    Shared base for the API endpoints: reads the uploaded files and sends JSON.
    Each endpoint subclasses it (class handler(JsonHandler)) and adds do_POST.
    Subclassing is like `class Handler extends JsonHandler` in JS.
    """

    def send_json(self, status, payload):
        """Send a JSON response with the given HTTP status code."""
        body = json.dumps(payload).encode("utf-8")  # json.dumps = JSON.stringify
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_uploads(self):
        """
        Return the uploaded files as {field name: (file name, bytes)}, or None
        after sending a 413 error if the request is over the size limit.
        """
        length = int(self.headers.get("Content-Length", 0))
        if length > MAX_UPLOAD_BYTES:
            self.send_json(413, {"error": "Upload is too large. The limit is about 4.5 MB per request."})
            return None
        body = self.rfile.read(length)
        return extract_files(self.headers.get("Content-Type", ""), body)
