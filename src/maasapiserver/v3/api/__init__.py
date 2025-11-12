#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from starlette.requests import Request
from starlette.responses import Response

from maasapiserver.v3.auth.cookie_manager import EncryptedCookieManager
from maasservicelayer.services import ServiceCollectionV3


def services(
    request: Request,
) -> ServiceCollectionV3:
    """Dependency to return the services collection."""
    return request.state.services


async def cookie_manager(
    request: Request, response: Response
) -> EncryptedCookieManager:
    """Dependency to return the cookie manager."""
    encryptor = await request.state.services.external_oauth.get_encryptor()
    return EncryptedCookieManager(request, response, encryptor)
