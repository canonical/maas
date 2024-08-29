#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from pydantic import BaseModel

from maasapiserver.common.api.base import Handler, handler


class RootGetResponse(BaseModel):
    """Root handler response."""


class RootHandler(Handler):
    """Root API handler."""

    @handler(
        path="/",
        methods=["GET"],
        include_in_schema=False,
    )
    async def get(self) -> RootGetResponse:
        return RootGetResponse()
