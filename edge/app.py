"""Minimal API entry point; business endpoints follow contract review."""

from fastapi import FastAPI

from edge.config import Settings


def create_app(settings: Settings) -> FastAPI:
    app = FastAPI(title="AquaGuard Edge", version="0.1.0")
    app.state.settings = settings

    @app.get("/health", tags=["operations"])
    def health() -> dict[str, str]:
        return {"status": "ok", "device_id": settings.device_id}

    return app
