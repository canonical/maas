# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Optional

from maasapiserver.v3.api.models.responses.base import BaseHal, BaseHref
from maasapiserver.v3.api.models.responses.spaces import SpaceResponse
from maasapiserver.v3.constants import V3_API_PREFIX
from maasapiserver.v3.models.base import MaasTimestampedBaseModel


class Space(MaasTimestampedBaseModel):
    name: Optional[str]
    description: Optional[str]

    def to_response(self, self_base_hyperlink: str) -> SpaceResponse:
        return SpaceResponse(
            id=self.id,
            name=self.name,
            description=self.description,
            vlans=BaseHref(
                href=f"{V3_API_PREFIX}/vlans?filter=space_id eq {self.id}"
            ),
            subnets=BaseHref(
                href=f"{V3_API_PREFIX}/subnets?filter=space_id eq {self.id}"
            ),
            hal_links=BaseHal(
                self=BaseHref(
                    href=f"{self_base_hyperlink.rstrip('/')}/{self.id}"
                )
            ),
        )
