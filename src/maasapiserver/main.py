# Copyright 2023-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import asyncio
from functools import partial
import logging
import ssl

from django.conf import settings as django_settings
from fastapi.exceptions import RequestValidationError
import structlog

from maasapiserver.app import (
    App,
    EventListener,
    ExceptionHandler,
    MiddlewareHandler,
    ServerConfig,
)
from maasapiserver.common.api.handlers import APICommon
from maasapiserver.common.middlewares.db import (
    DatabaseMetricsMiddleware,
    TransactionMiddleware,
)
from maasapiserver.common.middlewares.exceptions import (
    ExceptionHandlers,
    ExceptionMiddleware,
)
from maasapiserver.common.middlewares.prometheus import PrometheusMiddleware
from maasapiserver.common.middlewares.response_finalizer import (
    ResponseFinalizerMiddleware,
)
from maasapiserver.settings import (
    api_service_socket_path,
    Config,
    internal_api_service_socket_path,
    read_config,
)
from maasapiserver.tls import TLSPatchedH11Protocol
from maasapiserver.v3.api.internal.handlers import APIv3Internal
from maasapiserver.v3.api.public.handlers import APIv3, APIv3UI
from maasapiserver.v3.listeners.vault import VaultMigrationPostgresListener
from maasapiserver.v3.middlewares.auth import (
    AuthenticationProvidersCache,
    LocalAuthenticationProvider,
    MacaroonAuthenticationProvider,
    OIDCAuthenticationProvider,
    V3AuthenticationMiddleware,
)
from maasapiserver.v3.middlewares.client_certificate import (
    RequireClientCertMiddleware,
)
from maasapiserver.v3.middlewares.context import ContextMiddleware
from maasapiserver.v3.middlewares.services import ServicesMiddleware
from maasservicelayer.db import Database
from maasservicelayer.db.listeners import PostgresListenersTaskFactory
from maasservicelayer.db.locks import wait_for_startup
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


def craft_public_app(
    db: Database, transaction_middleware_class: type = TransactionMiddleware
) -> App:
    cache = CacheForServices()
    return App(
        "MAASAPIServer",
        "maasapiserver",
        [APICommon, APIv3, APIv3UI],
        middlewares=[
            MiddlewareHandler(PrometheusMiddleware),
            MiddlewareHandler(DatabaseMetricsMiddleware, db=db),
            MiddlewareHandler(
                V3AuthenticationMiddleware,
                providers_cache=AuthenticationProvidersCache(
                    jwt_authentication_providers=[
                        LocalAuthenticationProvider()
                    ],
                    macaroon_authentication_provider=MacaroonAuthenticationProvider(),
                    oidc_authentication_provider=OIDCAuthenticationProvider(),
                ),
            ),
            MiddlewareHandler(ServicesMiddleware, cache=cache),
            MiddlewareHandler(transaction_middleware_class, db=db),
            MiddlewareHandler(ExceptionMiddleware),
            MiddlewareHandler(ResponseFinalizerMiddleware),
            MiddlewareHandler(ContextMiddleware),
        ],
        exception_handlers=[
            ExceptionHandler(
                RequestValidationError,
                ExceptionHandlers.validation_exception_handler,
            )
        ],
        event_listeners=[
            EventListener(
                "startup",
                partial(
                    PostgresListenersTaskFactory.create,
                    db_engine=db.engine,
                    listeners=[VaultMigrationPostgresListener()],
                ),
            ),
            EventListener("shutdown", cache.close),
        ],
        server_config=ServerConfig(
            socket_path=api_service_socket_path().as_posix()
        ),
    )


def craft_internal_app(
    db: Database, server_config: ServerConfig | None = None
) -> App:
    if server_config is None:
        # Useful for the tests
        cert, key, cacerts = get_maas_cluster_cert_paths()  # pyright: ignore [reportGeneralTypeIssues]
        server_config = ServerConfig(
            socket_path=internal_api_service_socket_path().as_posix(),
            ssl_keyfile=key,
            ssl_certfile=cert,
            ssl_ca_certs=cacerts,
            ssl_cert_reqs=ssl.CERT_OPTIONAL,
            http=TLSPatchedH11Protocol,
        )

    internal_cache = CacheForServices()
    return App(
        "MAASInternalAPIServer",
        "maasinternalapiserver",
        [APICommon, APIv3Internal],
        middlewares=[
            MiddlewareHandler(PrometheusMiddleware),
            MiddlewareHandler(DatabaseMetricsMiddleware, db=db),
            MiddlewareHandler(ServicesMiddleware, cache=internal_cache),
            MiddlewareHandler(TransactionMiddleware, db=db),
            MiddlewareHandler(RequireClientCertMiddleware),
            MiddlewareHandler(ExceptionMiddleware),
            MiddlewareHandler(ResponseFinalizerMiddleware),
            MiddlewareHandler(ContextMiddleware),
        ],
        exception_handlers=[
            ExceptionHandler(
                RequestValidationError,
                ExceptionHandlers.validation_exception_handler,
            )
        ],
        event_listeners=[EventListener("shutdown", internal_cache.close)],
        server_config=server_config,
    )


def run(app_config: Config | None = None):
    """
    Run the user and the internal server in the same event loop.
    The internal server has uvicorn configured so to enable MTLS. All the internal endpoints are not authenticated at API level
    because they rely on the fact that uvicorn is providing security on top. For this reason, DO NOT include the v3Internal
    router in the user app!
    """

    if not django_settings.configured:
        django_settings.configure()

    loop = asyncio.new_event_loop()

    if app_config is None:
        app_config = loop.run_until_complete(read_config())

    configure_logging(
        level=logging.DEBUG if app_config.debug else logging.INFO,
        query_level=(
            logging.DEBUG if app_config.debug_queries else logging.WARNING
        ),
    )
    config_uvicorn_logging(
        logging.DEBUG if app_config.debug_http else logging.INFO
    )

    db = Database(app_config.db, echo=app_config.debug_queries)
    # In maasserver we have a startup lock. If it is set, we have to wait to start maasapiserver as well.
    loop.run_until_complete(wait_for_startup(db))

    public_app = craft_public_app(db)
    internal_app = craft_internal_app(db)

    async def run_servers():
        return await asyncio.gather(
            public_app.server.serve(), internal_app.server.serve()
        )

    loop.run_until_complete(run_servers())
