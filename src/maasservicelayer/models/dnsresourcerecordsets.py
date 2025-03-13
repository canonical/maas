# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Any, Optional

from pydantic import BaseModel

from maascommon.enums.dns import DNSResourceTypeEnum


class GenericDNSRecord(BaseModel):
    name: str
    node_id: Optional[int] | None = None
    ttl: Optional[int] | None = None
    rrtype: DNSResourceTypeEnum
    rrdatas: list[Any]
