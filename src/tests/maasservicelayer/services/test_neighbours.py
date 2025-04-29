#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from ipaddress import IPv4Address
from unittest.mock import Mock

import pytest

from maasservicelayer.context import Context
from maasservicelayer.db.repositories.neighbours import NeighboursRepository
from maasservicelayer.models.neighbours import Neighbour
from maasservicelayer.services.neighbours import NeighboursService
from maasservicelayer.utils.date import utcnow
from tests.maasservicelayer.services.base import ServiceCommonTests

TEST_NEIGHBOUR = Neighbour(
    id=1,
    created=utcnow(),
    updated=utcnow(),
    ip=IPv4Address("10.0.0.1"),
    mac_address="aa:bb:cc:dd:ee:ff",
    count=1,
    time=1,
    interface_id=1,
)


class TestCommonNeighboursService(ServiceCommonTests):
    @pytest.fixture
    def service_instance(self) -> NeighboursService:
        return NeighboursService(
            context=Context(), neighbours_repository=Mock(NeighboursRepository)
        )

    @pytest.fixture
    def test_instance(self) -> Neighbour:
        return TEST_NEIGHBOUR
