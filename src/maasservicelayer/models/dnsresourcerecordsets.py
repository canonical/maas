# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Any

from pydantic import BaseModel

from maascommon.enums.dns import DNSResourceTypeEnum


class GenericDNSRecord(BaseModel):
    name: str
    node_id: int | None = None
    ttl: int | None = None
    rrtype: DNSResourceTypeEnum
    rrdatas: list[Any]
