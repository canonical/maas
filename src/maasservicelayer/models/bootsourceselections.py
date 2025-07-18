# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.models.base import (
    generate_builder,
    MaasTimestampedBaseModel,
)


@generate_builder()
class BootSourceSelection(MaasTimestampedBaseModel):
    os: str
    release: str
    arches: list[str] | None = None
    subarches: list[str] | None = None
    labels: list[str] | None = None
    boot_source_id: int
