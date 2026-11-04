from maascommon.enums.scriptresult import ScriptStatus
from maasservicelayer.builders.scriptresult import ScriptResultBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.scriptresults import (
    ScriptResultsRepository,
)
from maasservicelayer.filters.query import QuerySpec
from maasservicelayer.filters.scriptresults import ScriptResultFilters
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
                where=ScriptResultFilters.and_filters(
                    [
                        ScriptResultFilters.with_status_in(
                            [ScriptStatus.PENDING, ScriptStatus.RUNNING]
                        ),
                        ScriptResultFilters.with_script_set_id_in(
                            scripts_sets
                        ),
                    ]
                )
            ),
            builder=ScriptResultBuilder(status=new_status),
        )
