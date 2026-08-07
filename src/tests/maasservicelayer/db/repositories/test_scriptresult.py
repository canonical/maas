# Copyright 2025-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maascommon.enums.scriptresult import ScriptStatus
from maasservicelayer.builders.scriptresult import ScriptResultBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.scriptresults import (
    ScriptResultClauseFactory,
    ScriptResultsRepository,
)
from maasservicelayer.models.base import ResourceBuilder
from maasservicelayer.models.scriptresult import ScriptResult
from tests.fixtures.factories.node import create_test_machine_entry
from tests.fixtures.factories.scriptresult import (
    create_test_scriptresult_entry,
)
from tests.fixtures.factories.scriptset import create_test_scriptset_entry
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasservicelayer.db.repositories.base import RepositoryCommonTests


class TestScriptResultClauseFactory:
    def test_with_script_id(self):
        clause = ScriptResultClauseFactory.with_script_id(1)
        assert (
            str(
                clause.condition.compile(
                    compile_kwargs={"literal_binds": True}
                )
            )
            == "maasserver_scriptresult.script_id = 1"
        )

    def test_with_script_id_in(self):
        clause = ScriptResultClauseFactory.with_script_id_in([1, 2, 3])
        assert (
            str(
                clause.condition.compile(
                    compile_kwargs={"literal_binds": True}
                )
            )
            == "maasserver_scriptresult.script_id IN (1, 2, 3)"
        )

    def test_with_script_set_id(self):
        clause = ScriptResultClauseFactory.with_script_set_id(1)
        assert (
            str(
                clause.condition.compile(
                    compile_kwargs={"literal_binds": True}
                )
            )
            == "maasserver_scriptresult.script_set_id = 1"
        )

    def test_with_script_set_id_in(self):
        clause = ScriptResultClauseFactory.with_script_set_id_in([1, 2, 3])
        assert (
            str(
                clause.condition.compile(
                    compile_kwargs={"literal_binds": True}
                )
            )
            == "maasserver_scriptresult.script_set_id IN (1, 2, 3)"
        )

    def test_with_script_name(self):
        clause = ScriptResultClauseFactory.with_script_name("my-script")
        assert (
            str(
                clause.condition.compile(
                    compile_kwargs={"literal_binds": True}
                )
            )
            == "maasserver_scriptresult.script_name = 'my-script'"
        )

    def test_with_status(self):
        clause = ScriptResultClauseFactory.with_status(ScriptStatus.PASSED)
        assert (
            str(
                clause.condition.compile(
                    compile_kwargs={"literal_binds": True}
                )
            )
            == f"maasserver_scriptresult.status = {ScriptStatus.PASSED}"
        )

    def test_with_status_in(self):
        clause = ScriptResultClauseFactory.with_status_in(
            [ScriptStatus.PENDING, ScriptStatus.RUNNING]
        )
        assert (
            str(
                clause.condition.compile(
                    compile_kwargs={"literal_binds": True}
                )
            )
            == f"maasserver_scriptresult.status IN ({ScriptStatus.PENDING}, {ScriptStatus.RUNNING})"
        )

    def test_with_node_id(self):
        clause = ScriptResultClauseFactory.with_node_id(1)
        assert (
            str(
                clause.condition.compile(
                    compile_kwargs={"literal_binds": True}
                )
            )
            == "maasserver_scriptset.node_id = 1"
        )


class TestScriptResultsRepository(RepositoryCommonTests[ScriptResult]):
    @pytest.fixture
    def repository_instance(
        self, db_connection: AsyncConnection
    ) -> ScriptResultsRepository:
        return ScriptResultsRepository(
            context=Context(connection=db_connection)
        )

    @pytest.fixture
    async def node_instance(self, fixture: Fixture) -> dict:
        return await create_test_machine_entry(fixture)

    @pytest.fixture
    async def scriptset_instance(
        self, fixture: Fixture, node_instance
    ) -> dict:
        return await create_test_scriptset_entry(
            fixture, node_id=node_instance["id"]
        )

    @pytest.fixture
    async def _setup_test_list(
        self, fixture: Fixture, scriptset_instance, num_objects: int
    ) -> list[ScriptResult]:
        return [
            await create_test_scriptresult_entry(
                fixture, script_set_id=scriptset_instance["id"]
            )
            for i in range(num_objects)
        ]

    @pytest.fixture
    async def instance_builder(self, scriptset_instance) -> ResourceBuilder:
        return ScriptResultBuilder(
            script_set_id=scriptset_instance["id"],
            status=ScriptStatus.PASSED,
            stdout="",
            stderr="",
            result="",
            output="",
            parameters={},
            suppressed=False,
        )

    @pytest.fixture
    async def instance_builder_model(self) -> type[ResourceBuilder]:
        return ScriptResultBuilder

    @pytest.fixture
    async def created_instance(
        self, fixture: Fixture, scriptset_instance
    ) -> ScriptResult:
        return await create_test_scriptresult_entry(
            fixture, script_set_id=scriptset_instance["id"]
        )

    @pytest.mark.skip(reason="There's no constraint in the DB for this table")
    async def test_create_duplicated(
        self, repository_instance, instance_builder
    ):
        raise NotImplementedError()

    @pytest.mark.skip(reason="There's no constraint in the DB for this table")
    async def test_create_many_duplicated(
        self, repository_instance, instance_builder
    ):
        raise NotImplementedError()


@pytest.mark.asyncio
class TestScriptResultsRepositoryGetLatestForNodes:
    @pytest.fixture
    def repository_instance(
        self, db_connection: AsyncConnection
    ) -> ScriptResultsRepository:
        return ScriptResultsRepository(
            context=Context(connection=db_connection)
        )

    async def test_returns_only_the_latest_passed_result_per_node(
        self,
        fixture: Fixture,
        repository_instance: ScriptResultsRepository,
    ):
        node_a = await create_test_machine_entry(fixture)
        node_b = await create_test_machine_entry(fixture)
        scriptset_a = await create_test_scriptset_entry(
            fixture, node_id=node_a["id"]
        )
        scriptset_b = await create_test_scriptset_entry(
            fixture, node_id=node_b["id"]
        )

        await create_test_scriptresult_entry(
            fixture,
            script_set_id=scriptset_a["id"],
            status=ScriptStatus.PASSED,
        )
        latest_a = await create_test_scriptresult_entry(
            fixture,
            script_set_id=scriptset_a["id"],
            status=ScriptStatus.PASSED,
        )
        # The most recent run for node_a failed, so the previous passed
        # result must still be returned.
        await create_test_scriptresult_entry(
            fixture,
            script_set_id=scriptset_a["id"],
            status=ScriptStatus.FAILED,
        )

        latest_b = await create_test_scriptresult_entry(
            fixture,
            script_set_id=scriptset_b["id"],
            status=ScriptStatus.PASSED,
        )

        results = dict(
            await repository_instance.get_latest_for_nodes(QuerySpec())
        )

        assert results == {
            node_a["id"]: latest_a,
            node_b["id"]: latest_b,
        }

    async def test_excludes_nodes_without_a_passed_result(
        self,
        fixture: Fixture,
        repository_instance: ScriptResultsRepository,
    ):
        node = await create_test_machine_entry(fixture)
        scriptset = await create_test_scriptset_entry(
            fixture, node_id=node["id"]
        )
        await create_test_scriptresult_entry(
            fixture,
            script_set_id=scriptset["id"],
            status=ScriptStatus.FAILED,
        )

        results = await repository_instance.get_latest_for_nodes(QuerySpec())

        assert results == []

    async def test_filters_by_query_spec(
        self,
        fixture: Fixture,
        repository_instance: ScriptResultsRepository,
    ):
        node = await create_test_machine_entry(fixture)
        scriptset = await create_test_scriptset_entry(
            fixture, node_id=node["id"]
        )
        matching = await create_test_scriptresult_entry(
            fixture,
            script_set_id=scriptset["id"],
            status=ScriptStatus.PASSED,
            script_id=1,
            script_name="50-maas-01-commissioning",
        )
        await create_test_scriptresult_entry(
            fixture,
            script_set_id=scriptset["id"],
            status=ScriptStatus.PASSED,
            script_id=2,
            script_name="30-maas-01-bmc-config",
        )

        results = await repository_instance.get_latest_for_nodes(
            QuerySpec(
                where=ScriptResultClauseFactory.with_script_name(
                    "50-maas-01-commissioning"
                )
            )
        )

        assert results == [(node["id"], matching)]
