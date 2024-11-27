# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from ipaddress import IPv4Address, IPv4Network

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maascommon.bootmethods import BOOT_METHODS_METADATA
from maascommon.enums.subnet import RdnsMode
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.subnets import (
    SubnetClauseFactory,
    SubnetResourceBuilder,
    SubnetsRepository,
)
from maasservicelayer.exceptions.catalog import ValidationException
from maasservicelayer.models.subnets import Subnet
from maasservicelayer.utils.date import utcnow
from tests.fixtures.factories.staticipaddress import (
    create_test_staticipaddress_entry,
)
from tests.fixtures.factories.subnet import create_test_subnet_entry
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasservicelayer.db.repositories.base import RepositoryCommonTests


class TestSubnetClauseFactory:
    def test_builder(self) -> None:
        clause = SubnetClauseFactory.with_id(id=1)
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == ("maasserver_subnet.id = 1")
        clause = SubnetClauseFactory.with_vlan_id(vlan_id=1)
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == ("maasserver_subnet.vlan_id = 1")
        clause = SubnetClauseFactory.with_fabric_id(fabric_id=1)
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == ("maasserver_vlan.fabric_id = 1")
        assert str(
            clause.joins[0].compile(compile_kwargs={"literal_binds": True})
        ) == (
            "maasserver_subnet JOIN maasserver_vlan ON maasserver_subnet.vlan_id = maasserver_vlan.id"
        )


class TestSubnetResourceBuilder:
    def test_builder(self) -> None:
        now = utcnow()
        net = IPv4Network("10.0.0.0/24", strict=False)
        resource = (
            SubnetResourceBuilder()
            .with_cidr(net)
            .with_name("name")
            .with_description("description")
            .with_allow_dns(True)
            .with_allow_proxy(True)
            .with_rdns_mode(RdnsMode.DEFAULT)
            .with_active_discovery(True)
            .with_managed(True)
            .with_disabled_boot_architectures(["ipxe"])
            .with_vlan_id(0)
            .with_created(now)
            .with_updated(now)
            .build()
        )

        assert resource.get_values() == {
            "cidr": net,
            "name": "name",
            "description": "description",
            "allow_dns": True,
            "allow_proxy": True,
            "rdns_mode": RdnsMode.DEFAULT,
            "active_discovery": True,
            "managed": True,
            "disabled_boot_architectures": ["ipxe"],
            "vlan_id": 0,
            "created": now,
            "updated": now,
        }

    @pytest.mark.parametrize(
        "arch, is_valid,",
        [
            *[
                (method.arch_octet, True)
                for method in BOOT_METHODS_METADATA
                if method.arch_octet is not None
            ],
            *[
                (method.name, True)
                for method in BOOT_METHODS_METADATA
                if method.name not in [None, "windows"]
            ],
            ("test", False),
        ],
    )
    def test_disabled_boot_architectures(
        self, arch: str, is_valid: bool
    ) -> None:
        if is_valid:
            SubnetResourceBuilder().with_disabled_boot_architectures([arch])
        else:
            with pytest.raises(ValidationException):
                SubnetResourceBuilder().with_disabled_boot_architectures(
                    [arch]
                )


class TestSubnetsRepository(RepositoryCommonTests[Subnet]):
    @pytest.fixture
    def repository_instance(
        self, db_connection: AsyncConnection
    ) -> SubnetsRepository:
        return SubnetsRepository(Context(connection=db_connection))

    @pytest.fixture
    async def _setup_test_list(
        self, fixture: Fixture, num_objects: int
    ) -> list[Subnet]:
        created_subnets = [
            Subnet(
                **(
                    await create_test_subnet_entry(
                        fixture, name=str(i), description=str(i)
                    )
                )
            )
            for i in range(num_objects)
        ]
        return created_subnets

    @pytest.fixture
    async def created_instance(self, fixture: Fixture) -> Subnet:
        return Subnet(
            **(
                await create_test_subnet_entry(
                    fixture, name="name", description="description"
                )
            )
        )

    @pytest.fixture
    async def instance_builder(self) -> SubnetResourceBuilder:
        return (
            SubnetResourceBuilder()
            .with_cidr(IPv4Network("10.10.10.1"))
            .with_name("name")
            .with_description("description")
            .with_allow_dns(True)
            .with_allow_proxy(True)
            .with_rdns_mode(RdnsMode.DEFAULT)
            .with_active_discovery(True)
            .with_managed(True)
            .with_disabled_boot_architectures(["ipxe"])
            .with_gateway_ip(IPv4Address("10.0.0.1"))
            .with_vlan_id(0)
        )


@pytest.mark.usefixtures("ensuremaasdb")
@pytest.mark.asyncio
class TestSubnetsRepositoryMethods:
    async def test_find_best_subnet_for_ip(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        await create_test_subnet_entry(fixture, cidr="10.0.0.0/25")
        subnet2 = await create_test_subnet_entry(fixture, cidr="10.0.1.0/24")

        ip = await create_test_staticipaddress_entry(fixture, ip="10.0.1.2")

        subnets = SubnetsRepository(Context(connection=db_connection))

        result = await subnets.find_best_subnet_for_ip(str(ip[0]["ip"]))
        assert result is not None
        assert result.id == subnet2["id"]
