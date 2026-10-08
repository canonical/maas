# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime, timezone

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
from maasservicelayer.models.nodes import Node
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
    async def node_instance(self, fixture: Fixture) -> Node:
        return await create_test_machine_entry(fixture)

    @pytest.fixture
    async def scriptset_instance(
        self, fixture: Fixture, node_instance
    ) -> Node:
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

    async def test_create_pending_with_script_reference(
        self, repository_instance: ScriptResultsRepository, scriptset_instance
    ) -> None:
        script_result = await repository_instance.create(
            builder=ScriptResultBuilder(
                script_set_id=scriptset_instance["id"],
                status=ScriptStatus.PENDING,
                script_id=1,
                script_name="smartctl-validate",
                script_version_id=1,
                parameters={"storage": {"value": "all"}},
                stdout="",
                stderr="",
                result="",
                output="",
                suppressed=False,
            )
        )
        assert script_result.status == ScriptStatus.PENDING
        assert script_result.script_id == 1
        assert script_result.script_name == "smartctl-validate"
        assert script_result.script_version_id == 1
        assert script_result.parameters == {"storage": {"value": "all"}}
        assert script_result.exit_status is None
        assert script_result.started is None
        assert script_result.ended is None
        assert script_result.physical_blockdevice_id is None
        assert script_result.interface_id is None

    async def test_create_pending_builtin_without_script_reference(
        self, repository_instance: ScriptResultsRepository, scriptset_instance
    ) -> None:
        """Builtin commissioning scripts aren't linked to a Script row.

        Only `script_name` is set, matching the legacy
        `ScriptResult.script_name` comment about results outliving a
        deleted Script.
        """
        script_result = await repository_instance.create(
            builder=ScriptResultBuilder(
                script_set_id=scriptset_instance["id"],
                status=ScriptStatus.PENDING,
                script_name="00-maas-05-kernel-cmdline",
                parameters={},
                stdout="",
                stderr="",
                result="",
                output="",
                suppressed=False,
            )
        )
        assert script_result.status == ScriptStatus.PENDING
        assert script_result.script_id is None
        assert script_result.script_name == "00-maas-05-kernel-cmdline"

    async def test_create_many_pending_results_per_storage_device(
        self, repository_instance: ScriptResultsRepository, scriptset_instance
    ) -> None:
        """One ScriptResult per block device, mirroring add_pending_script
        expanding a storage-type parameter into multiple results."""
        builders = [
            ScriptResultBuilder(
                script_set_id=scriptset_instance["id"],
                status=ScriptStatus.PENDING,
                script_id=1,
                script_name="smartctl-validate",
                physical_blockdevice_id=blockdevice_id,
                parameters={"storage": {"value": {"id": blockdevice_id}}},
                stdout="",
                stderr="",
                result="",
                output="",
                suppressed=False,
            )
            for blockdevice_id in (1, 2)
        ]

        created = await repository_instance.create_many(builders=builders)

        results = await repository_instance.get_many(
            query=QuerySpec(
                where=ScriptResultClauseFactory.with_script_set_id(
                    scriptset_instance["id"]
                )
            )
        )
        assert {r.id for r in created} == {r.id for r in results}
        assert {r.physical_blockdevice_id for r in results} == {1, 2}

    async def test_create_pending_with_started_and_ended(
        self, repository_instance: ScriptResultsRepository, scriptset_instance
    ) -> None:
        started = datetime.now(timezone.utc)
        ended = datetime.now(timezone.utc)

        script_result = await repository_instance.create(
            builder=ScriptResultBuilder(
                script_set_id=scriptset_instance["id"],
                status=ScriptStatus.PASSED,
                exit_status=0,
                started=started,
                ended=ended,
                interface_id=1,
                parameters={},
                stdout="",
                stderr="",
                result="",
                output="",
                suppressed=False,
            )
        )
        assert script_result.exit_status == 0
        assert script_result.started == started
        assert script_result.ended == ended
        assert script_result.interface_id == 1
