# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock

import pytest

from maascommon.enums.boot_resources import BootResourceType
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.bootresources import (
    BootResourcesRepository,
)
from maasservicelayer.models.bootresources import BootResource
from maasservicelayer.services.bootresources import BootResourceService
from maasservicelayer.utils.date import utcnow
from tests.maasservicelayer.services.base import ServiceCommonTests


class TestBootResourceService(ServiceCommonTests):
    @pytest.fixture
    def service_instance(self) -> BootResourceService:
        return BootResourceService(
            context=Context(), repository=Mock(BootResourcesRepository)
        )

    @pytest.fixture
    def test_instance(self) -> BootResource:
        now = utcnow()
        return BootResource(
            id=1,
            created=now,
            updated=now,
            rtype=BootResourceType.SYNCED,
            name="ubuntu/noble",
            architecture="amd64/generic",
            rolling=False,
            base_image="",
            extra={},
        )
