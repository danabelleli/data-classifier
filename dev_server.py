"""
Local development server for the Python API. Not used on Vercel.

On Vercel, each file in api/ is its own function at its own URL. Locally we
need one server that sends each URL to the right file, which is what this does:
    /api/classify  -> api/classify.py
    /api/evaluate  -> api/evaluate.py

Run from the project root:
    python3 dev_server.py
Vite (npm run dev) forwards /api requests here; see vite.config.js.
"""

import importlib.util
from http.server import HTTPServer
from pathlib import Path

from classifier.upload import JsonHandler

API_DIR = Path(__file__).resolve().parent / "api"


def load_handler(file_name):
    """
    Load the `handler` class from a file in api/.
    The api folder is not a Python package, so we load the file by its path
    (roughly what require("./api/classify.py") would do in Node).
    """
    spec = importlib.util.spec_from_file_location(file_name, API_DIR / file_name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.handler


ROUTES = {
    "/api/classify": load_handler("classify.py"),
    "/api/evaluate": load_handler("evaluate.py"),
}


class DevHandler(JsonHandler):
    """
    One handler for every local request: it looks at the URL and runs the
    do_POST of the matching api/ file.

    Python note: ROUTES[path].do_POST(self) calls another class's method with
    this request as `self`. It works because both classes share JsonHandler,
    so the method finds the send_json/read_uploads it needs.
    """

    def do_POST(self):
        target = ROUTES.get(self.path.split("?")[0])  # ignore any ?query part
        if target is None:
            self.send_json(404, {"error": f"No API at {self.path}"})
            return
        target.do_POST(self)


if __name__ == "__main__":
    print("Classifier API on http://localhost:8000 (/api/classify, /api/evaluate)")
    HTTPServer(("127.0.0.1", 8000), DevHandler).serve_forever()
