# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import timezone
from ipaddress import IPv4Network

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.context import Context
from maasservicelayer.db.repositories.subnets import (
    SubnetResourceBuilder,
    SubnetsRepository,
)
from maasservicelayer.exceptions.catalog import AlreadyExistsException
from maasservicelayer.models.subnets import Subnet
from maasservicelayer.utils.date import utcnow
from tests.fixtures.factories.staticipaddress import (
    create_test_staticipaddress_entry,
)
from tests.fixtures.factories.subnet import create_test_subnet_entry
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasservicelayer.db.repositories.base import RepositoryCommonTests


class TestSubnetResourceBuilder:
    def test_builder(self) -> None:
        now = utcnow()
        resource = (
            SubnetResourceBuilder()
            .with_cidr("10.0.0.1/24")
            .with_name("name")
            .with_description("description")
            .with_allow_dns(True)
            .with_allow_proxy(True)
            .with_rdns_mode(0)
            .with_active_discovery(True)
            .with_managed(True)
            .with_disabled_boot_architectures(["amd64"])
            .with_vlan_id(0)
            .with_created(now)
            .with_updated(now)
            .build()
        )

        assert resource.get_values() == {
            "cidr": "10.0.0.1/24",
            "name": "name",
            "description": "description",
            "allow_dns": True,
            "allow_proxy": True,
            "rdns_mode": 0,
            "active_discovery": True,
            "managed": True,
            "disabled_boot_architectures": ["amd64"],
            "vlan_id": 0,
            "created": now,
            "updated": now,
        }


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
    async def _created_instance(self, fixture: Fixture) -> Subnet:
        return Subnet(
            **(
                await create_test_subnet_entry(
                    fixture, name="name", description="description"
                )
            )
        )

    async def test_create(
        self, repository_instance: SubnetsRepository
    ) -> None:
        now = utcnow()
        created_subnet = await repository_instance.create(
            SubnetResourceBuilder()
            .with_cidr(IPv4Network("10.0.0.1"))
            .with_name("name")
            .with_description("description")
            .with_allow_dns(True)
            .with_allow_proxy(True)
            .with_rdns_mode(0)
            .with_active_discovery(True)
            .with_managed(True)
            .with_disabled_boot_architectures(["ipxe"])
            .with_vlan_id(0)
            .with_created(now)
            .with_updated(now)
            .build()
        )
        assert created_subnet.id > 1
        assert created_subnet.cidr == IPv4Network("10.0.0.1")
        assert created_subnet.name == "name"
        assert created_subnet.description == "description"
        assert created_subnet.allow_dns is True
        assert created_subnet.allow_proxy is True
        assert created_subnet.rdns_mode == 0
        assert created_subnet.active_discovery is True
        assert created_subnet.managed is True
        assert created_subnet.disabled_boot_architectures == ["ipxe"]
        assert created_subnet.created.astimezone(
            timezone.utc
        ) >= now.astimezone(timezone.utc)
        assert created_subnet.updated.astimezone(
            timezone.utc
        ) >= now.astimezone(timezone.utc)

    async def test_create_duplicated(
        self, repository_instance: SubnetsRepository, _created_instance: Subnet
    ) -> None:
        now = utcnow()
        with pytest.raises(AlreadyExistsException):
            await repository_instance.create(
                SubnetResourceBuilder()
                .with_cidr(_created_instance.cidr)
                .with_name(_created_instance.name)
                .with_description(_created_instance.description)
                .with_allow_dns(_created_instance.allow_dns)
                .with_allow_proxy(_created_instance.allow_proxy)
                .with_rdns_mode(_created_instance.rdns_mode)
                .with_active_discovery(_created_instance.active_discovery)
                .with_managed(_created_instance.managed)
                .with_disabled_boot_architectures(
                    _created_instance.disabled_boot_architectures
                )
                .with_vlan_id(0)
                .with_created(now)
                .with_updated(now)
                .build()
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
