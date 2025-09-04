# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Self

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
