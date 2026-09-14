# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import asyncio
from dataclasses import dataclass
import ssl
from typing import Any, Callable, Type

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from fastapi.responses import HTMLResponse
import uvicorn
from uvicorn.config import HTTPProtocolType

from maasapiserver.common.api.base import API
from maasapiserver.common.constants import API_PREFIX


class MiddlewareHandler:
    def __init__(self, middleware_class: type[Any], **kwargs: Any) -> None:
        self.middleware_class = middleware_class
        self.kwargs = kwargs

    def get_middleware(self) -> type[Any]:
        return self.middleware_class

    def get_kwargs(self) -> dict[str, Any]:
        return self.kwargs


@dataclass
class ExceptionHandler:
    exception_type: Type[Exception]
    handler: Callable[..., Any]


@dataclass
class EventListener:
    event: str
    handler: Callable[..., Any]


@dataclass
class ServerConfig:
    host: str = "127.0.0.1"
    port: int = 8000
    socket_path: str | None = None
    ssl_keyfile: str | None = None
    ssl_certfile: str | None = None
    ssl_ca_certs: str | None = None
    ssl_cert_reqs: int = ssl.CERT_NONE
    http: type[asyncio.Protocol] | HTTPProtocolType = "auto"


def custom_openapi(app: FastAPI):
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title="MAAS API v3",
        version="0.1.0",
        openapi_version="3.0.3",
        summary="Beta version of the MAAS API v3",
        routes=app.routes,
    )
    app.openapi_schema = openapi_schema
    return app.openapi_schema


# Swagger UI assets served locally from the snap
# (see snap/snapcraft.yaml for build details). Serving them from the
# same origin is required by the strict FIPS/hardening CSP
# (script-src / style-src / font-src 'self').
_SWAGGER_UI_CSS_URL = "/MAAS/swagger-ui/swagger-ui.css"
_SWAGGER_UI_JS_URL = "/MAAS/swagger-ui/swagger-ui-bundle.js"
_SWAGGER_UI_INIT_URL = "/MAAS/swagger-ui/swagger-ui-init.js"
# Reuse the MAAS UI favicon which is already served locally via the
# /MAAS/r/ static location. This avoids the default fastapi.tiangolo.com
# favicon fetch.
_SWAGGER_UI_FAVICON_URL = "/MAAS/r/maas-favicon-32px.png"


def _render_swagger_ui_html(*, title: str, openapi_url: str) -> str:
    """Render the Swagger UI HTML without any inline scripts.

    FastAPI's built-in ``get_swagger_ui_html`` emits an inline ``<script>``
    block to bootstrap Swagger UI, which is incompatible with a strict CSP
    (``script-src 'self'``). This helper produces the same page but sources
    the bootstrap from an external file, ``swagger-ui-init.js``, which is
    also served locally.

    The OpenAPI URL is passed to the bootstrap via a ``data-openapi-url``
    attribute on the ``<script>`` tag, so no inline JS is needed to
    configure it.
    """
    return f"""\
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{title}</title>
    <link rel="icon" type="image/png" href="{_SWAGGER_UI_FAVICON_URL}">
    <link rel="stylesheet" type="text/css" href="{_SWAGGER_UI_CSS_URL}">
  </head>
  <body>
    <div id="swagger-ui"></div>
    <script src="{_SWAGGER_UI_JS_URL}"></script>
    <script src="{_SWAGGER_UI_INIT_URL}" data-openapi-url="{openapi_url}"></script>
  </body>
</html>
"""


class App:
    def __init__(
        self,
        app_title: str,
        app_name: str,
        api: list[API],
        # Order is important: the last in the list is the first processing the request.
        middlewares: list[MiddlewareHandler],
        exception_handlers: list[ExceptionHandler],
        event_listeners: list[EventListener],
        server_config: ServerConfig,
    ):
        self._app_title = app_title
        self._name = app_name
        self._api = api
        self._middlewares = middlewares
        self._exception_handlers = exception_handlers
        self._event_listeners = event_listeners
        self._server_config = server_config
        self._app = self._prepare_app()
        self._server = self._prepare_server()

    def _prepare_app(self):
        app = FastAPI(
            title=self._app_title,
            name=self._name,
            # Disable FastAPI's built-in Swagger UI page: it emits an
            # inline <script> and pulls assets from the fastapi.tiangolo.com
            # CDN, both of which violate the hardened CSP. We register a
            # CSP-safe replacement below.
            docs_url=None,
            openapi_url=f"{API_PREFIX}/openapi.json",
        )
        app.openapi = lambda: custom_openapi(app)

        @app.get(f"{API_PREFIX}/docs", include_in_schema=False)
        async def swagger_ui_html() -> HTMLResponse:
            return HTMLResponse(
                _render_swagger_ui_html(
                    title="MAAS API V3 - Swagger UI",
                    openapi_url=f"{API_PREFIX}/openapi.json",
                )
            )

        for api in self._api:
            api.register(app.router)

        for middleware in self._middlewares:
            app.add_middleware(  # pyright: ignore [reportCallIssue]
                middleware.get_middleware(), **middleware.get_kwargs()
            )

        for exception_handler in self._exception_handlers:
            app.add_exception_handler(
                exception_handler.exception_type, exception_handler.handler
            )

        for event_listener in self._event_listeners:
            app.add_event_handler(event_listener.event, event_listener.handler)

        return app

    def _prepare_server(self) -> uvicorn.Server:
        server_config = uvicorn.Config(
            self._app,
            loop="asyncio",
            proxy_headers=True,
            host=self._server_config.host,
            port=self._server_config.port,
            uds=self._server_config.socket_path,
            ssl_keyfile=self._server_config.ssl_keyfile,
            ssl_certfile=self._server_config.ssl_certfile,
            ssl_ca_certs=self._server_config.ssl_ca_certs,
            ssl_cert_reqs=self._server_config.ssl_cert_reqs,
            # We configure the logging OUTSIDE the library in order to use our custom json formatter.
            log_config=None,
            http=self._server_config.http,
        )
        return uvicorn.Server(server_config)

    @property
    def fastapi_app(self) -> FastAPI:
        return self._app

    @property
    def server(self) -> uvicorn.Server:
        return self._server
