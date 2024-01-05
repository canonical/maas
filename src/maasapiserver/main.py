import logging

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
import uvicorn

from .common.db import Database
from .common.middlewares.db import (
    DatabaseMetricsMiddleware,
    TransactionMiddleware,
)
from .common.middlewares.exceptions import (
    ExceptionHandlers,
    ExceptionMiddleware,
)
from .common.middlewares.prometheus import metrics, PrometheusMiddleware
from .settings import api_service_socket_path, Config, read_config
from .v2.api.handlers import APIv2
from .v3.api.handlers import APIv3


def create_app(
    config: Config,
    transaction_middleware_class: type = TransactionMiddleware,
    # In the tests the database is created in the fixture, so we need to inject it here as a parameter.
    db: Database = None,
) -> FastAPI:
    """Create the FastAPI application."""

    if db is None:
        db = Database(config.db, echo=config.debug_queries)

    app = FastAPI(
        title="MAASAPIServer",
        name="maasapiserver",
    )

    # The order here is important: the exception middleware must be the first one being executed (i.e. it must be the last
    # middleware added here)
    app.add_middleware(PrometheusMiddleware)
    app.add_middleware(DatabaseMetricsMiddleware, db=db)
    app.add_middleware(transaction_middleware_class, db=db)
    app.add_middleware(ExceptionMiddleware)

    # Add exception handlers for exceptions that can be thrown outside the middlewares.
    app.add_exception_handler(
        RequestValidationError, ExceptionHandlers.validation_exception_handler
    )

    # Register URL handlers
    app.router.add_api_route("/metrics", metrics, methods=["GET"])
    APIv2.register(app.router)
    APIv3.register(app.router)
    return app


def run(app_config: Config | None = None):
    if app_config is None:
        app_config = read_config()

    logging.basicConfig(
        level=logging.DEBUG if app_config.debug else logging.INFO
    )

    server_config = uvicorn.Config(
        create_app(config=app_config),
        loop="asyncio",
        proxy_headers=True,
        uds=api_service_socket_path(),
    )
    server = uvicorn.Server(server_config)
    server.run()
