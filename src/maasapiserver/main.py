# Copyright 2023-2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import asyncio
from functools import partial
import logging
import ssl

from django.conf import settings as django_settings
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
import structlog
import uvicorn

from maasapiserver.common.api.handlers import APICommon
from maasapiserver.common.constants import API_PREFIX
from maasapiserver.common.middlewares.db import (
    DatabaseMetricsMiddleware,
    TransactionMiddleware,
)
from maasapiserver.common.middlewares.exceptions import (
    ExceptionHandlers,
    ExceptionMiddleware,
)
from maasapiserver.common.middlewares.prometheus import PrometheusMiddleware
from maasapiserver.settings import (
    api_service_socket_path,
    Config,
    internal_api_service_socket_path,
    read_config,
)
from maasapiserver.v2.api.handlers import APIv2
from maasapiserver.v3.api.internal.handlers import APIv3Internal
from maasapiserver.v3.api.public.handlers import APIv3
from maasapiserver.v3.listeners.vault import VaultMigrationPostgresListener
from maasapiserver.v3.middlewares.auth import (
    AuthenticationProvidersCache,
    DjangoSessionAuthenticationProvider,
    LocalAuthenticationProvider,
    MacaroonAuthenticationProvider,
    V3AuthenticationMiddleware,
)
from maasapiserver.v3.middlewares.context import ContextMiddleware
from maasapiserver.v3.middlewares.services import ServicesMiddleware
from maasserver.workflow.worker import (
    get_client_async as get_temporal_client_async,
)
from maasservicelayer.db import Database
from maasservicelayer.db.listeners import PostgresListenersTaskFactory
from maasservicelayer.db.locks import StartupLock
from maasservicelayer.logging.configure import configure_logging
from maasservicelayer.services import CacheForServices
from provisioningserver.certificates import get_maas_cluster_cert_paths

logger = structlog.getLogger()


def config_uvicorn_logging(level=logging.INFO) -> None:
    logging.getLogger("uvicorn.error").setLevel(level)
    logging.getLogger("uvicorn.asgi").setLevel(level)
    # We have already a middleware to log this info: let's log only ERROR unless debug is enabled.
    logging.getLogger("uvicorn.access").setLevel(
        logging.ERROR if level == logging.INFO else level
    )


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


async def prepare_app(
    config: Config,
    transaction_middleware_class: type = TransactionMiddleware,
    # In the tests the database is created in the fixture, so we need to inject it here as a parameter.
    db: Database = None,
    add_authentication_middleware: bool = True,
    app_title: str = "APIServer",
    app_name: str = "apiserver",
) -> FastAPI:
    """Create the FastAPI application."""

    if not django_settings.configured:
        django_settings.configure()

    if db is None:
        db = Database(config.db, echo=config.debug_queries)

    # In maasserver we have a startup lock. If it is set, we have to wait to start maasapiserver as well.
    await wait_for_startup(db)

    temporal = await get_temporal_client_async()
    services_cache = CacheForServices()

    app = FastAPI(
        title=app_title,
        name=app_name,
        openapi_url=f"{API_PREFIX}/openapi.json",
        # The SwaggerUI page is provided by the APICommon router.
        docs_url=None,
    )

    # The order here is important: the exception middleware must be the first one being executed (i.e. it must be the last
    # middleware added here)
    app.add_middleware(PrometheusMiddleware)
    app.add_middleware(DatabaseMetricsMiddleware, db=db)

    if add_authentication_middleware:
        app.add_middleware(
            V3AuthenticationMiddleware,
            providers_cache=AuthenticationProvidersCache(
                jwt_authentication_providers=[LocalAuthenticationProvider()],
                session_authentication_provider=DjangoSessionAuthenticationProvider(),
                macaroon_authentication_provider=MacaroonAuthenticationProvider(),
            ),
        )

    app.add_middleware(
        ServicesMiddleware, temporal=temporal, cache=services_cache
    )
    app.add_middleware(transaction_middleware_class, db=db)
    app.add_middleware(ExceptionMiddleware)
    app.add_middleware(ContextMiddleware)

    # Add exception handlers for exceptions that can be thrown outside the middlewares.
    app.add_exception_handler(
        RequestValidationError, ExceptionHandlers.validation_exception_handler
    )

    APICommon.register(app.router)

    # Event handlers
    app.add_event_handler(
        "startup",
        partial(
            PostgresListenersTaskFactory.create,
            db_engine=db.engine,
            listeners=[VaultMigrationPostgresListener()],
        ),
    )
    app.add_event_handler("shutdown", services_cache.close)

    return app


async def create_app(
    config: Config,
    transaction_middleware_class: type = TransactionMiddleware,
    # In the tests the database is created in the fixture, so we need to inject it here as a parameter.
    db: Database = None,
) -> FastAPI:

    app = await prepare_app(
        config,
        transaction_middleware_class,
        db,
        True,
        "MAASAPIServer",
        "maasapiserver",
    )
    APIv2.register(app.router)
    APIv3.register(app.router)
    return app


async def create_internal_app(
    config: Config,
    transaction_middleware_class: type = TransactionMiddleware,
    # In the tests the database is created in the fixture, so we need to inject it here as a parameter.
    db: Database = None,
) -> FastAPI:
    # DO NOT add the authentication middleware. We enable MTLS at uvicorn level.
    app = await prepare_app(
        config,
        transaction_middleware_class,
        db,
        False,
        "MAASInternalAPIServer",
        "maasinternalapiserver",
    )
    APIv3Internal.register(app.router)
    return app


def run(app_config: Config | None = None, start_internal_server: bool = True):
    """
    Run the user and the internal server in the same event loop.
    The internal server has uvicorn configured so to enable MTLS. All the internal endpoints are not authenticated at API level
    because they rely on the fact that uvicorn is providing security on top. For this reason, DO NOT include the v3Internal
    router in the user app!
    """
    loop = asyncio.new_event_loop()

    if app_config is None:
        app_config = loop.run_until_complete(read_config())

    servers_tasks = []

    configure_logging(
        level=logging.DEBUG if app_config.debug else logging.INFO,
        query_level=(
            logging.DEBUG if app_config.debug_queries else logging.WARNING
        ),
    )
    config_uvicorn_logging(
        logging.DEBUG if app_config.debug_http else logging.INFO
    )

    # User app
    user_app = loop.run_until_complete(create_app(config=app_config))
    user_server_config = uvicorn.Config(
        user_app,
        loop=loop,
        proxy_headers=True,
        uds=api_service_socket_path(),
        # We configure the logging OUTSIDE the library in order to use our custom json formatter.
        log_config=None,
    )
    user_server = uvicorn.Server(user_server_config)
    servers_tasks.append(user_server.serve())

    # Internal app
    internal_app = loop.run_until_complete(
        create_internal_app(config=app_config)
    )

    cert, key, cacerts = get_maas_cluster_cert_paths()
    internal_server_config = uvicorn.Config(
        internal_app,
        loop=loop,
        proxy_headers=True,
        uds=internal_api_service_socket_path(),
        ssl_keyfile=key,
        ssl_certfile=cert,
        ssl_ca_certs=cacerts,
        ssl_cert_reqs=ssl.CERT_REQUIRED,
        # We configure the logging OUTSIDE the library in order to use our custom json formatter.
        log_config=None,
    )
    internal_server = uvicorn.Server(internal_server_config)

    async def run_servers():
        return await asyncio.gather(
            user_server.serve(), internal_server.serve()
        )

    loop.run_until_complete(run_servers())
