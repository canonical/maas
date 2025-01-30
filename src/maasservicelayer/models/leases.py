#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from pydantic import BaseModel, IPvAnyAddress

from maascommon.enums.ipaddress import IpAddressFamily, LeaseAction
from maasservicelayer.models.base import generate_builder


@generate_builder()
class Lease(BaseModel):
    action: LeaseAction
    ip_family: IpAddressFamily
    hostname: str
    mac: str
    ip: IPvAnyAddress
    timestamp_epoch: int
    lease_time_seconds: int  # seconds
