# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


from maasservicelayer.models.base import (
    generate_builder,
    MaasTimestampedBaseModel,
)


@generate_builder()
class LegacyBootSourceSelection(MaasTimestampedBaseModel):
    os: str
    release: str
    arches: list[str]
    subarches: list[str]
    labels: list[str]
    boot_source_id: int
