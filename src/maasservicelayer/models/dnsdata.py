#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).


from maasservicelayer.models.base import (
    generate_builder,
    MaasTimestampedBaseModel,
)


@generate_builder()
class DNSData(MaasTimestampedBaseModel):
    dnsresource_id: int
    ttl: int | None = None
    rrtype: str
    rrdata: str
