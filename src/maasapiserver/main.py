import logging
import re

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.utils import get_openapi
import uvicorn

from maasapiserver.common.api.handlers import APICommon
from maasapiserver.common.db import Database
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
from maasapiserver.v3.middlewares.auth import (
    AuthenticationProvidersCache,
    LocalAuthenticationProvider,
    V3AuthenticationMiddleware,
)
from maasapiserver.v3.middlewares.services import ServicesMiddleware


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

    def custom_openapi():
        """
        The maasapiserver is always running behing a nginx proxy that is rewriting the requests paths.
        For this reason, we have to patch the openapi schema in the same way.
        """
        openapi_schema = get_openapi(
            title="MAAS API V3",
            version="0.0.1",
            routes=app.routes,
        )

        # Replace ^/api/ with /MAAS/a/ exactly like in src/maasserver/templates/http/regiond.nginx.conf.template.
        # TODO: https://warthogs.atlassian.net/browse/MAASENG-3221 add an integration test for this
        patched_paths = {
            re.sub(r"^/api/", "/MAAS/a/", key): value
            for key, value in openapi_schema["paths"].items()
        }
        openapi_schema["paths"] = patched_paths
        app.openapi_schema = openapi_schema
        return app.openapi_schema

    app.openapi = custom_openapi

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
