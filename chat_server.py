from __future__ import annotations

import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import RLock

from business_ai.app import build_orchestrator
from business_ai.core.models import TaskRequest

BASE_DIR = Path(__file__).parent
UI_FILE = BASE_DIR / "ui" / "index.html"
STATIC_DIR = BASE_DIR / "ui" / "assets"
HOST = "127.0.0.1"
PORT = 8000

orchestrator = build_orchestrator()
lock = RLock()


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, payload: dict, status: int = 200) -> None:
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _send_text(self, text: str, status: int = 200, content_type: str = "text/plain") -> None:
        raw = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        if self.path == "/":
            if not UI_FILE.exists():
                self._send_text("UI not found", 404)
                return
            self._send_text(UI_FILE.read_text(encoding="utf-8"), content_type="text/html")
            return

        if self.path.startswith("/static/"):
            rel = self.path.removeprefix("/static/").strip("/")
            target = (STATIC_DIR / rel).resolve()
            if not str(target).startswith(str(STATIC_DIR.resolve())) or not target.is_file():
                self._send_text("Not found", 404)
                return
            body = target.read_bytes()
            ctype, _ = mimetypes.guess_type(str(target))
            self.send_response(200)
            self.send_header("Content-Type", ctype or "application/octet-stream")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if self.path == "/health":
            self._send_json({"status": "ok"})
            return

        self._send_text("Not found", 404)

    def do_POST(self) -> None:
        if self.path != "/api/chat":
            self._send_text("Not found", 404)
            return

        content_len = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(content_len)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            self._send_json({"error": "Invalid JSON"}, status=400)
            return

        message = str(payload.get("message") or "").strip()
        if not message:
            self._send_json({"error": "Message is required"}, status=400)
            return

        project_id = str(payload.get("project_id") or "white board")
        conversation_id = str(payload.get("conversation_id") or "conversation-1")
        metadata = payload.get("metadata") or {}

        req = TaskRequest(
            text=message,
            project_id=project_id,
            conversation_id=conversation_id,
            metadata=metadata,
        )

        with lock:
            result = orchestrator.run(req)

        self._send_json({
            "domain": result.domain,
            "response": result.response,
            "data": result.data,
            "project_id": project_id,
            "conversation_id": conversation_id,
        })


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Friday running on http://{HOST}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
