"""Strict startup configuration for the local development service."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass


class ConfigurationError(ValueError):
    """The service cannot start with the supplied configuration."""


@dataclass(frozen=True)
class Settings:
    device_id: str
    host: str
    port: int

    @classmethod
    def from_env(cls, environ: dict[str, str] | None = None) -> "Settings":
        values = os.environ if environ is None else environ
        device_id = values.get("AQUAGUARD_DEVICE_ID", "").strip()
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", device_id):
            raise ConfigurationError(
                "AQUAGUARD_DEVICE_ID is required (1-64 ASCII letters, digits, _ or -)."
            )
        host = values.get("AQUAGUARD_HOST", "127.0.0.1").strip()
        if host not in {"127.0.0.1", "localhost"}:
            raise ConfigurationError("AQUAGUARD_HOST must be 127.0.0.1 or localhost for this local baseline.")
        raw_port = values.get("AQUAGUARD_PORT", "8000").strip()
        try:
            port = int(raw_port)
        except ValueError as exc:
            raise ConfigurationError("AQUAGUARD_PORT must be an integer from 1 to 65535.") from exc
        if not 1 <= port <= 65535:
            raise ConfigurationError("AQUAGUARD_PORT must be an integer from 1 to 65535.")
        return cls(device_id=device_id, host=host, port=port)
