import asyncio
from functools import partial
import logging

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
import uvicorn

from maasapiserver.common.api.handlers import APICommon
from maasapiserver.common.constants import API_PREFIX
from maasapiserver.common.db import Database
from maasapiserver.common.listeners.postgres import (
    PostgresListenersTaskFactory,
)
from maasapiserver.common.locks.db import StartupLock
from maasapiserver.common.middlewares.db import (
    DatabaseMetricsMiddleware,
    TransactionMiddleware,
)
from maasapiserver.common.middlewares.exceptions import (
    ExceptionHandlers,
    ExceptionMiddleware,
)
from maasapiserver.common.middlewares.prometheus import PrometheusMiddleware
from maasapiserver.settings import api_service_socket_path, Config, read_config
from maasapiserver.v2.api.handlers import APIv2
from maasapiserver.v3.api.handlers import APIv3
from maasapiserver.v3.listeners.vault import VaultMigrationPostgresListener
from maasapiserver.v3.middlewares.auth import (
    AuthenticationProvidersCache,
    LocalAuthenticationProvider,
    V3AuthenticationMiddleware,
)
from maasapiserver.v3.middlewares.services import ServicesMiddleware

logger = logging.getLogger(__name__)


async def wait_for_startup(db: Database):
    """
    Wait until the startup lock has been removed and we can start the application.
    """
    async with db.engine.connect() as conn:
        async with conn.begin():
            startup_lock = StartupLock(conn)
            while await startup_lock.is_locked():
                logger.info("Startup lock found. Retrying in 5 seconds")
                await asyncio.sleep(5)


async def create_app(
    config: Config,
    transaction_middleware_class: type = TransactionMiddleware,
    # In the tests the database is created in the fixture, so we need to inject it here as a parameter.
    db: Database = None,
) -> FastAPI:
    """Create the FastAPI application."""

    if db is None:
        db = Database(config.db, echo=config.debug_queries)

    # In maasserver we have a startup lock. If it is set, we have to wait to start maasapiserver as well.
    await wait_for_startup(db)

    app = FastAPI(
        title="MAASAPIServer",
        name="maasapiserver",
        openapi_url=f"{API_PREFIX}/openapi.json",
        # The SwaggerUI page is provided by the APICommon router.
        docs_url=None,
    )

    # The order here is important: the exception middleware must be the first one being executed (i.e. it must be the last
    # middleware added here)
    app.add_middleware(PrometheusMiddleware)
    app.add_middleware(DatabaseMetricsMiddleware, db=db)

    app.add_middleware(
        V3AuthenticationMiddleware,
        providers_cache=AuthenticationProvidersCache(
            [LocalAuthenticationProvider()]
        ),
    )

    app.add_middleware(ServicesMiddleware)
    app.add_middleware(transaction_middleware_class, db=db)
    app.add_middleware(ExceptionMiddleware)

    # Add exception handlers for exceptions that can be thrown outside the middlewares.
    app.add_exception_handler(
        RequestValidationError, ExceptionHandlers.validation_exception_handler
    )

    APICommon.register(app.router)
    APIv2.register(app.router)
    APIv3.register(app.router)

    # Event handlers
    app.add_event_handler(
        "startup",
        partial(
            PostgresListenersTaskFactory.create,
            db_engine=db.engine,
            listeners=[VaultMigrationPostgresListener()],
        ),
    )

    return app


def run(app_config: Config | None = None):
    loop = asyncio.new_event_loop()

    if app_config is None:
        app_config = loop.run_until_complete(read_config())

    logging.basicConfig(
        level=logging.DEBUG if app_config.debug else logging.INFO
    )

    app = loop.run_until_complete(create_app(config=app_config))

    server_config = uvicorn.Config(
        app,
        loop=loop,
        proxy_headers=True,
        uds=api_service_socket_path(),
    )
    server = uvicorn.Server(server_config)
    loop.run_until_complete(server.serve())
