"""Run with ``python -m edge``."""

from __future__ import annotations

import socket
import sys

import uvicorn

from edge.app import create_app
from edge.config import ConfigurationError, Settings


def main() -> int:
    try:
        settings = Settings.from_env()
    except ConfigurationError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    # Give an actionable failure before starting Uvicorn. Uvicorn still owns
    # the final bind, so a concurrent process can race this advisory check.
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind((settings.host, settings.port))
    except OSError as exc:
        print(f"Cannot listen on {settings.host}:{settings.port}: {exc}", file=sys.stderr)
        return 2

    try:
        app=create_app(settings)
    except (ConfigurationError,ValueError,OSError) as exc:
        print(f"Configuration error: {exc}",file=sys.stderr)
        return 2
    uvicorn.run(app, host=settings.host, port=settings.port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
