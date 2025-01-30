#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Optional

from maasservicelayer.models.base import (
    generate_builder,
    MaasTimestampedBaseModel,
)


@generate_builder()
class DNSData(MaasTimestampedBaseModel):
    dnsresource_id: int
    ttl: Optional[int]
    rrtype: str
    rrdata: str
