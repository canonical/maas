#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Optional

from maasapiserver.v3.api.models.responses.base import (
    BaseHal,
    BaseHref,
    HalResponse,
    TokenPaginatedResponse,
)


class SpaceResponse(HalResponse[BaseHal]):
    kind = "Space"
    id: int
    name: Optional[str]
    description: Optional[str]
    vlans: BaseHref
    subnets: BaseHref


class SpacesListResponse(TokenPaginatedResponse[SpaceResponse]):
    kind = "SpacesList"
