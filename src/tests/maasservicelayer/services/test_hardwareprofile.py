# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime, timezone
import json
from unittest.mock import Mock, patch

import pytest

from maascommon.enums.scriptresult import ScriptStatus
from maasservicelayer.builders.hardwareprofile import HardwareProfileBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.hardwareprofile import (
    HardwareProfileRepository,
)
from maasservicelayer.db.repositories.scriptresults import (
    ScriptResultClauseFactory,
)
from maasservicelayer.models.hardwareprofile import HardwareProfile
from maasservicelayer.models.scriptresult import ScriptResult
from maasservicelayer.services.hardwareprofile import HardwareProfileService
from maasservicelayer.services.scriptresult import ScriptResultsService
from tests.maasservicelayer.services.base import ServiceCommonTests


def _make_script_result(output: str) -> ScriptResult:
    now = datetime.now(timezone.utc)
    return ScriptResult(
        id=1,
        created=now,
        updated=now,
        script_set_id=1,
        status=ScriptStatus.PASSED,
        stdout="",
        stderr="",
        result="",
        output=output,
        parameters={},
        suppressed=False,
    )


class TesthardwareprofilesServiceCommon(ServiceCommonTests):
    @pytest.fixture
    def service_instance(self) -> HardwareProfileService:
        return HardwareProfileService(
            context=Context(),
            hardware_profile_repository=Mock(HardwareProfileRepository),
            scriptresults_service=Mock(ScriptResultsService),
        )

    @pytest.fixture
    def test_instance(self) -> HardwareProfile:
        return HardwareProfile(
            id=1,
            node_id=1,
            architecture="amd64/generic",
            cpu_cores=4,
            cpu_speed_mhz=2400,
            memory_mb=4096,
            disk_count=1,
            total_storage_bytes=512 * 1024 * 1024 * 1024,
            nic_count=1,
            gpu_count=0,
            system_vendor=None,
            system_product=None,
            hardware_fingerprint="a" * 64,
            storage=[],
            network=[],
            accelerators=[],
        )

    @pytest.fixture
    def builder_model(self) -> type[HardwareProfileBuilder]:
        return HardwareProfileBuilder


@pytest.mark.asyncio
class TestHardwareProfileService:
    @pytest.fixture
    def mock_repository(self):
        return Mock(HardwareProfileRepository)

    @pytest.fixture
    def mock_scriptresults_service(self):
        return Mock(ScriptResultsService)

    @pytest.fixture
    def service(
        self, mock_repository, mock_scriptresults_service
    ) -> HardwareProfileService:
        return HardwareProfileService(
            context=Context(),
            hardware_profile_repository=mock_repository,
            scriptresults_service=mock_scriptresults_service,
        )

    async def test_create_or_update(
        self, service: HardwareProfileService, mock_repository: Mock
    ):
        builder = HardwareProfileBuilder()
        await service.create_or_update(builder)

        mock_repository.create_or_update.assert_called_once_with(builder)

    async def test_populate_all_skips_if_profiles_already_exist(
        self,
        service: HardwareProfileService,
        mock_repository: Mock,
        mock_scriptresults_service: Mock,
    ):
        mock_repository.exists.return_value = True

        await service.populate_all()

        mock_repository.exists.assert_awaited_once_with(query=QuerySpec())
        mock_scriptresults_service.get_latest_for_nodes.assert_not_called()
        mock_repository.create_many.assert_not_called()

    async def test_populate_all_creates_a_profile_for_every_node(
        self,
        service: HardwareProfileService,
        mock_repository: Mock,
        mock_scriptresults_service: Mock,
    ):
        mock_repository.exists.return_value = False
        script_result = _make_script_result(json.dumps({"foo": "bar"}))
        mock_scriptresults_service.get_latest_for_nodes.return_value = [
            (1, script_result)
        ]
        builder = HardwareProfileBuilder(node_id=1)

        with patch.object(
            HardwareProfileBuilder,
            "from_commissioning_output",
            return_value=builder,
        ) as mock_from_commissioning_output:
            await service.populate_all()

        mock_scriptresults_service.get_latest_for_nodes.assert_awaited_once_with(
            QuerySpec(
                where=ScriptResultClauseFactory.with_script_name(
                    "50-maas-01-commissioning"
                )
            )
        )
        mock_from_commissioning_output.assert_called_once_with(
            {"foo": "bar"}, 1
        )
        mock_repository.create_many.assert_awaited_once_with(
            builders=[builder]
        )

    async def test_populate_all_skips_node_with_unparsable_output(
        self,
        service: HardwareProfileService,
        mock_repository: Mock,
        mock_scriptresults_service: Mock,
    ):
        mock_repository.exists.return_value = False
        bad_script_result = _make_script_result("not-valid-json")
        good_script_result = _make_script_result(json.dumps({"foo": "bar"}))
        mock_scriptresults_service.get_latest_for_nodes.return_value = [
            (1, bad_script_result),
            (2, good_script_result),
        ]
        builder = HardwareProfileBuilder(node_id=2)

        with patch.object(
            HardwareProfileBuilder,
            "from_commissioning_output",
            return_value=builder,
        ):
            await service.populate_all()

        mock_repository.create_many.assert_awaited_once_with(
            builders=[builder]
        )

    async def test_populate_all_does_not_call_create_many_when_no_profile_could_be_built(
        self,
        service: HardwareProfileService,
        mock_repository: Mock,
        mock_scriptresults_service: Mock,
    ):
        mock_repository.exists.return_value = False
        bad_script_result = _make_script_result("not-valid-json")
        mock_scriptresults_service.get_latest_for_nodes.return_value = [
            (1, bad_script_result)
        ]

        await service.populate_all()

        mock_repository.create_many.assert_not_called()
