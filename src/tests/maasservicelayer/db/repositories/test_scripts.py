# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maascommon.enums.node import HardwareDeviceTypeEnum
from maascommon.enums.script import ScriptParallel, ScriptType
from maasservicelayer.builders.script import ScriptBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.scripts import ScriptsRepository
from maasservicelayer.filters.query import QuerySpec
from maasservicelayer.filters.scripts import ScriptsFilters
from maasservicelayer.models.base import ResourceBuilder
from maasservicelayer.models.script import Script
from tests.fixtures.factories.script import (
    create_test_script_entry,
    create_test_versionedtextfile_entry,
)
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasservicelayer.db.repositories.base import RepositoryCommonTests


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
                where=ScriptsFilters.with_script_type(ScriptType.COMMISSIONING)
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
            QuerySpec(where=ScriptsFilters.with_default(True))
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
            QuerySpec(where=ScriptsFilters.with_tags_contains(["noauto"]))
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
                where=ScriptsFilters.with_tags_overlap(
                    ["enlisting", "deploy-info"]
                )
            )
        )
        assert {script.name for script in scripts} == {
            "enlist-script",
            "deploy-script",
        }

    async def test_get_many_filter_by_without_tags_contains(
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
            QuerySpec(where=ScriptsFilters.without_tags_contains(["noauto"]))
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
            QuerySpec(where=ScriptsFilters.with_empty_for_hardware())
        )
        assert len(scripts) == 1
        assert scripts[0].name == "generic-script"

    async def test_get_many_filter_by_nonempty_for_hardware(
        self, repository_instance: ScriptsRepository, fixture: Fixture
    ) -> None:
        await create_test_script_entry(
            fixture, name="generic-script", for_hardware=[]
        )
        hardware_script = await create_test_script_entry(
            fixture, name="hardware-script", for_hardware=["pci:8086:1918"]
        )

        scripts = await repository_instance.get_many(
            QuerySpec(where=ScriptsFilters.with_nonempty_for_hardware())
        )

        assert scripts == [hardware_script]

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

        scripts = await repository_instance.get_many(
            QuerySpec(
                where=ScriptsFilters.and_filters(
                    [
                        ScriptsFilters.with_script_type(
                            ScriptType.COMMISSIONING
                        ),
                        ScriptsFilters.with_empty_for_hardware(),
                        ScriptsFilters.without_tags_contains(["noauto"]),
                    ]
                )
            )
        )
        assert len(scripts) == 1
        assert scripts[0].name == "default-commissioning"
