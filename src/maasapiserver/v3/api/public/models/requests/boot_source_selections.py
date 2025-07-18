# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


from pydantic import BaseModel, Field

from maasservicelayer.builders.bootsourceselections import (
    BootSourceSelectionBuilder,
)
from maasservicelayer.models.bootsources import BootSource


class BootSourceSelectionRequest(BaseModel):
    os: str = Field(
        description="The OS (e.g. ubuntu, centos) for which to import resources."
    )
    release: str = Field(
        description="The release for which to import resources."
    )
    arches: list[str] | None = Field(
        description="The architecture list for which to import resources.",
        default=["*"],
    )
    subarches: list[str] | None = Field(
        description="The subarchitecture list for which to import resources.",
        default=["*"],
    )
    labels: list[str] | None = Field(
        description="The label lists for which to import resources.",
        default=["*"],
    )

    def to_builder(
        self, boot_source: BootSource
    ) -> BootSourceSelectionBuilder:
        return BootSourceSelectionBuilder(
            os=self.os,
            release=self.release,
            arches=self.arches,
            subarches=self.subarches,
            labels=self.labels,
            boot_source_id=boot_source.id,
        )
