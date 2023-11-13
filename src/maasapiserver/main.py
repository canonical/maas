from fastapi import FastAPI
import uvicorn

from .common.api.db import DatabaseMetricsMiddleware, TransactionMiddleware
from .common.db import Database
from .prometheus import metrics, PrometheusMiddleware
from .settings import api_service_socket_path, read_db_config
from .v2.api.handlers import APIv2
from .v3.api.handlers import APIv3


def create_app(
    db: Database | None = None,
    transaction_middleware_class: type = TransactionMiddleware,
) -> FastAPI:
    """Create the FastAPI application."""
    if db is None:
        config = read_db_config()
        db = Database(config.db, echo=config.debug_queries)

    app = FastAPI(
        title="MAASAPIServer",
        name="maasapiserver",
    )
    app.add_middleware(PrometheusMiddleware)
    app.add_middleware(DatabaseMetricsMiddleware, db=db)
    app.add_middleware(transaction_middleware_class, db=db)

    # Register URL handlers
    app.router.add_api_route("/metrics", metrics, methods=["GET"])
    APIv2.register(app.router)
    APIv3.register(app.router)
    return app


def run(db: Database | None = None):
    config = uvicorn.Config(
        create_app(db=db),
        loop="asyncio",
        proxy_headers=True,
        uds=api_service_socket_path(),
    )
    server = uvicorn.Server(config)
    server.run()
