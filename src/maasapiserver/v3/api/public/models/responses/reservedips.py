#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Optional, Self

from pydantic import IPvAnyAddress

from maasapiserver.v3.api.public.models.responses.base import (
    BaseHal,
    BaseHref,
    HalResponse,
    TokenPaginatedResponse,
)
from maasservicelayer.models.fields import MacAddress
from maasservicelayer.models.reservedips import ReservedIP


class ReservedIPResponse(HalResponse[BaseHal]):
    kind = "ReservedIP"
    id: int
    ip: IPvAnyAddress
    mac_address: MacAddress
    comment: Optional[str]

    @classmethod
    def from_model(
        cls, reservedip: ReservedIP, self_base_hyperlink: str
    ) -> Self:
        return cls(
            id=reservedip.id,
            ip=reservedip.ip,
            mac_address=reservedip.mac_address,
            comment=reservedip.comment,
            hal_links=BaseHal(
                self=BaseHref(
                    href=f"{self_base_hyperlink.rstrip('/')}/{reservedip.id}"
                )
            ),
        )


class ReservedIPsListResponse(TokenPaginatedResponse[ReservedIPResponse]):
    kind = "ReservedIPsList"
