#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

import datetime
from typing import Optional

from pydantic import IPvAnyAddress

from maascommon.enums.ipaddress import IpAddressType
from maasservicelayer.models.base import MaasTimestampedBaseModel, make_builder


class StaticIPAddress(MaasTimestampedBaseModel):
    ip: Optional[IPvAnyAddress]
    alloc_type: IpAddressType
    lease_time: int
    temp_expires_on: Optional[datetime.datetime]
    subnet_id: int


StaticIPAddressBuilder = make_builder(StaticIPAddress)
