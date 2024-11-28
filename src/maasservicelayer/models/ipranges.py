from typing import Optional

from pydantic import IPvAnyAddress

from maascommon.enums.ipranges import IPRangeType
from maasservicelayer.models.base import MaasTimestampedBaseModel


class IPRange(MaasTimestampedBaseModel):
    type: IPRangeType
    start_ip: IPvAnyAddress
    end_ip: IPvAnyAddress
    comment: Optional[str] = None
    subnet_id: int
