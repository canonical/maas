#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Self, Type

from sqlalchemy import Table

from maasservicelayer.db.repositories.base import (
    BaseRepository,
    ResourceBuilder,
)
from maasservicelayer.db.tables import FabricTable
from maasservicelayer.models.fabrics import Fabric


class FabricsResourceBuilder(ResourceBuilder):
    def with_name(self, value: str) -> Self:
        self._request.set_value(FabricTable.c.name.name, value)
        return self

    def with_description(self, value: str | None = None) -> Self:
        if not value:
            value = ""
        self._request.set_value(FabricTable.c.description.name, value)
        return self

    def with_class_type(self, value: str) -> Self:
        self._request.set_value(FabricTable.c.class_type.name, value)
        return self


class FabricsRepository(BaseRepository[Fabric]):
    def get_repository_table(self) -> Table:
        return FabricTable

    def get_model_factory(self) -> Type[Fabric]:
        return Fabric
