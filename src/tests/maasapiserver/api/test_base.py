from fastapi import FastAPI

from maasapiserver.api.base import API, Handler, handler


class TestAPI:
    async def test_register_handlers(self) -> None:
        class Handler1(Handler):
            @handler(path="/handler1", methods=["GET"])
            def get(self) -> None:
                return None

            @handler(path="/handler1/foo", methods=["GET", "DELETE"])
            def foo(self) -> None:
                return None

        class Handler2(Handler):
            @handler(path="/handler2/bar", methods=["GET"])
            def bar(self) -> None:
                return None

            @handler(path="/handler2/baz", methods=["GET", "POST"])
            def baz(self) -> None:
                return None

        api = API(prefix="/v1", handlers=[Handler1(), Handler2()])
        app = FastAPI()
        api.register(app.router)
        routes = [(route.path, route.methods) for route in app.router.routes]
        assert ("/v1/handler1", {"GET"}) in routes
        assert ("/v1/handler1/foo", {"GET", "DELETE"}) in routes
        assert ("/v1/handler2/bar", {"GET"}) in routes
        assert ("/v1/handler2/baz", {"GET", "POST"}) in routes
