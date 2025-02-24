from fastapi import APIRouter

from maasapiserver.common.api.models.responses.errors import (
    ValidationErrorBodyResponse,
)


class Handler:
    """An API handler for an entity."""

    def get_handlers(self):
        """Get the alphebetised list of all handler functions in the class.

        Subclasses may override this to define their own, non-alphabetised
        handler registration order.
        """
        return dir(self)

    def register(self, router: APIRouter):
        for name in self.get_handlers():
            if name.startswith("_"):
                continue

            attr = getattr(self, name)
            if config := getattr(attr, "__handler_config", None):
                router.add_api_route(endpoint=attr, **config)


def handler(**config):
    """Decorator for API handlers inside a Handler class."""

    def register_handler(func):
        # Use the name of the python function as operationId in the openapi spec.
        config["operation_id"] = func.__name__
        if "responses" in config:
            # if 422 is not registered, FastAPI would automatically add HTTPValidationError. So let's set our error definition
            # by default.
            config["responses"].update(
                {422: {"model": ValidationErrorBodyResponse}}
            )
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
