from typing import Optional

from maasservicelayer.models.base import MaasTimestampedBaseModel


class DNSResource(MaasTimestampedBaseModel):
    name: str
    address_ttl: Optional[int]
    domain_id: int
