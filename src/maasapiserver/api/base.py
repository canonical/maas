from fastapi import APIRouter


class Handler:
    """An API handler for an entity."""

    def register(self, router: APIRouter):
        for name in dir(self):
            if name.startswith("_"):
                continue

            attr = getattr(self, name)
            if config := getattr(attr, "__handler_config", None):
                router.add_api_route(endpoint=attr, **config)


def handler(**config):
    """Decorator for API handlers inside a Handler class."""

    def register_handler(func):
        func.__handler_config = config
        return func

    return register_handler


class API:
    """API definition."""

    def __init__(self, prefix: str, handlers: list[Handler]):
        self.prefix = prefix
        self.handlers = handlers

    def register(self, router: APIRouter):
        """Register the API with the router."""
        api_router = APIRouter()
        for handler in self.handlers:
            handler.register(api_router)
        router.include_router(router=api_router, prefix=self.prefix)
