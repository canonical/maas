#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Self

from maasapiserver.v3.api.public.models.responses.base import (
    BaseHal,
    HalResponse,
    PaginatedResponse,
)
from maascommon.sslkey import get_html_display_for_key
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


class SSLKeyListResponse(PaginatedResponse[SSLKeyResponse]):
    kind = "SSLKeys"


class SSLKeyWithSummaryResponse(SSLKeyResponse):
    kind = "SSLKeyWithSummary"
    display: str

    @classmethod
    def from_model(cls, sslkey: SSLKey) -> Self:
        return cls(
            id=sslkey.id,
            key=sslkey.key,
            display=get_html_display_for_key(sslkey.key),
        )


class SSLKeysWithSummaryListResponse(
    PaginatedResponse[SSLKeyWithSummaryResponse]
):
    kind = "SSLKeysWithSummary"
