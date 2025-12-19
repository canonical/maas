# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


from fastapi import Query
from pydantic import BaseModel, Field

from maasservicelayer.builders.bootsourceselections import (
    BootSourceSelectionBuilder,
)
from maasservicelayer.db.filters import Clause
from maasservicelayer.db.repositories.bootsourceselections import (
    BootSourceSelectionClauseFactory,
    BootSourceSelectionStatusClauseFactory,
)
from maasservicelayer.models.bootsources import BootSource


class BaseSelectionRequest(BaseModel):
    os: str = Field(
        description="The OS (e.g. ubuntu, centos) for which to import resources."
    )
    release: str = Field(
        description="The release for which to import resources."
    )
    arch: str = Field(
        description="The architecture list for which to import resources.",
    )


class BootSourceSelectionRequest(BaseSelectionRequest):
    def to_builder(
        self, boot_source: BootSource
    ) -> BootSourceSelectionBuilder:
        return BootSourceSelectionBuilder(
            os=self.os,
            release=self.release,
            arch=self.arch,
            boot_source_id=boot_source.id,
        )


class SelectionRequest(BaseSelectionRequest):
    boot_source_id: int = Field(
        description="The id of the boot source that this selection refers to"
    )

    def to_builder(self) -> BootSourceSelectionBuilder:
        return BootSourceSelectionBuilder(
            os=self.os,
            release=self.release,
            arch=self.arch,
            boot_source_id=self.boot_source_id,
        )


class BulkSelectionRequest(BaseModel):
    selections: list[SelectionRequest] = Field(
        description="Boot source selections to create",
        min_items=1,
        unique_items=True,
    )

    def get_builders(self) -> list[BootSourceSelectionBuilder]:
        return [s.to_builder() for s in self.selections]


class BootSourceSelectionStatusFilterParams(BaseModel):
    ids: list[int] | None = Field(
        Query(
            default=None,
            alias="id",
            description="Filter by Boot Source Selection ID",
        )
    )
    selected: bool | None = Field(
        Query(
            default=None,
            description="Filter by whether the boot source selection is selected",
        )
    )

    def to_clause(self) -> Clause | None:
        clauses = []
        if self.ids is not None:
            clauses.append(
                BootSourceSelectionStatusClauseFactory.with_ids(self.ids)
            )
        if self.selected is not None:
            clauses.append(
                BootSourceSelectionStatusClauseFactory.with_selected(
                    self.selected
                )
            )

        if not clauses:
            return None
        elif len(clauses) == 1:
            return clauses[0]
        else:
            return BootSourceSelectionStatusClauseFactory.and_clauses(clauses)

    def to_href_format(self) -> str:
        tokens = []
        if self.ids is not None:
            tokens.extend([f"id={id}" for id in self.ids])

        if self.selected is not None:
            tokens.append(f"selected={str(self.selected).lower()}")

        if tokens:
            return "&".join(tokens)
        return ""


class BootSourceSelectionStatisticFilterParams(BaseModel):
    ids: list[int] | None = Field(
        Query(
            default=None,
            alias="id",
            description="Filter by Boot Source Selection ID",
        )
    )

    def to_clause(self) -> Clause | None:
        if self.ids is not None:
            return BootSourceSelectionClauseFactory.with_ids(self.ids)
        return None

    def to_href_format(self) -> str | None:
        if self.ids is not None:
            return "&".join([f"id={id}" for id in self.ids])
        return None
