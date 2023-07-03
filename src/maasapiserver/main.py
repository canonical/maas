from fastapi import FastAPI
import uvicorn

from .settings import api_service_socket_path


def create_app() -> FastAPI:
    """Create the FastAPI application."""
    return FastAPI(
        title="MAASAPIServer",
        name="maasapiserver",
    )


def run(dsn: str | None = None):
    config = uvicorn.Config(
        create_app(),
        loop="asyncio",
        proxy_headers=True,
        uds=api_service_socket_path(),
    )
    server = uvicorn.Server(config)
    server.run()
