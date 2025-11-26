# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


from fastapi import Query
from pydantic import BaseModel, Field

from maasservicelayer.builders.bootsourceselections import (
    BootSourceSelectionBuilder,
)
from maasservicelayer.db.filters import Clause
from maasservicelayer.db.repositories.bootsourceselections import (
    BootSourceSelectionStatusClauseFactory,
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


class BootSourceSelectionFilterParams(BaseModel):
    ids: list[int] | None = Field(
        Query(
            default=None,
            alias="id",
            description="Filter by Boot Source Selection ID",
        )
    )

    def to_clause(self) -> Clause | None:
        if self.ids is not None:
            return BootSourceSelectionStatusClauseFactory.with_ids(self.ids)

        return None

    def to_href_format(self) -> str:
        if self.ids is not None:
            tokens = [f"id={id}" for id in self.ids]
            return "&".join(tokens)

        return ""
