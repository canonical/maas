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
    arch: str = Field(
        description="The architecture list for which to import resources.",
    )

    def to_builder(
        self, boot_source: BootSource
    ) -> BootSourceSelectionBuilder:
        return BootSourceSelectionBuilder(
            os=self.os,
            release=self.release,
            arch=self.arch,
            boot_source_id=boot_source.id,
        )
