"""Entry point for the MMA Assist backend.

Starts a waitress WSGI server (not Flask's dev server - see docs/SPEC.md
section 3). Runs in two modes:

* Standalone - launched directly, binds the default port and opens the
  user's browser. Unchanged behaviour for anyone running `python run.py`.
* Embedded - launched by the Electron shell (desktop/), which picks a free
  port and passes `--port N --no-browser`. Electron owns the window, so
  opening a browser tab as well would be wrong.

On startup it prints a machine-readable `UFC_PREDICTOR_READY <url>` line;
the Electron main process watches stdout for it as a fast path, and polls
/health as the authoritative check.
"""
from __future__ import annotations

import argparse
import os
import socket
import sys
import threading
import time
import webbrowser

from waitress import serve

from app import create_app
from app.config import Config
from app.version import set_current_version

READY_PREFIX = "UFC_PREDICTOR_READY"


def _port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the MMA Assist backend server")
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("UFC_PREDICTOR_PORT") or 0) or None,
        help=f"Port to bind (default: {Config.DEFAULT_PORT}). Electron passes a free port here.",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Interface to bind (default: 127.0.0.1)")
    parser.add_argument(
        "--no-browser",
        action="store_true",
        default=os.environ.get("UFC_PREDICTOR_NO_BROWSER") == "1",
        help="Don't open a browser tab - used when a shell (Electron) provides the window",
    )
    parser.add_argument(
        "--app-version",
        default=os.environ.get("UFC_PREDICTOR_APP_VERSION"),
        help=(
            "Version of the installed desktop app, passed by the Electron shell. "
            "Omitted means a dev run, which disables update checks rather than "
            "comparing against a made-up version."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    set_current_version(args.app_version)
    host = args.host
    port = args.port or Config.DEFAULT_PORT
    url = f"http://{host}:{port}/"

    if _port_in_use(host, port):
        if args.no_browser:
            # Electron picked this port moments ago, so something else
            # grabbing it means the launch is genuinely broken - failing
            # loudly beats silently attaching to a stranger's server.
            print(f"ERROR: port {port} is already in use", file=sys.stderr, flush=True)
            raise SystemExit(1)
        # Standalone: almost certainly another copy of this app is already
        # running, so focus a tab on it rather than starting a second server.
        webbrowser.open(url)
        return

    app = create_app()

    if not args.no_browser:
        def open_browser() -> None:
            time.sleep(1.0)
            webbrowser.open(url)

        threading.Thread(target=open_browser, daemon=True).start()

    # Printed before serve() blocks. Electron reads this to learn the URL.
    print(f"{READY_PREFIX} {url}", flush=True)
    print(f"MMA Assist running at {url}  (Ctrl+C to stop)", flush=True)
    serve(app, host=host, port=port)


if __name__ == "__main__":
    main()
