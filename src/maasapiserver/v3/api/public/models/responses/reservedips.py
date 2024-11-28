#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from pydantic import IPvAnyAddress

from maasapiserver.v3.api.public.models.responses.base import (
    BaseHal,
    BaseHref,
    HalResponse,
    TokenPaginatedResponse,
)
from maasservicelayer.models.reservedips import ReservedIP


class ReservedIPResponse(HalResponse[BaseHal]):
    kind = "ReservedIP"
    id: int
    subnet_id: int
    ip: IPvAnyAddress
    mac_address: str
    comment: str

    @classmethod
    def from_model(cls, reservedip: ReservedIP, self_base_hyperlink: str):
        return cls(
            id=reservedip.id,
            subnet_id=reservedip.subnet_id,
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
