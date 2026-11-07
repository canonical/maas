#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime
from typing import Self

from pydantic import Field

from maasapiserver.v3.api.public.models.responses.base import (
    BaseHal,
    BaseHref,
    HalResponse,
    PaginatedResponse,
)
from maasservicelayer.models.tokens import ApiToken


class ApiTokenResponse(HalResponse[BaseHal]):
    kind: str = Field(default="ApiToken")
    id: int
    name: str
    public_id: str
    user_id: int
    created: datetime
    expires_at: datetime
    last_used_at: datetime | None = None
    revoked_at: datetime | None = None

    @classmethod
    def from_model(
        cls, api_token: ApiToken, self_base_hyperlink: str, **extra: str
    ) -> Self:
        return cls(
            id=api_token.id,
            name=api_token.name,
            public_id=api_token.public_id,
            user_id=api_token.user_id,
            created=api_token.created,
            expires_at=api_token.expires_at,
            last_used_at=api_token.last_used_at,
            revoked_at=api_token.revoked_at,
            hal_links=BaseHal(  # pyright: ignore [reportCallIssue]
                self=BaseHref(
                    href=f"{self_base_hyperlink.rstrip('/')}/{api_token.id}"
                )
            ),
            **extra,
        )


class ApiTokenCreatedResponse(ApiTokenResponse):
    kind: str = Field(default="ApiTokenCreated")
    token: str = Field(
        description="The raw token. It is only shown once, at creation."
    )


class ApiTokensListResponse(PaginatedResponse[ApiTokenResponse]):
    kind: str = Field(default="ApiTokensList")
