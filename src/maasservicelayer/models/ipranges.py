# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


from pydantic import IPvAnyAddress

from maascommon.enums.ipranges import IPRangeType
from maasservicelayer.models.base import (
    generate_builder,
    MaasTimestampedBaseModel,
)


@generate_builder()
class IPRange(MaasTimestampedBaseModel):
    type: IPRangeType
    start_ip: IPvAnyAddress
    end_ip: IPvAnyAddress
    comment: str | None = None
    subnet_id: int
    user_id: int | None = None
