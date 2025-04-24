# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime
from unittest.mock import Mock

import pytest

from maasservicelayer.context import Context
from maasservicelayer.db.repositories.discoveries import DiscoveriesRepository
from maasservicelayer.models.discoveries import Discovery
from maasservicelayer.models.fields import MacAddress
from maasservicelayer.services.discoveries import DiscoveriesService
from tests.maasservicelayer.services.base import ReadOnlyServiceCommonTests


class TestDiscoveriesService(ReadOnlyServiceCommonTests):
    @pytest.fixture
    def service_instance(self) -> DiscoveriesService:
        return DiscoveriesService(
            context=Context(),
            discoveries_repository=Mock(DiscoveriesRepository),
        )

    @pytest.fixture
    def test_instance(self) -> Discovery:
        return Discovery(
            id=1,
            discovery_id="MTAuMTAuMC4yOSwwMDoxNjozZToyOTphNTphMQ==",
            neighbour_id=1,
            ip="10.10.0.29",
            mac_address=MacAddress("aa:bb:cc:dd:ee:ff"),
            first_seen=datetime.now(),
            last_seen=datetime.now(),
            vid=1,
            observer_hostname="foo",
            observer_system_id="aabbcc",
            observer_id=1,
            observer_interface_id=1,
            observer_interface_name="eth0",
            mdns_id=1,
            hostname="bar",
            fabric_id=1,
            fabric_name="fabric-0",
            vlan_id=5001,
            is_external_dhcp=False,
            subnet_id=1,
            subnet_cidr="10.10.0.0/24",
            subnet_prefixlen=24,
        )
