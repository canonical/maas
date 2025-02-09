#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock

import pytest

from maascommon.enums.scriptresult import ScriptStatus
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.scriptresults import (
    ScriptResultsRepository,
)
from maasservicelayer.models.scriptresult import ScriptResult
from maasservicelayer.services.scriptresult import ScriptResultsService
from tests.maasservicelayer.services.base import ServiceCommonTests


@pytest.mark.asyncio
class TestCommonScriptResultsService(ServiceCommonTests):
    @pytest.fixture
    def service_instance(self) -> ScriptResultsService:
        return ScriptResultsService(
            context=Context(),
            scriptresults_repository=Mock(ScriptResultsRepository),
        )

    @pytest.fixture
    def test_instance(self) -> ScriptResult:
        return ScriptResult(
            id=1, script_set_id=10, status=ScriptStatus.PASSED, parameters={}
        )


@pytest.mark.asyncio
class TestScriptResultsService:
    @pytest.fixture
    def scriptresults_repository_mock(self):
        return Mock(ScriptResultsRepository)

    @pytest.fixture
    def scriptresults_service(
        self,
        scriptresults_repository_mock,
    ) -> ScriptResultsService:
        return ScriptResultsService(
            context=Context(),
            scriptresults_repository=scriptresults_repository_mock,
        )

    async def test_update_running_scripts(
        self, scriptresults_service, scriptresults_repository_mock
    ):
        script_sets = [1, 2, 3]
        new_status = ScriptStatus.FAILED

        await scriptresults_service.update_running_scripts(
            scripts_sets=script_sets, new_status=new_status
        )

        scriptresults_repository_mock.update_many.assert_called_once()
        kwargs = scriptresults_repository_mock.update_many.call_args.kwargs
        query = str(
            kwargs["query"].where.condition.compile(
                compile_kwargs={"literal_binds": True}
            )
        )
        assert (
            query
            == "maasserver_scriptresult.status IN (0, 1) AND maasserver_scriptresult.script_set_id IN (1, 2, 3)"
        )
