import datetime
from typing import Optional

from pydantic import IPvAnyAddress

from maascommon.enums.ipaddress import IpAddressType
from maasservicelayer.models.base import MaasTimestampedBaseModel


class StaticIPAddress(MaasTimestampedBaseModel):
    ip: Optional[IPvAnyAddress]
    alloc_type: IpAddressType
    lease_time: int
    temp_expires_on: Optional[datetime.datetime]
    subnet_id: int
