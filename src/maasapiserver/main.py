from fastapi import FastAPI
import uvicorn

from .api.v1 import APIv1
from .settings import api_service_socket_path


def create_app() -> FastAPI:
    """Create the FastAPI application."""
    app = FastAPI(
        title="MAASAPIServer",
        name="maasapiserver",
    )
    # Register URL handlers
    APIv1.register(app.router)
    return app


def run(dsn: str | None = None):
    config = uvicorn.Config(
        create_app(),
        loop="asyncio",
        proxy_headers=True,
        uds=api_service_socket_path(),
    )
    server = uvicorn.Server(config)
    server.run()
