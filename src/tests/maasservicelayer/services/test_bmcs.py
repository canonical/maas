#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock

import pytest

from maasservicelayer.context import Context
from maasservicelayer.db.repositories.bmcs import BmcsRepository
from maasservicelayer.enums.power_drivers import PowerTypeEnum
from maasservicelayer.models.bmc import Bmc
from maasservicelayer.services.bmcs import BmcsService
from maasservicelayer.utils.date import utcnow
from tests.maasservicelayer.services.base import ServiceCommonTests


class TestCommonBmcsService(ServiceCommonTests):
    @pytest.fixture
    def service_instance(self) -> BmcsService:
        return BmcsService(
            context=Context(), bmcs_repository=Mock(BmcsRepository)
        )

    @pytest.fixture
    def test_instance(self) -> Bmc:
        now = utcnow()
        return Bmc(
            id=1,
            created=now,
            updated=now,
            power_type=PowerTypeEnum.LXD,
            power_parameters={
                "power_address": "https://192.0.2.10:8443",
                "instance_name": "test-vm",
                "project": "default",
            },
        )
