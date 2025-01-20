# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Optional

from maasservicelayer.models.base import MaasTimestampedBaseModel, make_builder


class Fabric(MaasTimestampedBaseModel):
    name: Optional[str]
    description: Optional[str]
    class_type: Optional[str]


FabricBuilder = make_builder(Fabric)
