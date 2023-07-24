from pydantic import BaseModel

from ..base import Handler, handler


class RootGetResponse(BaseModel):
    """Root handler response."""


class RootHandler(Handler):
    """Root API handler."""

    @handler(path="/", methods=["GET"])
    async def get(self) -> RootGetResponse:
        return RootGetResponse()
