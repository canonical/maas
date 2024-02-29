from maasapiserver.v3.api.models.responses.base import BaseHal, BaseHref
from maasapiserver.v3.api.models.responses.zones import ZoneResponse
from maasapiserver.v3.models.base import MaasTimestampedBaseModel


class Zone(MaasTimestampedBaseModel):
    name: str
    description: str

    def to_response(self, self_base_hyperlink: str) -> ZoneResponse:
        return ZoneResponse(
            id=self.id,
            name=self.name,
            description=self.description,
            hal_links=BaseHal(
                self=BaseHref(
                    href=f"{self_base_hyperlink.rstrip('/')}/{self.id}"
                )
            ),
        )
