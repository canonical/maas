# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Optional

from maasservicelayer.models.base import MaasTimestampedBaseModel, make_builder


class Domain(MaasTimestampedBaseModel):
    name: str
    authoritative: bool
    ttl: Optional[int]


DomainBuilder = make_builder(Domain)
