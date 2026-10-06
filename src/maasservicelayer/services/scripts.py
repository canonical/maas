# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.builders.script import ScriptBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.scripts import ScriptsRepository
from maasservicelayer.models.script import Script
from maasservicelayer.services.base import BaseService


class ScriptsService(BaseService[Script, ScriptsRepository, ScriptBuilder]):
    def __init__(
        self,
        context: Context,
        repository: ScriptsRepository,
    ):
        super().__init__(context, repository)
