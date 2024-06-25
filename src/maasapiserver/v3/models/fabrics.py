# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Optional

from maasapiserver.v3.api.models.responses.base import BaseHal, BaseHref
from maasapiserver.v3.api.models.responses.fabrics import FabricResponse
from maasapiserver.v3.constants import V3_API_PREFIX
from maasapiserver.v3.models.base import MaasTimestampedBaseModel


class Fabric(MaasTimestampedBaseModel):
    name: Optional[str]
    description: Optional[str]
    class_type: Optional[str]

    def to_response(self, self_base_hyperlink: str) -> FabricResponse:
        return FabricResponse(
            id=self.id,
            name=self.name,
            description=self.description,
            class_type=self.class_type,
            vlans=BaseHref(
                href=f"{V3_API_PREFIX}/vlans?filter=fabric_id eq {self.id}"
            ),
            hal_links=BaseHal(
                self=BaseHref(
                    href=f"{self_base_hyperlink.rstrip('/')}/{self.id}"
                )
            ),
        )
