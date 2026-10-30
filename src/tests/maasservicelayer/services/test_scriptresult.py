#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maascommon.enums.scriptresult import ScriptStatus
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.scriptresults import (
    ScriptResultsRepository,
)
from maasservicelayer.filters.query import QuerySpec
from maasservicelayer.filters.scriptresults import ScriptResultFilters
from maasservicelayer.models.scriptresult import ScriptResult
from maasservicelayer.services.scriptresult import ScriptResultsService
from tests.fixtures.factories.node import create_test_machine_entry
from tests.fixtures.factories.scriptresult import (
    create_test_scriptresult_entry,
)
from tests.fixtures.factories.scriptset import create_test_scriptset_entry
from tests.maasapiserver.fixtures.db import Fixture
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
    @pytest.mark.parametrize("empty_selection", [False, True])
    async def test_updates_only_active_scripts_in_selected_sets(
        self,
        db_connection: AsyncConnection,
        fixture: Fixture,
        empty_selection: bool,
    ) -> None:
        node = await create_test_machine_entry(fixture)
        selected = await create_test_scriptset_entry(fixture, node["id"])
        other = await create_test_scriptset_entry(fixture, node["id"])
        pending = await create_test_scriptresult_entry(
            fixture, selected["id"], status=ScriptStatus.PENDING
        )
        running = await create_test_scriptresult_entry(
            fixture, selected["id"], status=ScriptStatus.RUNNING
        )
        completed = await create_test_scriptresult_entry(
            fixture, selected["id"], status=ScriptStatus.PASSED
        )
        unrelated = await create_test_scriptresult_entry(
            fixture, other["id"], status=ScriptStatus.RUNNING
        )
        context = Context(connection=db_connection)
        repository = ScriptResultsRepository(context)
        service = ScriptResultsService(context, repository)

        updated = await service.update_running_scripts(
            scripts_sets=[] if empty_selection else [selected["id"]],
            new_status=ScriptStatus.FAILED,
        )

        assert {result.id for result in updated} == (
            set() if empty_selection else {pending.id, running.id}
        )
        results = await repository.get_many(
            QuerySpec(
                where=ScriptResultFilters.with_script_set_id_in(
                    [selected["id"], other["id"]]
                )
            )
        )
        assert {result.id: result.status for result in results} == {
            pending.id: ScriptStatus.PENDING
            if empty_selection
            else ScriptStatus.FAILED,
            running.id: ScriptStatus.RUNNING
            if empty_selection
            else ScriptStatus.FAILED,
            completed.id: ScriptStatus.PASSED,
            unrelated.id: ScriptStatus.RUNNING,
        }
