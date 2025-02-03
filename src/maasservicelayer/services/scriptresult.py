from maasservicelayer.builders.scriptresult import ScriptResultBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.scriptresults import (
    ScriptResultsRepository,
)
from maasservicelayer.models.scriptresult import ScriptResult
from maasservicelayer.services.base import BaseService


class ScriptResultsService(
    BaseService[ScriptResult, ScriptResultsRepository, ScriptResultBuilder]
):
    def __init__(
        self,
        context: Context,
        scriptresults_repository: ScriptResultsRepository,
    ):
        super().__init__(context, scriptresults_repository)
