"""Minimal API entry point; business endpoints follow contract review."""

from fastapi import FastAPI
import os

from edge.config import Settings


def create_app(settings: Settings) -> FastAPI:
    mode=os.environ.get('AQUAGUARD_RUNTIME','baseline')
    if mode in ('simulation','mqtt'):
        from edge.runtime import simulation_app
        return simulation_app(settings)
    if mode!='baseline':
        from edge.config import ConfigurationError
        raise ConfigurationError('AQUAGUARD_RUNTIME must be baseline, simulation or mqtt')
    app = FastAPI(title="AquaGuard Edge", version="0.1.0")
    app.state.settings = settings

    @app.get("/health", tags=["operations"])
    def health() -> dict[str, str]:
        return {"status": "ok", "device_id": settings.device_id}

    return app
