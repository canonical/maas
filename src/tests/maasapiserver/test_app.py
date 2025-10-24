# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import ssl
from unittest.mock import MagicMock

from fastapi import FastAPI
import pytest
import uvicorn

from maasapiserver.app import (
    App,
    EventListener,
    ExceptionHandler,
    MiddlewareHandler,
    ServerConfig,
)


class TestMiddlewareHandler:
    def test_getters(self):
        mock_class = MagicMock()
        handler = MiddlewareHandler(mock_class, arg1="value1")
        assert handler.get_middleware() == mock_class
        assert handler.get_kwargs() == {"arg1": "value1"}


class TestExceptionHandler:
    def test_dataclass_fields(self):
        mock_handler = MagicMock()
        handler = ExceptionHandler(ValueError, mock_handler)
        assert handler.exception_type is ValueError
        assert handler.handler == mock_handler


class TestEventListener:
    def test_dataclass_fields(self):
        mock_handler = MagicMock()
        listener = EventListener(event="startup", handler=mock_handler)
        assert listener.event == "startup"
        assert listener.handler == mock_handler


class TestServerConfig:
    def test_defaults(self):
        config = ServerConfig()
        assert config.host == "127.0.0.1"
        assert config.port == 8000
        assert config.socket_path is None
        assert config.ssl_cert_reqs == ssl.CERT_NONE
        assert config.http == "auto"


@pytest.fixture
def fake_middleware():
    class DummyMiddleware:
        pass

    return MiddlewareHandler(DummyMiddleware, option=True)


@pytest.fixture
def fake_exception_handler():
    mock_handler = MagicMock()
    return ExceptionHandler(ValueError, mock_handler)


@pytest.fixture
def fake_event_listener():
    mock_handler = MagicMock()
    return EventListener("startup", mock_handler)


@pytest.fixture
def fake_server_config():
    return ServerConfig(host="0.0.0.0", port=9000)


@pytest.fixture
def mock_fastapi(monkeypatch):
    # Mock FastAPI so to check the calls to the contructor
    mock_app = MagicMock(spec=FastAPI)
    mock_app.router = MagicMock()
    mock_fastapi_class = MagicMock(return_value=mock_app)
    monkeypatch.setattr("maasapiserver.app.FastAPI", mock_fastapi_class)
    return mock_fastapi_class, mock_app


@pytest.fixture
def mock_uvicorn(monkeypatch):
    # Mock Uvicorn Config and Server so to check the calls to the constructors
    mock_config = MagicMock(spec=uvicorn.Config)
    mock_server = MagicMock(spec=uvicorn.Server)
    mock_config_class = MagicMock(return_value=mock_config)
    mock_server_class = MagicMock(return_value=mock_server)

    monkeypatch.setattr("maasapiserver.app.uvicorn.Config", mock_config_class)
    monkeypatch.setattr("maasapiserver.app.uvicorn.Server", mock_server_class)

    return mock_config_class, mock_server_class, mock_config, mock_server


class TestApp:
    def test_prepare_app_adds_middlewares_exceptions_events(
        self,
        mock_fastapi,
        fake_middleware,
        fake_exception_handler,
        fake_event_listener,
        fake_server_config,
        mock_uvicorn,
    ):
        mock_fastapi_class, mock_app = mock_fastapi
        mock_api = MagicMock()

        App(
            app_title="My App",
            app_name="test_app",
            api=[mock_api],
            middlewares=[fake_middleware],
            exception_handlers=[fake_exception_handler],
            event_listeners=[fake_event_listener],
            server_config=fake_server_config,
        )

        # FastAPI is initialized
        mock_fastapi_class.assert_called_once()

        # API are registered
        mock_api.register.assert_called_once_with(mock_app.router)

        # Middlewares are registered
        mock_app.add_middleware.assert_called_once_with(
            fake_middleware.get_middleware(), **fake_middleware.get_kwargs()
        )
        # Exception handlers are registered
        mock_app.add_exception_handler.assert_called_once_with(
            fake_exception_handler.exception_type,
            fake_exception_handler.handler,
        )
        # Event handlers are registered
        mock_app.add_event_handler.assert_called_once_with(
            fake_event_listener.event, fake_event_listener.handler
        )

    def test_prepare_server_configuration(
        self, mock_fastapi, mock_uvicorn, fake_server_config
    ):
        _, mock_app = mock_fastapi
        mock_config_class, mock_server_class, mock_config, mock_server = (
            mock_uvicorn
        )

        App(
            app_title="My App",
            app_name="test_app",
            api=[],
            middlewares=[],
            exception_handlers=[],
            event_listeners=[],
            server_config=fake_server_config,
        )

        mock_config_class.assert_called_once_with(
            mock_app,
            loop="asyncio",
            proxy_headers=True,
            host=fake_server_config.host,
            port=fake_server_config.port,
            uds=fake_server_config.socket_path,
            ssl_keyfile=fake_server_config.ssl_keyfile,
            ssl_certfile=fake_server_config.ssl_certfile,
            ssl_ca_certs=fake_server_config.ssl_ca_certs,
            ssl_cert_reqs=fake_server_config.ssl_cert_reqs,
            log_config=None,
            http=fake_server_config.http,
        )
        mock_server_class.assert_called_once_with(mock_config)

    def test_get_app_and_get_server(
        self, mock_fastapi, mock_uvicorn, fake_server_config
    ):
        _, mock_app = mock_fastapi
        _, _, _, mock_server = mock_uvicorn

        app = App(
            app_title="TestApp",
            app_name="example",
            api=[],
            middlewares=[],
            exception_handlers=[],
            event_listeners=[],
            server_config=fake_server_config,
        )

        assert app.fastapi_app == mock_app
        assert app.server == mock_server
