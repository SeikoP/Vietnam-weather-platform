"""API route modules."""

from .districts import router as districts_router
from .health import router as health_router
from .weather import router as weather_router

__all__ = ["districts_router", "health_router", "weather_router"]
