#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).
from enum import StrEnum

from pydantic import BaseModel, IPvAnyAddress

from maascommon.enums.ipaddress import LeaseAction
from maasservicelayer.models.fields import MacAddress


class LeaseIPFamily(StrEnum):
    IPV4 = "ipv4"
    IPV6 = "ipv6"


class LeaseInfoRequest(BaseModel):
    action: LeaseAction
    ip_family: LeaseIPFamily
    hostname: str
    # The MAC address may be absent, e.g. when the DHCP server reports a
    # DHCPDECLINE. We accept the request, and we let the service layer decide what to do.
    mac: MacAddress | None = None
    ip: IPvAnyAddress
    timestamp: int
    lease_time: int  # seconds
