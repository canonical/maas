#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Type

from sqlalchemy import Table

from maasservicelayer.db.mappers.scriptresults import (
    ScriptResultsDomainDataMapper,
)
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import ScriptResultTable
from maasservicelayer.models.scriptresult import ScriptResult


class ScriptResultsRepository(BaseRepository[ScriptResult]):
    def get_mapper(self) -> ScriptResultsDomainDataMapper:
        return ScriptResultsDomainDataMapper(ScriptResult, ScriptResultTable)

    def get_repository_table(self) -> Table:
        return ScriptResultTable

    def get_model_factory(self) -> Type[ScriptResult]:
        return ScriptResult
