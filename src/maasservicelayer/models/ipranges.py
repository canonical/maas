# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Optional

from pydantic import IPvAnyAddress

from maascommon.enums.ipranges import IPRangeType
from maasservicelayer.models.base import MaasTimestampedBaseModel, make_builder


class IPRange(MaasTimestampedBaseModel):
    type: IPRangeType
    start_ip: IPvAnyAddress
    end_ip: IPvAnyAddress
    comment: Optional[str] = None
    subnet_id: int
    user_id: Optional[int] = None


IPRangeBuilder = make_builder(IPRange)
