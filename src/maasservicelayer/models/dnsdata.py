#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Optional

from maasservicelayer.models.base import MaasTimestampedBaseModel


class DNSData(MaasTimestampedBaseModel):
    dnsresource_id: int
    ttl: Optional[int]
    rrtype: str
    rrdata: str
