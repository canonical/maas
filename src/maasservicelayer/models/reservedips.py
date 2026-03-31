# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from pydantic import IPvAnyAddress

from maasservicelayer.models.base import (
    generate_builder,
    MaasTimestampedBaseModel,
)
from maasservicelayer.models.fields import MacAddress


@generate_builder()
class ReservedIP(MaasTimestampedBaseModel):
    ip: IPvAnyAddress
    mac_address: MacAddress
    comment: str | None = None
    subnet_id: int
