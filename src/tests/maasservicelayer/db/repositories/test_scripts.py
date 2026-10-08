# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maascommon.enums.node import HardwareDeviceTypeEnum
from maascommon.enums.script import ScriptParallel, ScriptType
from maasservicelayer.builders.script import ScriptBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.scripts import (
    ScriptsClauseFactory,
    ScriptsRepository,
)
from maasservicelayer.models.base import ResourceBuilder
from maasservicelayer.models.script import Script
from tests.fixtures.factories.script import (
    create_test_script_entry,
    create_test_versionedtextfile_entry,
)
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasservicelayer.db.repositories.base import RepositoryCommonTests


class TestScriptsClauseFactory:
    def test_with_id(self) -> None:
        clause = ScriptsClauseFactory.with_id(1)
        assert (
            str(
                clause.condition.compile(
                    compile_kwargs={"literal_binds": True}
                )
            )
            == "maasserver_script.id = 1"
        )

    def test_with_ids(self) -> None:
        clause = ScriptsClauseFactory.with_ids([1, 2, 3])
        assert (
            str(
                clause.condition.compile(
                    compile_kwargs={"literal_binds": True}
                )
            )
            == "maasserver_script.id IN (1, 2, 3)"
        )

    def test_with_name(self) -> None:
        clause = ScriptsClauseFactory.with_name("smartctl")
        assert (
            str(
                clause.condition.compile(
                    compile_kwargs={"literal_binds": True}
                )
            )
            == "maasserver_script.name = 'smartctl'"
        )

    def test_with_names(self) -> None:
        clause = ScriptsClauseFactory.with_names(["smartctl", "memtester"])
        assert (
            str(
                clause.condition.compile(
                    compile_kwargs={"literal_binds": True}
                )
            )
            == "maasserver_script.name IN ('smartctl', 'memtester')"
        )

    def test_with_script_type(self) -> None:
        clause = ScriptsClauseFactory.with_script_type(
            ScriptType.COMMISSIONING
        )
        assert (
            str(
                clause.condition.compile(
                    compile_kwargs={"literal_binds": True}
                )
            )
            == f"maasserver_script.script_type = {ScriptType.COMMISSIONING}"
        )

    def test_with_default(self) -> None:
        clause = ScriptsClauseFactory.with_default(True)
        assert (
            str(
                clause.condition.compile(
                    compile_kwargs={"literal_binds": True}
                )
            )
            == 'maasserver_script."default" = true'
        )

    def test_with_tags_contains(self) -> None:
        clause = ScriptsClauseFactory.with_tags_contains(["noauto"])
        assert (
            str(
                clause.condition.compile(
                    compile_kwargs={"literal_binds": True}
                )
            )
            == "maasserver_script.tags @> ARRAY['noauto']"
        )

    def test_with_tags_overlap(self) -> None:
        clause = ScriptsClauseFactory.with_tags_overlap(
            ["enlisting", "deploy-info"]
        )
        assert (
            str(
                clause.condition.compile(
                    compile_kwargs={"literal_binds": True}
                )
            )
            == "maasserver_script.tags && ARRAY['enlisting', 'deploy-info']"
        )

    def test_without_tags(self) -> None:
        clause = ScriptsClauseFactory.without_tags(["noauto"])
        assert (
            str(
                clause.condition.compile(
                    compile_kwargs={"literal_binds": True}
                )
            )
            == "maasserver_script.tags IS NULL "
            "OR NOT ((maasserver_script.tags @> ARRAY['noauto']))"
        )

    def test_with_empty_for_hardware(self) -> None:
        clause = ScriptsClauseFactory.with_empty_for_hardware()
        assert (
            str(
                clause.condition.compile(
                    compile_kwargs={"literal_binds": True}
                )
            )
            == "maasserver_script.for_hardware = ARRAY[]"
        )

    def test_with_nonempty_for_hardware(self) -> None:
        clause = ScriptsClauseFactory.with_nonempty_for_hardware()
        assert (
            str(
                clause.condition.compile(
                    compile_kwargs={"literal_binds": True}
                )
            )
            == "maasserver_script.for_hardware != ARRAY[]"
        )


class TestScriptsRepository(RepositoryCommonTests[Script]):
    @pytest.fixture
    def repository_instance(
        self, db_connection: AsyncConnection
    ) -> ScriptsRepository:
        return ScriptsRepository(context=Context(connection=db_connection))

    @pytest.fixture
    async def _setup_test_list(
        self, fixture: Fixture, num_objects: int
    ) -> list[Script]:
        return [
            await create_test_script_entry(fixture, name=f"script-{i}")
            for i in range(num_objects)
        ]

    @pytest.fixture
    async def created_instance(self, fixture: Fixture) -> Script:
        return await create_test_script_entry(fixture, name="created-script")

    @pytest.fixture
    async def instance_builder_model(self) -> type[ResourceBuilder]:
        return ScriptBuilder

    @pytest.fixture
    async def instance_builder(self, fixture: Fixture) -> ResourceBuilder:
        versionedtextfile = await create_test_versionedtextfile_entry(fixture)
        return ScriptBuilder(
            name="builder-script",
            title="builder-script",
            description="",
            tags=[],
            script_type=ScriptType.COMMISSIONING,
            timeout=timedelta(),
            destructive=False,
            default=False,
            script_id=versionedtextfile["id"],
            hardware_type=HardwareDeviceTypeEnum.NODE,
            packages={},
            parallel=ScriptParallel.DISABLED,
            parameters={},
            results={},
            for_hardware=[],
            may_reboot=False,
            recommission=False,
            apply_configured_networking=False,
        )

    async def test_get_many_filter_by_script_type(
        self, repository_instance: ScriptsRepository, fixture: Fixture
    ) -> None:
        await create_test_script_entry(
            fixture,
            name="commissioning-script",
            script_type=ScriptType.COMMISSIONING,
        )
        await create_test_script_entry(
            fixture,
            name="testing-script",
            script_type=ScriptType.TESTING,
        )

        scripts = await repository_instance.get_many(
            QuerySpec(
                where=ScriptsClauseFactory.with_script_type(
                    ScriptType.COMMISSIONING
                )
            )
        )
        assert len(scripts) == 1
        assert scripts[0].name == "commissioning-script"

    async def test_get_many_filter_by_default(
        self, repository_instance: ScriptsRepository, fixture: Fixture
    ) -> None:
        await create_test_script_entry(
            fixture, name="builtin-script", default=True
        )
        await create_test_script_entry(
            fixture, name="user-script", default=False
        )

        scripts = await repository_instance.get_many(
            QuerySpec(where=ScriptsClauseFactory.with_default(True))
        )
        assert len(scripts) == 1
        assert scripts[0].name == "builtin-script"

    async def test_get_many_filter_by_tags_contains(
        self, repository_instance: ScriptsRepository, fixture: Fixture
    ) -> None:
        await create_test_script_entry(
            fixture, name="noauto-script", tags=["noauto", "commissioning"]
        )
        await create_test_script_entry(
            fixture, name="auto-script", tags=["commissioning"]
        )

        scripts = await repository_instance.get_many(
            QuerySpec(
                where=ScriptsClauseFactory.with_tags_contains(["noauto"])
            )
        )
        assert len(scripts) == 1
        assert scripts[0].name == "noauto-script"

    async def test_get_many_filter_by_tags_overlap(
        self, repository_instance: ScriptsRepository, fixture: Fixture
    ) -> None:
        await create_test_script_entry(
            fixture, name="enlist-script", tags=["enlisting"]
        )
        await create_test_script_entry(
            fixture, name="deploy-script", tags=["deploy-info"]
        )
        await create_test_script_entry(
            fixture, name="other-script", tags=["other"]
        )

        scripts = await repository_instance.get_many(
            QuerySpec(
                where=ScriptsClauseFactory.with_tags_overlap(
                    ["enlisting", "deploy-info"]
                )
            )
        )
        assert {script.name for script in scripts} == {
            "enlist-script",
            "deploy-script",
        }

    async def test_get_many_filter_by_without_tags(
        self, repository_instance: ScriptsRepository, fixture: Fixture
    ) -> None:
        await create_test_script_entry(
            fixture, name="noauto-script", tags=["noauto"]
        )
        await create_test_script_entry(
            fixture, name="auto-script", tags=["commissioning"]
        )
        await create_test_script_entry(
            fixture, name="no-tags-script", tags=None
        )

        scripts = await repository_instance.get_many(
            QuerySpec(where=ScriptsClauseFactory.without_tags(["noauto"]))
        )
        assert {script.name for script in scripts} == {
            "auto-script",
            "no-tags-script",
        }

    async def test_get_many_filter_by_empty_for_hardware(
        self, repository_instance: ScriptsRepository, fixture: Fixture
    ) -> None:
        await create_test_script_entry(
            fixture, name="generic-script", for_hardware=[]
        )
        await create_test_script_entry(
            fixture,
            name="pci-script",
            for_hardware=["pci:8086:1918"],
        )

        scripts = await repository_instance.get_many(
            QuerySpec(where=ScriptsClauseFactory.with_empty_for_hardware())
        )
        assert len(scripts) == 1
        assert scripts[0].name == "generic-script"

    async def test_get_many_filter_default_commissioning_selection(
        self, repository_instance: ScriptsRepository, fixture: Fixture
    ) -> None:
        await create_test_script_entry(
            fixture,
            name="default-commissioning",
            script_type=ScriptType.COMMISSIONING,
            for_hardware=[],
            tags=["commissioning"],
        )
        await create_test_script_entry(
            fixture,
            name="noauto-commissioning",
            script_type=ScriptType.COMMISSIONING,
            for_hardware=[],
            tags=["noauto"],
        )
        await create_test_script_entry(
            fixture,
            name="hardware-commissioning",
            script_type=ScriptType.COMMISSIONING,
            for_hardware=["pci:8086:1918"],
            tags=["commissioning"],
        )
        await create_test_script_entry(
            fixture,
            name="testing-script",
            script_type=ScriptType.TESTING,
            for_hardware=[],
            tags=["commissioning"],
        )
        await create_test_script_entry(
            fixture,
            name="no-tags-commissioning",
            script_type=ScriptType.COMMISSIONING,
            for_hardware=[],
            tags=None,
        )

        scripts = await repository_instance.get_many(
            QuerySpec(
                where=ScriptsClauseFactory.and_clauses(
                    [
                        ScriptsClauseFactory.with_script_type(
                            ScriptType.COMMISSIONING
                        ),
                        ScriptsClauseFactory.with_empty_for_hardware(),
                        ScriptsClauseFactory.without_tags(["noauto"]),
                    ]
                )
            )
        )
        assert {script.name for script in scripts} == {
            "default-commissioning",
            "no-tags-commissioning",
        }
