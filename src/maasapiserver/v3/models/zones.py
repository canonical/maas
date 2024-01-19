from datetime import datetime
import hashlib

from maasapiserver.v3.api.models.responses.base import BaseHal, BaseHref
from maasapiserver.v3.api.models.responses.zones import ZoneResponse
from maasapiserver.v3.models.base import MaasBaseModel


class Zone(MaasBaseModel):
    id: int
    created: datetime
    updated: datetime
    name: str
    description: str

    def etag(self):
        m = hashlib.sha256()
        m.update(self.updated.isoformat().encode("utf-8"))
        return m.hexdigest()

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
