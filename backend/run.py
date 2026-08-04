"""Entry point for the UFC Predictor desktop app.

Starts a waitress WSGI server (not Flask's dev server - see docs/SPEC.md
section 3), guards against a second instance already listening on the
chosen port, and opens the user's default browser automatically.
"""
from __future__ import annotations

import socket
import threading
import time
import webbrowser

from waitress import serve

from app import create_app
from app.config import Config


def _port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


def main() -> None:
    host = "127.0.0.1"
    port = Config.DEFAULT_PORT

    if _port_in_use(host, port):
        # Almost certainly another instance of this app is already running -
        # just focus a browser tab on it instead of starting a second server.
        webbrowser.open(f"http://{host}:{port}/")
        return

    app = create_app()

    def open_browser() -> None:
        time.sleep(1.0)
        webbrowser.open(f"http://{host}:{port}/")

    threading.Thread(target=open_browser, daemon=True).start()
    print(f"UFC Predictor running at http://{host}:{port}/  (Ctrl+C to stop)")
    serve(app, host=host, port=port)


if __name__ == "__main__":
    main()
