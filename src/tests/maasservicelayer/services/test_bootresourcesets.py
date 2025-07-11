# Copyright 2025 Canonical Ltd. This software is licensed under the
# GNU Affero General Public License version 3 (see the set LICENSE).

from unittest.mock import Mock

import pytest

from maasservicelayer.context import Context
from maasservicelayer.db.repositories.bootresourcesets import (
    BootResourceSetsRepository,
)
from maasservicelayer.models.bootresourcesets import BootResourceSet
from maasservicelayer.services.bootresourcesets import BootResourceSetsService
from maasservicelayer.utils.date import utcnow
from tests.maasservicelayer.services.base import ServiceCommonTests


@pytest.mark.asyncio
class TestBootResourceSetsService(ServiceCommonTests):
    @pytest.fixture
    def service_instance(self) -> BootResourceSetsService:
        return BootResourceSetsService(
            context=Context(),
            repository=Mock(BootResourceSetsRepository),
        )

    @pytest.fixture
    def test_instance(self) -> BootResourceSet:
        now = utcnow()
        return BootResourceSet(
            id=1,
            created=now,
            updated=now,
            version="20250618",
            label="stable",
            resource_id=1,
        )
