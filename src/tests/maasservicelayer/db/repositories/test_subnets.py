# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from ipaddress import IPv4Address, IPv4Network

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maascommon.enums.subnet import RdnsMode
from maasservicelayer.builders.subnets import SubnetBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.subnets import (
    SubnetClauseFactory,
    SubnetsRepository,
)
from maasservicelayer.exceptions.catalog import ValidationException
from maasservicelayer.models.subnets import Subnet
from tests.fixtures.factories.iprange import create_test_ip_range_entry
from tests.fixtures.factories.staticipaddress import (
    create_test_staticipaddress_entry,
)
from tests.fixtures.factories.subnet import create_test_subnet_entry
from tests.fixtures.factories.vlan import create_test_vlan_entry
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
    async def instance_builder_model(self) -> type[SubnetBuilder]:
        return SubnetBuilder

    @pytest.fixture
    async def instance_builder(self) -> SubnetBuilder:
        return SubnetBuilder(
            cidr=IPv4Network("10.10.10.1"),
            name="name",
            description="description",
            allow_dns=True,
            allow_proxy=True,
            rdns_mode=RdnsMode.DEFAULT,
            active_discovery=True,
            managed=True,
            disabled_boot_architectures=["ipxe"],
            gateway_ip=IPv4Address("10.0.0.1"),
            vlan_id=0,
        )

    @pytest.mark.skip(reason="Not implemented yet")
    async def test_delete_one(self, repository_instance, created_instance):
        pass

    @pytest.mark.skip(reason="Not implemented yet")
    async def test_delete_one_multiple_results(
        self, repository_instance, created_instance
    ):
        pass

    @pytest.mark.skip(reason="Not implemented yet")
    async def test_delete_by_id(self, repository_instance, created_instance):
        pass

    @pytest.mark.skip(reason="Not implemented yet")
    async def test_delete_many(self, repository_instance, created_instance):
        pass

    async def test_delete_checks_vlan_dhcp_on_dynamic_range(
        self, repository_instance: SubnetsRepository, fixture: Fixture
    ) -> None:
        vlan_with_dhcp_on = await create_test_vlan_entry(fixture, dhcp_on=True)
        subnet = await create_test_subnet_entry(
            fixture, vlan_id=vlan_with_dhcp_on["id"]
        )
        await create_test_ip_range_entry(
            fixture, subnet=subnet, type="dynamic"
        )
        query = QuerySpec(where=SubnetClauseFactory.with_id(subnet["id"]))
        with pytest.raises(ValidationException):
            await repository_instance.delete_one(query)

    async def test_delete_checks_vlan_dhcp_on_reserved_range(
        self, repository_instance: SubnetsRepository, fixture: Fixture
    ) -> None:
        vlan_with_dhcp_on = await create_test_vlan_entry(fixture, dhcp_on=True)
        subnet = await create_test_subnet_entry(
            fixture, vlan_id=vlan_with_dhcp_on["id"]
        )
        await create_test_ip_range_entry(
            fixture, subnet=subnet, type="reserved"
        )
        query = QuerySpec(where=SubnetClauseFactory.with_id(subnet["id"]))
        await repository_instance.delete_one(query)

    async def test_delete_checks_vlan_dhcp_off_dynamic_range(
        self, repository_instance: SubnetsRepository, fixture: Fixture
    ) -> None:
        vlan_with_dhcp_off = await create_test_vlan_entry(
            fixture, dhcp_on=False
        )
        subnet = await create_test_subnet_entry(
            fixture, vlan_id=vlan_with_dhcp_off["id"]
        )
        await create_test_ip_range_entry(
            fixture, subnet=subnet, type="dynamic"
        )
        query = QuerySpec(where=SubnetClauseFactory.with_id(subnet["id"]))
        await repository_instance.delete_one(query)


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
