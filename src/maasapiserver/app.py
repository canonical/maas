# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import asyncio
from dataclasses import dataclass
import ssl
from typing import Callable, Type

from fastapi import FastAPI
import uvicorn
from uvicorn.config import HTTPProtocolType

from maasapiserver.common.api.base import API
from maasapiserver.common.constants import API_PREFIX


class MiddlewareHandler:
    def __init__(self, middleware_class, **kwargs):
        self.middleware_class = middleware_class
        self.kwargs = kwargs

    def get_middleware(self):
        return self.middleware_class

    def get_kwargs(self):
        return self.kwargs


@dataclass
class ExceptionHandler:
    exception_type: Type[Exception]
    handler: Callable


@dataclass
class EventListener:
    event: str
    handler: Callable


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
            openapi_url=f"{API_PREFIX}/openapi.json",
            # The SwaggerUI page is provided by the APICommon router.
            docs_url=None,
        )

        for api in self._api:
            api.register(app.router)

        for middleware in self._middlewares:
            app.add_middleware(
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
