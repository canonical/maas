#  Copyright 2023-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Optional

from maasservicelayer.models.base import MaasTimestampedBaseModel, make_builder


class DhcpSnippet(MaasTimestampedBaseModel):
    name: str
    description: str
    enabled: bool
    node_id: int
    subnet_id: int
    value_id: Optional[int] = None
    iprange_id: int


DhcpSnippetBuilder = make_builder(DhcpSnippet)
