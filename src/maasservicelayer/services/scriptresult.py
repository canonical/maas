from maascommon.enums.scriptresult import ScriptStatus
from maasservicelayer.builders.scriptresult import ScriptResultBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.scriptresults import (
    ScriptResultClauseFactory,
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

    async def update_running_scripts(
        self, scripts_sets: list[int], new_status: ScriptStatus
    ):
        return await self.update_many(
            query=QuerySpec(
                where=ScriptResultClauseFactory.and_clauses(
                    [
                        ScriptResultClauseFactory.with_status_in(
                            [ScriptStatus.PENDING, ScriptStatus.RUNNING]
                        ),
                        ScriptResultClauseFactory.with_script_set_id_in(
                            scripts_sets
                        ),
                    ]
                )
            ),
            builder=ScriptResultBuilder(status=new_status),
        )
