# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock

import pytest

from maasservicelayer.context import Context
from maasservicelayer.db.repositories.bootsourceselections import (
    BootSourceSelectionsRepository,
)
from maasservicelayer.models.base import MaasBaseModel
from maasservicelayer.models.bootsourceselections import BootSourceSelection
from maasservicelayer.services.base import BaseService
from maasservicelayer.services.bootsourceselections import (
    BootSourceSelectionsService,
)
from maasservicelayer.utils.date import utcnow
from tests.maasservicelayer.services.base import ServiceCommonTests


@pytest.mark.asyncio
class TestBootSourcesService(ServiceCommonTests):
    @pytest.fixture
    def service_instance(self) -> BaseService:
        return BootSourceSelectionsService(
            context=Context(),
            repository=Mock(BootSourceSelectionsRepository),
            cache=None,
        )

    @pytest.fixture
    def test_instance(self) -> MaasBaseModel:
        now = utcnow()
        return BootSourceSelection(
            id=1,
            created=now,
            updated=now,
            os="str",
            release="str",
            arches=["a", "b"],
            subarches=["1", "2"],
            labels=["lab-1", "lab-2"],
            boot_source_id=25,
        )
