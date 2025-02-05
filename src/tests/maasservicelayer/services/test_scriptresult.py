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
class TestScriptResultsService(ServiceCommonTests):
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
