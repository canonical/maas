#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from pydantic import BaseModel, IPvAnyAddress

from maascommon.enums.ipaddress import LeaseAction
from maasservicelayer.models.fields import MacAddress


class LeaseInfoRequest(BaseModel):
    action: LeaseAction
    ip_family: str
    hostname: str
    mac: MacAddress
    ip: IPvAnyAddress
    timestamp: int
    lease_time: int  # seconds
