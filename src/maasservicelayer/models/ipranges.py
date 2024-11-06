from typing import Optional

from pydantic import IPvAnyAddress

from maasservicelayer.models.base import MaasTimestampedBaseModel


class IPRange(MaasTimestampedBaseModel):
    type: str
    start_ip: IPvAnyAddress
    end_ip: IPvAnyAddress
    comment: Optional[str] = None
    subnet_id: int
