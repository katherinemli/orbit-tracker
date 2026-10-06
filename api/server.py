"""HTTP API + static file server. Standard library only.

The API never drives the mount: it reads the daemon's published snapshot
and forwards operator commands as files. A background thread samples the
snapshot once per second to keep a short history for charts.
"""

import argparse
import json
import os
import threading
import time
from collections import deque
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ALLOWED_ACTIONS = {"start", "stop", "reset"}
HISTORY_SECONDS = 300


class Store:
    """Latest snapshot plus a rolling history, shared across request threads."""

    def __init__(self, runtime: Path):
        self.runtime = runtime
        self.history = deque(maxlen=HISTORY_SECONDS)
        self.lock = threading.Lock()

    def snapshot(self) -> dict | None:
        try:
            return json.loads((self.runtime / "state.json").read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            return None

    def sample_forever(self) -> None:
        while True:
            snap = self.snapshot()
            if snap:
                with self.lock:
                    self.history.append({
                        "t": time.time(),
                        "signal_dbm": snap["signal_dbm"],
                        "error_deg": snap["error_deg"],
                        "temperature_c": snap["temperature_c"],
                    })
            time.sleep(1.0)

    def send_command(self, action: str) -> None:
        tmp = self.runtime / "command.tmp"
        tmp.write_text(json.dumps({"action": action}))
        os.replace(tmp, self.runtime / "command.json")


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, store: Store, **kwargs):
        self.store = store
        super().__init__(*args, **kwargs)

    def log_message(self, *_):  # keep the console quiet
        pass

    def send_json(self, payload, status=HTTPStatus.OK) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/api/status":
            snap = self.store.snapshot()
            if snap is None:
                return self.send_json({"error": "daemon not running"},
                                      HTTPStatus.SERVICE_UNAVAILABLE)
            return self.send_json(snap)
        if self.path == "/api/history":
            with self.store.lock:
                return self.send_json(list(self.store.history))
        if self.path.startswith("/api/"):
            return self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
        return super().do_GET()

    def do_POST(self):
        if self.path != "/api/command":
            return self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
        try:
            length = int(self.headers.get("Content-Length", 0))
            action = json.loads(self.rfile.read(length) or b"{}").get("action")
        except (ValueError, json.JSONDecodeError):
            action = None
        if action not in ALLOWED_ACTIONS:
            return self.send_json({"error": f"action must be one of {sorted(ALLOWED_ACTIONS)}"},
                                  HTTPStatus.BAD_REQUEST)
        self.store.send_command(action)
        return self.send_json({"accepted": action}, HTTPStatus.ACCEPTED)


def main() -> None:
    parser = argparse.ArgumentParser(description="Orbit Tracker API")
    parser.add_argument("--runtime", default="runtime")
    parser.add_argument("--web", default=str(Path(__file__).parent.parent / "web"))
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    store = Store(Path(args.runtime))
    threading.Thread(target=store.sample_forever, daemon=True).start()
    handler = partial(Handler, store=store, directory=args.web)
    server = ThreadingHTTPServer(("0.0.0.0", args.port), handler)
    print(f"Dashboard: http://localhost:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
