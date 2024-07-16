#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

import abc

from macaroonbakery.httpbakery.agent import AuthInfo

from maasapiserver.common.auth.bakery import (
    AsyncAgentInteractor,
    HttpBakeryAsyncClient,
)
from maasapiserver.common.auth.models.exceptions import MacaroonApiException
from maasapiserver.common.auth.models.responses import UserDetailsResponse


class MacaroonAsyncClient(abc.ABC):
    """Async client to talk with a macaroon based server."""

    def __init__(self, url: str, auth_info: AuthInfo):
        self._url = url.rstrip("/")
        interactor = AsyncAgentInteractor(auth_info)
        self._client = HttpBakeryAsyncClient(interaction_methods=[interactor])

    @abc.abstractmethod
    async def get_user_details(self, username: str) -> UserDetailsResponse:
        """Return details about a user."""
        return UserDetailsResponse(username=username, fullname="", email="")

    async def _request(self, method, url, json=None, status_code=200):
        resp = await self._client.request(method=method, url=url, json=json)
        content = await resp.json()
        if resp.status != status_code:
            # Some servers return "Message" while other "message"
            raise MacaroonApiException(
                resp.status, content.get("Message") or content.get("message")
            )
        return content

    async def close(self):
        await self._client.close()
