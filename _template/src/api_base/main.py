"""Application factory and process wiring.

Code is grouped by feature: `api_base/item/` holds that entity's model, schema,
repository, service, and wiring. Routers are the exception and live together in
`api_base/routers/`.

Grouping by feature does not relax the layering rule:

    router -> service -> repository -> model

Each layer talks only to the one below it. See the README, and the docstrings in
`api_base/item/__init__.py` and `api_base/routers/__init__.py`.
"""

import json
import logging
import logging.config
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api_base import __version__
from api_base.config import Settings, get_settings
from api_base.db import dispose_engine
from api_base.exceptions import register_exception_handlers
from api_base.routers.health import router as health_router

# --- example feature ---
from api_base.routers.item import router as item_router

# --- end example feature ---

logger = logging.getLogger(__name__)


class JsonFormatter(logging.Formatter):
    """One JSON object per line, which is what log shippers want."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(settings: Settings) -> None:
    """Called once from `create_app`. Also takes over uvicorn's own loggers."""
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            # The class object, not a dotted string: this module is still being
            # imported when `app = create_app()` runs at the bottom of the file.
            "formatters": {"json": {"()": JsonFormatter}},
            "handlers": {
                "stdout": {
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stdout",
                    "formatter": "json",
                }
            },
            "root": {"handlers": ["stdout"], "level": settings.log_level},
            "loggers": {
                "uvicorn": {
                    "handlers": ["stdout"],
                    "level": settings.log_level,
                    "propagate": False,
                },
                "uvicorn.access": {
                    "handlers": ["stdout"],
                    "level": settings.log_level,
                    "propagate": False,
                },
            },
        }
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    logger.info("starting %s (%s)", settings.app_name, settings.environment)
    yield
    await dispose_engine()
    logger.info("stopped %s", settings.app_name)


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings)

    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        debug=settings.debug,
        lifespan=lifespan,
    )

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    register_exception_handlers(app)

    app.include_router(health_router, prefix=settings.api_prefix)
    # --- example feature ---
    app.include_router(item_router, prefix=settings.api_prefix)
    # --- end example feature ---

    return app


app = create_app()
