# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock

import pytest

from maasservicelayer.context import Context
from maasservicelayer.db.repositories.mdns import MDNSRepository
from maasservicelayer.models.mdns import MDNS
from maasservicelayer.services.mdns import MDNSService
from maasservicelayer.utils.date import utcnow
from tests.maasservicelayer.services.base import ServiceCommonTests

TEST_MDNS = MDNS(
    id=1,
    created=utcnow(),
    updated=utcnow(),
    hostname="foo",
    ip="10.0.0.1",
    count=1,
    interface_id=1,
)


class TestCommonMDNSService(ServiceCommonTests):
    @pytest.fixture
    def service_instance(self) -> MDNSService:
        return MDNSService(
            context=Context(), mdns_repository=Mock(MDNSRepository)
        )

    @pytest.fixture
    def test_instance(self) -> MDNS:
        return TEST_MDNS
