#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Optional, Self

from pydantic import IPvAnyAddress

from maasapiserver.v3.api.public.models.responses.base import (
    BaseHal,
    BaseHref,
    HalResponse,
    PaginatedResponse,
)
from maascommon.enums.ipranges import IPRangeType
from maasservicelayer.models.ipranges import IPRange


class IPRangeResponse(HalResponse[BaseHal]):
    kind = "IPRange"
    id: int
    type: IPRangeType
    start_ip: IPvAnyAddress
    end_ip: IPvAnyAddress
    comment: Optional[str]
    owner_id: int

    @classmethod
    def from_model(cls, iprange: IPRange, self_base_hyperlink: str) -> Self:
        return cls(
            id=iprange.id,
            type=iprange.type,
            start_ip=iprange.start_ip,
            end_ip=iprange.end_ip,
            comment=iprange.comment,
            owner_id=iprange.user_id,
            hal_links=BaseHal(  # pyright: ignore [reportCallIssue]
                self=BaseHref(
                    href=f"{self_base_hyperlink.rstrip('/')}/{iprange.id}"
                )
            ),
        )


class IPRangeListResponse(PaginatedResponse[IPRangeResponse]):
    kind = "IPRangesList"
