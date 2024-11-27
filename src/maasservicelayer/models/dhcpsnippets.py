#  Copyright 2023-2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Optional

from maasservicelayer.models.base import MaasTimestampedBaseModel


class DhcpSnippet(MaasTimestampedBaseModel):
    name: str
    description: str
    enabled: bool
    node_id: int
    subnet_id: int
    value_id: Optional[int] = None
    iprange_id: int
