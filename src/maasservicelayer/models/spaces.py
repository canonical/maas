# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Optional

from maasservicelayer.models.base import MaasTimestampedBaseModel, make_builder


class Space(MaasTimestampedBaseModel):
    name: Optional[str]
    description: Optional[str]


SpaceBuilder = make_builder(Space)
