#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Optional

from maasapiserver.v3.api.models.responses.base import (
    BaseHal,
    BaseHref,
    HalResponse,
    TokenPaginatedResponse,
)


class FabricResponse(HalResponse[BaseHal]):
    kind = "Fabric"
    id: int
    name: Optional[str]
    description: Optional[str]
    class_type: Optional[str]
    vlans: BaseHref


class FabricsListResponse(TokenPaginatedResponse[FabricResponse]):
    kind = "FabricsList"
