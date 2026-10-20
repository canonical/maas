# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import timedelta
from unittest.mock import Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maascommon.enums.node import HardwareDeviceTypeEnum
from maascommon.enums.script import ScriptParallel, ScriptType
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.scripts import ScriptsRepository
from maasservicelayer.models.script import Script
from maasservicelayer.services.scripts import (
    get_unmatched_selection,
    ScriptsService,
)
from tests.fixtures.factories.script import (
    create_test_script_entry,
    make_script,
)
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasservicelayer.services.base import ServiceCommonTests


@pytest.mark.asyncio
class TestCommonScriptsService(ServiceCommonTests):
    @pytest.fixture
    def service_instance(self) -> ScriptsService:
        return ScriptsService(
            context=Context(),
            repository=Mock(ScriptsRepository),
        )

    @pytest.fixture
    def test_instance(self) -> Script:
        return Script(
            id=1,
            name="smartctl",
            title="smartctl",
            description="",
            tags=[],
            script_type=ScriptType.COMMISSIONING,
            timeout=timedelta(),
            destructive=False,
            default=True,
            script_id=10,
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


@pytest.mark.asyncio
class TestIntegrationScriptsService:
    @pytest.fixture
    def service(self, db_connection: AsyncConnection) -> ScriptsService:
        context = Context(connection=db_connection)
        return ScriptsService(
            context=context, repository=ScriptsRepository(context)
        )

    @pytest.fixture
    async def commissioning_scripts(self, fixture: Fixture) -> None:
        for name, extra in {
            "builtin": {"default": True},
            "user": {"tags": ["storage"]},
            "untagged": {"tags": None},
            "noauto": {"tags": ["noauto"]},
            "for-hardware": {"for_hardware": ["pci:8086:1918"]},
            "testing": {"script_type": ScriptType.TESTING},
        }.items():
            await create_test_script_entry(
                fixture,
                name=name,
                **{"script_type": ScriptType.COMMISSIONING, **extra},
            )

    @pytest.mark.usefixtures("commissioning_scripts")
    @pytest.mark.parametrize("selection", [None, []])
    async def test_commissioning_scripts_default(
        self, service: ScriptsService, selection: list[str] | None
    ) -> None:
        scripts = await service.get_commissioning_scripts(selection)
        assert {script.name for script in scripts} == {
            "builtin",
            "user",
            "untagged",
        }

    @pytest.mark.usefixtures("commissioning_scripts")
    async def test_commissioning_scripts_none_selects_builtin_only(
        self, service: ScriptsService
    ) -> None:
        scripts = await service.get_commissioning_scripts(["user", "none"])
        assert [script.name for script in scripts] == ["builtin"]

    @pytest.mark.parametrize("selection", [["none"], ["user"]])
    async def test_commissioning_scripts_selects_tagged_with_builtin_name(
        self, service: ScriptsService, fixture: Fixture, selection: list[str]
    ) -> None:
        await create_test_script_entry(
            fixture,
            name="builtin-test",
            default=True,
            script_type=ScriptType.TESTING,
        )
        await create_test_script_entry(
            fixture, name="tagged", tags=["builtin-test"]
        )
        await create_test_script_entry(fixture, name="user")

        scripts = await service.get_commissioning_scripts(selection)
        assert "tagged" in {script.name for script in scripts}

    @pytest.mark.usefixtures("commissioning_scripts")
    async def test_commissioning_scripts_selection_includes_builtin(
        self, service: ScriptsService
    ) -> None:
        scripts = await service.get_commissioning_scripts(
            ["noauto", "for-hardware", "testing"]
        )
        assert {script.name for script in scripts} == {
            "builtin",
            "noauto",
            "for-hardware",
        }

    async def test_commissioning_scripts_selected_by_tag_or_id(
        self, service: ScriptsService, fixture: Fixture
    ) -> None:
        await create_test_script_entry(fixture, name="by-tag", tags=["fw"])
        by_id = await create_test_script_entry(fixture, name="by-id")
        await create_test_script_entry(fixture, name="unselected")

        scripts = await service.get_commissioning_scripts(
            ["fw", str(by_id.id)]
        )
        assert {script.name for script in scripts} == {"by-tag", "by-id"}

    async def test_testing_scripts_default_to_commissioning_tag(
        self, service: ScriptsService, fixture: Fixture
    ) -> None:
        for name, tags in {
            "tagged": ["commissioning"],
            "untagged": None,
            "other": ["storage"],
        }.items():
            await create_test_script_entry(
                fixture, name=name, tags=tags, script_type=ScriptType.TESTING
            )
        await create_test_script_entry(
            fixture, name="commissioning", tags=["commissioning"]
        )

        scripts = await service.get_testing_scripts(None)
        assert [script.name for script in scripts] == ["tagged"]

    async def test_testing_scripts_selection(
        self, service: ScriptsService, fixture: Fixture
    ) -> None:
        await create_test_script_entry(
            fixture,
            name="smartctl",
            tags=["commissioning"],
            script_type=ScriptType.TESTING,
        )
        await create_test_script_entry(
            fixture,
            name="memtester",
            tags=["memory"],
            script_type=ScriptType.TESTING,
        )

        scripts = await service.get_testing_scripts(["memtester"])
        assert [script.name for script in scripts] == ["memtester"]

    async def test_testing_scripts_none_selects_nothing(
        self, service: ScriptsService, fixture: Fixture
    ) -> None:
        await create_test_script_entry(
            fixture,
            name="smartctl",
            tags=["commissioning"],
            script_type=ScriptType.TESTING,
        )

        assert await service.get_testing_scripts(["none"]) == []


class TestGetUnmatchedSelection:
    @pytest.mark.parametrize("selection", [None, []])
    def test_without_selection(self, selection: list[str] | None) -> None:
        assert get_unmatched_selection(selection, []) == []

    def test_matches_names_tags_and_ids(self) -> None:
        scripts = [
            make_script("smartctl", id=5, tags=["storage"]),
            make_script("memtester", id=7, tags=None),
        ]
        assert (
            get_unmatched_selection(
                ["smartctl", "storage", "7", "05", "none"], scripts
            )
            == []
        )

    def test_returns_unmatched_entries(self) -> None:
        scripts = [make_script("smartctl", id=5)]
        assert get_unmatched_selection(["smartctl", "typo", "6"], scripts) == [
            "typo",
            "6",
        ]
