# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock

import pytest

from maasservicelayer.context import Context
from maasservicelayer.db.repositories.rdns import RDNSRepository
from maasservicelayer.models.rdns import RDNS
from maasservicelayer.services.rdns import RDNSService
from maasservicelayer.utils.date import utcnow
from tests.maasservicelayer.services.base import ServiceCommonTests

TEST_RDNS = RDNS(
    id=1,
    created=utcnow(),
    updated=utcnow(),
    hostname="foo",
    hostnames=["foo"],
    ip="10.0.0.1",
    observer_id=1,
)


class TestCommonRDNSService(ServiceCommonTests):
    @pytest.fixture
    def service_instance(self) -> RDNSService:
        return RDNSService(
            context=Context(), rdns_repository=Mock(RDNSRepository)
        )

    @pytest.fixture
    def test_instance(self) -> RDNS:
        return TEST_RDNS
