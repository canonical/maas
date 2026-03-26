# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


from maasservicelayer.models.base import (
    generate_builder,
    MaasTimestampedBaseModel,
)


@generate_builder()
class Fabric(MaasTimestampedBaseModel):
    name: str | None = None
    description: str | None = None
    class_type: str | None = None
