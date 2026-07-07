from time import monotonic

from fastapi import FastAPI, Request
from pydantic import ValidationError

from src.api.routes import health, provinces, weather
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
        title="Vietnam Weather Data Platform API",
        version="0.1.0",
        description="REST API for Vietnam weather warehouse data.",
    )

    @app.middleware("http")
    async def log_api_requests(request: Request, call_next):
        started_at = monotonic()
        response = await call_next(request)
        latency_ms = round((monotonic() - started_at) * 1000, 2)
        try:
            from src.database.models import ApiRequest
            from src.database.session import SessionLocal

            with SessionLocal() as session:
                session.add(
                    ApiRequest(
                        endpoint=str(request.url.path),
                        method=request.method,
                        status_code=response.status_code,
                        latency_ms=latency_ms,
                        context={"query": str(request.query_params)},
                    )
                )
                session.commit()
        except Exception as exc:
            LOGGER.warning("api_request_log_failed", error=str(exc))
        return response

    app.include_router(health.router)
    app.include_router(provinces.router)
    app.include_router(weather.router)
    return app


app = create_app()