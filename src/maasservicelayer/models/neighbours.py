#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).


from pydantic import IPvAnyAddress

from maasservicelayer.models.base import (
    generate_builder,
    MaasTimestampedBaseModel,
)
from maasservicelayer.models.fields import MacAddress


@generate_builder()
class Neighbour(MaasTimestampedBaseModel):
    ip: IPvAnyAddress | None
    time: int
    count: int
    mac_address: MacAddress | None
    vid: int | None
    interface_id: int
