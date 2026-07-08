from time import monotonic

from fastapi import FastAPI, Request
from pydantic import ValidationError

from src.api.routes import districts_router, health_router, weather_router
from src.config.settings import get_settings
from src.monitoring.logging import configure_logging, get_logger

LOGGER = get_logger(__name__)


def create_app() -> FastAPI:
    try:
        settings = get_settings()
        configure_logging(settings.log_level)
    except ValidationError:
        configure_logging("INFO")

    app = FastAPI(
        title="Hanoi Weather & AQI Data Platform API",
        version="0.2.0",
        description="REST API for Hanoi weather and air quality warehouse data.",
    )

    @app.middleware("http")
    async def log_api_requests(request: Request, call_next):
        started_at = monotonic()
        response = await call_next(request)
        latency_ms = round((monotonic() - started_at) * 1000, 2)
        LOGGER.info(
            "api_request",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            latency_ms=latency_ms,
            query=str(request.query_params),
        )
        return response

    app.include_router(health_router)
    app.include_router(districts_router)
    app.include_router(weather_router)
    return app


app = create_app()
