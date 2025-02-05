# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Optional, Self

from maasapiserver.v3.api.public.models.responses.base import (
    BaseHal,
    BaseHref,
    HalResponse,
    PaginatedResponse,
)
from maasservicelayer.models.domains import Domain


class DomainResponse(HalResponse[BaseHal]):
    kind = "Domain"
    authoritative: bool
    ttl: Optional[int]
    id: int
    name: str
    # TODO: add is_default

    @classmethod
    def from_model(cls, domain: Domain, self_base_hyperlink: str) -> Self:
        return cls(
            authoritative=domain.authoritative,
            ttl=domain.ttl,
            id=domain.id,
            name=domain.name,
            hal_links=BaseHal(
                self=BaseHref(
                    href=f"{self_base_hyperlink.rstrip('/')}/{domain.id}"
                )
            ),
        )


class DomainsListResponse(PaginatedResponse[DomainResponse]):
    kind = "DomainsList"
