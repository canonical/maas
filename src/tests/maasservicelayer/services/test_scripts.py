# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import timedelta
from unittest.mock import Mock

import pytest

from maascommon.enums.node import HardwareDeviceTypeEnum
from maascommon.enums.script import ScriptParallel, ScriptType
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.scripts import ScriptsRepository
from maasservicelayer.models.script import Script
from maasservicelayer.services.scripts import ScriptsService
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
