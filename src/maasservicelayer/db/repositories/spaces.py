#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Type

from sqlalchemy import Table

from maasservicelayer.db.repositories.base import (
    BaseRepository,
    ResourceBuilder,
)
from maasservicelayer.db.tables import SpaceTable
from maasservicelayer.models.spaces import Space


class SpaceResourceBuilder(ResourceBuilder):
    def with_name(self, name: str) -> "SpaceResourceBuilder":
        self._request.set_value(SpaceTable.c.name.name, name)
        return self

    def with_description(self, description: str) -> "SpaceResourceBuilder":
        self._request.set_value(SpaceTable.c.description.name, description)
        return self


class SpacesRepository(BaseRepository[Space]):
    def get_repository_table(self) -> Table:
        return SpaceTable

    def get_model_factory(self) -> Type[Space]:
        return Space
