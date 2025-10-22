# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from base64 import b64encode
import json
from typing import Self

from pydantic import BaseModel

from maasapiserver.v3.api.public.models.responses.base import (
    BaseHal,
    BaseHref,
    HalResponse,
    PaginatedResponse,
)
from maasservicelayer.models.racks import Rack


class RackResponse(HalResponse[BaseHal]):
    kind = "Rack"
    id: int
    name: str

    @classmethod
    def from_model(cls, rack: Rack, self_base_hyperlink: str) -> Self:
        return cls(
            id=rack.id,
            name=rack.name,
            hal_links=BaseHal(  # pyright: ignore [reportCallIssue]
                self=BaseHref(
                    href=f"{self_base_hyperlink.rstrip('/')}/{rack.id}"
                )
            ),
        )


class RackListResponse(PaginatedResponse[RackResponse]):
    kind = "RackList"


class RackBootstrapTokenResponse(BaseModel):
    kind = "RackBootstrapToken"
    token: str

    @classmethod
    def from_model(cls, token) -> Self:
        token_b64_bytes = b64encode(json.dumps(token).encode("utf-8"))
        token_b64_str = token_b64_bytes.decode("utf-8")
        return cls(token=token_b64_str)
