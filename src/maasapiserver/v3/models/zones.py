from datetime import datetime
import hashlib

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
