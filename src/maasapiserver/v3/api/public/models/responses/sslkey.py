#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Self

from maasapiserver.v3.api.public.models.responses.base import (
    BaseHal,
    HalResponse,
    TokenPaginatedResponse,
)
from maasservicelayer.models.sslkeys import SSLKey


class SSLKeyResponse(HalResponse[BaseHal]):
    kind = "SSLKey"
    id: int
    key: str

    @classmethod
    def from_model(cls, sslkey: SSLKey) -> Self:
        return cls(
            id=sslkey.id,
            key=sslkey.key,
        )


class SSLKeyListResponse(TokenPaginatedResponse[SSLKeyResponse]):
    kind = "SSLKeys"
