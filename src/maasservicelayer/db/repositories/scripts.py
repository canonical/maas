# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Type

from sqlalchemy import Table

from maasservicelayer.db.mappers.scripts import ScriptsDomainDataMapper
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import ScriptTable
from maasservicelayer.models.script import Script


class ScriptsRepository(BaseRepository[Script]):
    def get_mapper(self) -> ScriptsDomainDataMapper:
        return ScriptsDomainDataMapper(Script, ScriptTable)

    def get_repository_table(self) -> Table:
        return ScriptTable

    def get_model_factory(self) -> Type[Script]:
        return Script
