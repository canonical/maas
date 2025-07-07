# Copyright 2025 Canonical Ltd. This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock

import pytest

from maasservicelayer.context import Context
from maasservicelayer.db.repositories.bootsourceselections import (
    BootSourceSelectionsRepository,
)
from maasservicelayer.models.bootsourceselections import BootSourceSelection
from maasservicelayer.services.bootsourceselections import (
    BootSourceSelectionsService,
)
from maasservicelayer.utils.date import utcnow
from tests.maasservicelayer.services.base import ServiceCommonTests


@pytest.mark.asyncio
class TestBootSourceSelectionsService(ServiceCommonTests):
    @pytest.fixture
    def service_instance(self) -> BootSourceSelectionsService:
        return BootSourceSelectionsService(
            context=Context(),
            repository=Mock(BootSourceSelectionsRepository),
        )

    @pytest.fixture
    def test_instance(self) -> BootSourceSelection:
        now = utcnow()
        return BootSourceSelection(
            id=1,
            created=now,
            updated=now,
            os="ubuntu",
            release="noble",
            arches=["amd64"],
            subarches=["*"],
            labels=["*"],
            boot_source_id=1,
        )
