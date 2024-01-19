from pydantic import BaseModel

from maasapiserver.common.api.base import Handler, handler


class RootGetResponse(BaseModel):
    """Root handler response."""


class RootHandler(Handler):
    """Root API handler."""

    @handler(path="/", methods=["GET"], include_in_schema=False)
    async def get(self) -> RootGetResponse:
        return RootGetResponse()
