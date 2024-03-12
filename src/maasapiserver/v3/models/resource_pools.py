from maasapiserver.v3.api.models.responses.base import BaseHal, BaseHref
from maasapiserver.v3.api.models.responses.resource_pools import (
    ResourcePoolResponse,
)
from maasapiserver.v3.models.base import MaasTimestampedBaseModel


class ResourcePool(MaasTimestampedBaseModel):
    name: str
    description: str

    def to_response(self, self_base_hyperlink: str) -> ResourcePoolResponse:
        return ResourcePoolResponse(
            id=self.id,
            name=self.name,
            description=self.description,
            created=self.created,
            updated=self.updated,
            hal_links=BaseHal(
                self=BaseHref(
                    href=f"{self_base_hyperlink.rstrip('/')}/{self.id}"
                )
            ),
        )
