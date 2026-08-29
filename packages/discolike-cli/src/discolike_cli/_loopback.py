from __future__ import annotations

import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from http.server import HTTPServer
from urllib.parse import parse_qs
from urllib.parse import urlparse

LOOPBACK_HOST = "127.0.0.1"
CALLBACK_PATH = "/callback"
CALLBACK_HTML = "<!doctype html><title>DiscoLike</title><p>Login complete. You can close this window.</p>"


class _LoopbackServer(HTTPServer):
    def __init__(self, *, host: str, port: int) -> None:
        super().__init__((host, port), _CallbackHandler)
        self.query: dict[str, str] = {}
        self.received = threading.Event()


class _CallbackHandler(BaseHTTPRequestHandler):
    server: _LoopbackServer

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != CALLBACK_PATH:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        self.server.query = {key: values[0] for key, values in parse_qs(parsed.query).items()}
        body = CALLBACK_HTML.encode()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        self.server.received.set()

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002 -- BaseHTTPRequestHandler signature
        _ = (format, args)


class CallbackServer:
    """Loopback redirect target for the authorization-code flow; serves on a daemon thread."""

    def __init__(self, *, port: int) -> None:
        self._server = _LoopbackServer(host=LOOPBACK_HOST, port=port)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def redirect_uri(self) -> str:
        return f"http://{LOOPBACK_HOST}:{self._server.server_port}{CALLBACK_PATH}"

    def wait(self, *, timeout: float) -> dict[str, str] | None:
        return self._server.query if self._server.received.wait(timeout) else None

    def __enter__(self) -> CallbackServer:
        self._thread.start()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self._server.shutdown()
        self._server.server_close()
