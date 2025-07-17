# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from ipaddress import IPv4Address, IPv4Network
from unittest.mock import Mock

import pytest

from maascommon.enums.subnet import RdnsMode
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.ui_subnets import UISubnetsRepository
from maasservicelayer.models.ui_subnets import UISubnet
from maasservicelayer.services.ui_subnets import UISubnetsService
from maasservicelayer.utils.date import utcnow
from tests.maasservicelayer.services.base import ReadOnlyServiceCommonTests


class TestUISubnetsService(ReadOnlyServiceCommonTests):
    @pytest.fixture
    def service_instance(self) -> UISubnetsService:
        return UISubnetsService(
            context=Context(),
            ui_subnets_repository=Mock(UISubnetsRepository),
        )

    @pytest.fixture
    def test_instance(self) -> UISubnet:
        return UISubnet(
            id=1,
            created=utcnow(),
            updated=utcnow(),
            name="10.0.0.1/24",
            cidr=IPv4Network("10.0.0.1"),
            description="",
            rdns_mode=RdnsMode.DEFAULT,
            gateway_ip=IPv4Address("10.0.0.1"),
            dns_servers=[],
            allow_dns=True,
            allow_proxy=True,
            active_discovery=True,
            managed=True,
            disabled_boot_architectures=[],
            vlan_id=1,
            vlan_vid=0,
            fabric_id=1,
            fabric_name="fabric-1",
            space_id=1,
            space_name="space-1",
        )
