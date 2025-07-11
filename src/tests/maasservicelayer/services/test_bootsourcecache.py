# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock

import pytest

from maasservicelayer.context import Context
from maasservicelayer.db.repositories.bootsourcecache import (
    BootSourceCacheRepository,
)
from maasservicelayer.models.bootsourcecache import BootSourceCache
from maasservicelayer.services.bootsourcecache import BootSourceCacheService
from maasservicelayer.utils.date import utcnow
from tests.maasservicelayer.services.base import ServiceCommonTests


class TestBootSourceCacheService(ServiceCommonTests):
    @pytest.fixture
    def service_instance(self) -> BootSourceCacheService:
        return BootSourceCacheService(
            context=Context(), repository=Mock(BootSourceCacheRepository)
        )

    @pytest.fixture
    def test_instance(self) -> BootSourceCache:
        now = utcnow()
        return BootSourceCache(
            id=1,
            created=now,
            updated=now,
            os="ubuntu",
            release="noble",
            arch="amd64",
            subarch="generic",
            label="stable",
            boot_source_id=1,
            extra={},
        )
