# Copyright 2024-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from ipaddress import IPv4Address
from unittest.mock import Mock

import pytest

from maascommon.enums.interface import InterfaceType
from maascommon.enums.ipaddress import IpAddressFamily, IpAddressType
from maascommon.workflows.dhcp import (
    CONFIGURE_DHCP_WORKFLOW_NAME,
    merge_configure_dhcp_param,
)
from maasservicelayer.builders.staticipaddress import StaticIPAddressBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.dnsresources import DNSResourceRepository
from maasservicelayer.db.repositories.staticipaddress import (
    StaticIPAddressRepository,
)
from maasservicelayer.models.base import MaasBaseModel
from maasservicelayer.models.dnsresources import DNSResource
from maasservicelayer.models.interfaces import Interface
from maasservicelayer.models.staticipaddress import StaticIPAddress
from maasservicelayer.models.subnets import Subnet
from maasservicelayer.services.base import BaseService
from maasservicelayer.services.staticipaddress import StaticIPAddressService
from maasservicelayer.services.temporal import TemporalService
from maasservicelayer.utils.date import utcnow
from maastemporalworker.workflow.dhcp import ConfigureDHCPParam
from tests.fixtures.factories.dnsdata import create_test_dnsdata_entry
from tests.fixtures.factories.dnsresource import create_test_dnsresource_entry
from tests.fixtures.factories.domain import create_test_domain_entry
from tests.fixtures.factories.staticipaddress import (
    create_test_staticipaddress_entry,
)
from tests.fixtures.factories.subnet import create_test_subnet_entry
from tests.maasservicelayer.services.base import ServiceCommonTests


@pytest.mark.asyncio
class TestCommonStaticIPAddressService(ServiceCommonTests):
    @pytest.fixture
    def service_instance(self) -> BaseService:
        return StaticIPAddressService(
            context=Context(),
            temporal_service=Mock(TemporalService),
            dnsresource_repository=Mock(DNSResourceRepository),
            staticipaddress_repository=Mock(StaticIPAddressRepository),
        )

    @pytest.fixture
    def test_instance(self) -> MaasBaseModel:
        now = utcnow()
        return StaticIPAddress(
            id=1,
            ip=IPv4Address("10.0.0.1"),
            alloc_type=IpAddressType.DISCOVERED,
            lease_time=30,
            temp_expires_on=now,
            subnet_id=1,
            created=now,
            updated=now,
        )

    @pytest.mark.skip(reason="custom update many")
    async def test_update_many(
        self, service_instance, test_instance: MaasBaseModel
    ):
        pass

    async def test_delete_many(
        self, service_instance, test_instance: MaasBaseModel
    ):
        with pytest.raises(NotImplementedError):
            await super().test_delete_many(service_instance, test_instance)


@pytest.mark.asyncio
class TestStaticIPAddressService:
    async def test_create_or_update(self) -> None:
        now = utcnow()
        subnet = Subnet(
            id=1,
            cidr="10.0.0.0/24",
            allow_dns=True,
            allow_proxy=True,
            disabled_boot_architectures=[],
            rdns_mode=1,
            active_discovery=True,
            managed=True,
            vlan_id=1,
            created=now,
            updated=now,
        )
        existing_ip_address = StaticIPAddress(
            id=1,
            ip=IPv4Address("10.0.0.1"),
            alloc_type=IpAddressType.DISCOVERED,
            lease_time=30,
            temp_expires_on=now,
            subnet_id=1,
            created=now,
            updated=now,
        )

        repository_mock = Mock(StaticIPAddressRepository)
        repository_mock.create_or_update.return_value = existing_ip_address

        mock_temporal = Mock(TemporalService)

        staticipaddress_service = StaticIPAddressService(
            context=Context(),
            temporal_service=mock_temporal,
            dnsresource_repository=Mock(DNSResourceRepository),
            staticipaddress_repository=repository_mock,
        )

        builder = StaticIPAddressBuilder(
            ip="10.0.0.2",
            lease_time=30,
            alloc_type=IpAddressType.DISCOVERED,
            subnet_id=subnet.id,
        )
        await staticipaddress_service.create_or_update(builder)

        repository_mock.create_or_update.assert_called_once_with(builder)

    async def test_create_or_update_registers_configure_dhcp(self):
        now = utcnow()
        subnet = Subnet(
            id=1,
            cidr="10.0.0.0/24",
            allow_dns=True,
            allow_proxy=True,
            disabled_boot_architectures=[],
            rdns_mode=1,
            active_discovery=True,
            managed=True,
            vlan_id=1,
            created=now,
            updated=now,
        )
        sip = StaticIPAddress(
            id=2,
            ip="10.0.0.2",
            lease_time=30,
            subnet_id=subnet.id,
            alloc_type=IpAddressType.AUTO,
            created=now,
            updated=now,
        )

        mock_staticipaddress_repository = Mock(StaticIPAddressRepository)
        mock_staticipaddress_repository.create_or_update.return_value = sip

        mock_temporal = Mock(TemporalService)

        staticipaddress_service = StaticIPAddressService(
            context=Context(),
            temporal_service=mock_temporal,
            dnsresource_repository=Mock(DNSResourceRepository),
            staticipaddress_repository=mock_staticipaddress_repository,
        )

        builder = StaticIPAddressBuilder(
            ip=sip.ip,
            lease_time=sip.lease_time,
            alloc_type=sip.alloc_type,
            subnet_id=sip.subnet_id,
        )
        await staticipaddress_service.create_or_update(builder)

        mock_staticipaddress_repository.create_or_update.assert_called_once_with(
            builder
        )
        mock_temporal.register_or_update_workflow_call.assert_called_once_with(
            CONFIGURE_DHCP_WORKFLOW_NAME,
            ConfigureDHCPParam(
                static_ip_addr_ids=[sip.id],
            ),
            parameter_merge_func=merge_configure_dhcp_param,
            wait=False,
        )

    async def test_get_discovered_ips_in_family_for_interfaces(self) -> None:
        now = utcnow()
        interface = Interface(
            id=1,
            name="eth0",
            type=InterfaceType.PHYSICAL,
            mac="00:11:22:33:44:55",
            created=now,
            updated=now,
        )

        repository_mock = Mock(StaticIPAddressRepository)

        mock_temporal = Mock(TemporalService)

        staticipaddress_service = StaticIPAddressService(
            context=Context(),
            temporal_service=mock_temporal,
            dnsresource_repository=Mock(DNSResourceRepository),
            staticipaddress_repository=repository_mock,
        )

        await staticipaddress_service.get_discovered_ips_in_family_for_interfaces(
            [interface]
        )

        repository_mock.get_discovered_ips_in_family_for_interfaces.assert_called_once_with(
            [interface], family=IpAddressFamily.IPV4
        )

    async def test_create(self) -> None:
        now = utcnow()
        subnet = Subnet(
            id=1,
            cidr="10.0.0.0/24",
            allow_dns=True,
            allow_proxy=True,
            disabled_boot_architectures=[],
            rdns_mode=1,
            active_discovery=True,
            vlan_id=1,
            managed=True,
            created=now,
            updated=now,
        )
        sip = StaticIPAddress(
            id=2,
            ip="10.0.0.2",
            lease_time=30,
            subnet_id=subnet.id,
            alloc_type=IpAddressType.AUTO,
            created=now,
            updated=now,
        )

        mock_staticipaddress_repository = Mock(StaticIPAddressRepository)
        mock_staticipaddress_repository.create.return_value = sip

        mock_temporal = Mock(TemporalService)

        staticipaddress_service = StaticIPAddressService(
            context=Context(),
            dnsresource_repository=Mock(DNSResourceRepository),
            temporal_service=mock_temporal,
            staticipaddress_repository=mock_staticipaddress_repository,
        )

        builder = StaticIPAddressBuilder(
            ip=sip.ip,
            lease_time=sip.lease_time,
            alloc_type=sip.alloc_type,
            subnet_id=sip.subnet_id,
        )
        await staticipaddress_service.create(builder)

        mock_staticipaddress_repository.create.assert_called_once_with(
            builder=builder
        )
        mock_temporal.register_or_update_workflow_call.assert_called_once_with(
            CONFIGURE_DHCP_WORKFLOW_NAME,
            ConfigureDHCPParam(
                static_ip_addr_ids=[sip.id],
            ),
            parameter_merge_func=merge_configure_dhcp_param,
            wait=False,
        )

    async def test_update(self) -> None:
        now = utcnow()
        subnet = Subnet(
            id=1,
            cidr="10.0.0.0/24",
            allow_dns=True,
            allow_proxy=True,
            disabled_boot_architectures=[],
            rdns_mode=1,
            active_discovery=True,
            managed=True,
            vlan_id=1,
            created=now,
            updated=now,
        )
        sip = StaticIPAddress(
            id=2,
            ip="10.0.0.2",
            lease_time=30,
            subnet_id=subnet.id,
            alloc_type=IpAddressType.AUTO,
            created=now,
            updated=now,
        )

        mock_staticipaddress_repository = Mock(StaticIPAddressRepository)
        mock_staticipaddress_repository.get_by_id.return_value = sip
        mock_staticipaddress_repository.update_by_id.return_value = sip

        mock_temporal = Mock(TemporalService)

        staticipaddress_service = StaticIPAddressService(
            dnsresource_repository=Mock(DNSResourceRepository),
            context=Context(),
            temporal_service=mock_temporal,
            staticipaddress_repository=mock_staticipaddress_repository,
        )

        builder = StaticIPAddressBuilder(
            ip=sip.ip,
            lease_time=sip.lease_time,
            alloc_type=sip.alloc_type,
            subnet_id=sip.subnet_id,
        )
        await staticipaddress_service.update_by_id(
            sip.id,
            builder,
        )

        mock_staticipaddress_repository.update_by_id.assert_called_once_with(
            id=sip.id,
            builder=builder,
        )
        mock_temporal.register_or_update_workflow_call.assert_called_once_with(
            CONFIGURE_DHCP_WORKFLOW_NAME,
            ConfigureDHCPParam(
                static_ip_addr_ids=[sip.id],
            ),
            parameter_merge_func=merge_configure_dhcp_param,
            wait=False,
        )

    @pytest.mark.parametrize(
        "builder, should_raise",
        [
            (StaticIPAddressBuilder(subnet_id=10), True),
            (StaticIPAddressBuilder(user_id=10), False),
        ],
    )
    async def test_update_many(
        self, builder: StaticIPAddressBuilder, should_raise: bool
    ) -> None:
        now = utcnow()
        ips = [
            StaticIPAddress(
                id=i,
                ip=f"10.0.0.{i}",
                lease_time=30,
                subnet_id=1,
                alloc_type=IpAddressType.AUTO,
                created=now,
                updated=now,
            )
            for i in range(2)
        ]

        mock_staticipaddress_repository = Mock(StaticIPAddressRepository)
        mock_staticipaddress_repository.update_many.return_value = ips

        mock_temporal = Mock(TemporalService)

        staticipaddress_service = StaticIPAddressService(
            dnsresource_repository=Mock(DNSResourceRepository),
            context=Context(),
            temporal_service=mock_temporal,
            staticipaddress_repository=mock_staticipaddress_repository,
        )

        if should_raise:
            with pytest.raises(NotImplementedError):
                await staticipaddress_service.update_many(QuerySpec(), builder)
        else:
            await staticipaddress_service.update_many(QuerySpec(), builder)

        mock_staticipaddress_repository.update_many.assert_called_once_with(
            query=QuerySpec(),
            builder=builder,
        )
        mock_temporal.register_or_update_workflow_call.assert_not_called()

    async def test_delete(self) -> None:
        now = utcnow()
        subnet = Subnet(
            id=1,
            cidr="10.0.0.0/24",
            allow_dns=True,
            allow_proxy=True,
            disabled_boot_architectures=[],
            rdns_mode=1,
            active_discovery=True,
            managed=True,
            vlan_id=1,
            created=now,
            updated=now,
        )
        sip = StaticIPAddress(
            id=2,
            ip="10.0.0.2",
            lease_time=30,
            subnet_id=subnet.id,
            alloc_type=IpAddressType.AUTO,
            created=now,
            updated=now,
        )

        mock_staticipaddress_repository = Mock(StaticIPAddressRepository)
        mock_staticipaddress_repository.get_by_id.return_value = sip
        mock_staticipaddress_repository.delete_by_id.return_value = sip
        mock_dnsresource_repository = Mock(DNSResourceRepository)
        mock_dnsresource_repository.get_dnsresources_for_ip.return_value = []

        mock_temporal = Mock(TemporalService)

        staticipaddress_service = StaticIPAddressService(
            context=Context(),
            temporal_service=mock_temporal,
            dnsresource_repository=mock_dnsresource_repository,
            staticipaddress_repository=mock_staticipaddress_repository,
        )

        await staticipaddress_service.delete_by_id(
            id=sip.id,
        )

        mock_staticipaddress_repository.delete_by_id.assert_called_once_with(
            id=sip.id,
        )
        mock_staticipaddress_repository.unlink_from_interfaces.assert_called_once_with(
            staticipaddress_id=sip.id
        )
        mock_dnsresource_repository.unlink_ip_from_all_dnsresources.assert_called_once_with(
            staticipaddress_id=sip.id
        )
        mock_temporal.register_or_update_workflow_call.assert_called_once_with(
            CONFIGURE_DHCP_WORKFLOW_NAME,
            ConfigureDHCPParam(
                subnet_ids=[sip.subnet_id],
            ),
            parameter_merge_func=merge_configure_dhcp_param,
            wait=False,
        )

    async def test_delete_cleans_up_orphaned_dns_resource(self) -> None:
        """Test that orphaned DNS resources are deleted when an IP is deleted."""
        now = utcnow()
        sip = StaticIPAddress(
            id=2,
            ip="10.0.0.2",
            lease_time=30,
            subnet_id=1,
            alloc_type=IpAddressType.AUTO,
            created=now,
            updated=now,
        )

        # DNS resource that will become orphaned
        dnsresource = DNSResource(
            id=1,
            name="test-host",
            domain_id=1,
            created=now,
            updated=now,
        )

        mock_staticipaddress_repository = Mock(StaticIPAddressRepository)
        mock_staticipaddress_repository.get_by_id.return_value = sip
        mock_staticipaddress_repository.delete_by_id.return_value = sip

        mock_dnsresource_repository = Mock(DNSResourceRepository)
        mock_dnsresource_repository.get_dnsresources_for_ip.return_value = [
            dnsresource
        ]
        mock_dnsresource_repository.get_dnsresources_without_ips.return_value = [
            dnsresource.id
        ]
        mock_dnsresource_repository.get_dnsresources_without_dnsdata.return_value = [
            dnsresource.id
        ]
        mock_dnsresource_repository.delete_many_by_ids.return_value = [
            dnsresource
        ]

        mock_temporal = Mock(TemporalService)

        staticipaddress_service = StaticIPAddressService(
            context=Context(),
            temporal_service=mock_temporal,
            dnsresource_repository=mock_dnsresource_repository,
            staticipaddress_repository=mock_staticipaddress_repository,
        )

        await staticipaddress_service.delete_by_id(id=sip.id)

        # Verify DNS resource was deleted using batch operations
        mock_dnsresource_repository.get_dnsresources_for_ip.assert_called_once_with(
            sip
        )
        mock_dnsresource_repository.get_dnsresources_without_ips.assert_called_once_with(
            [dnsresource.id]
        )
        mock_dnsresource_repository.get_dnsresources_without_dnsdata.assert_called_once_with(
            [dnsresource.id]
        )
        mock_dnsresource_repository.delete_many_by_ids.assert_called_once_with(
            [dnsresource.id]
        )

    async def test_delete_keeps_dns_resource_with_remaining_ips(self) -> None:
        """Test that DNS resources with other IPs are kept when an IP is deleted."""
        now = utcnow()
        sip = StaticIPAddress(
            id=2,
            ip="10.0.0.2",
            lease_time=30,
            subnet_id=1,
            alloc_type=IpAddressType.AUTO,
            created=now,
            updated=now,
        )

        # DNS resource that has other IPs
        dnsresource = DNSResource(
            id=1,
            name="test-host",
            domain_id=1,
            created=now,
            updated=now,
        )

        mock_staticipaddress_repository = Mock(StaticIPAddressRepository)
        mock_staticipaddress_repository.get_by_id.return_value = sip
        mock_staticipaddress_repository.delete_by_id.return_value = sip

        mock_dnsresource_repository = Mock(DNSResourceRepository)
        mock_dnsresource_repository.get_dnsresources_for_ip.return_value = [
            dnsresource
        ]
        mock_dnsresource_repository.get_dnsresources_without_ips.return_value = []

        mock_temporal = Mock(TemporalService)

        staticipaddress_service = StaticIPAddressService(
            context=Context(),
            temporal_service=mock_temporal,
            dnsresource_repository=mock_dnsresource_repository,
            staticipaddress_repository=mock_staticipaddress_repository,
        )

        await staticipaddress_service.delete_by_id(id=sip.id)

        # Verify DNS resource was NOT deleted (has remaining IPs)
        mock_dnsresource_repository.get_dnsresources_without_ips.assert_called_once_with(
            [dnsresource.id]
        )
        mock_dnsresource_repository.get_dnsresources_without_dnsdata.assert_not_called()
        mock_dnsresource_repository.delete_many_by_ids.assert_not_called()

    async def test_delete_keeps_dns_resource_with_dnsdata(self) -> None:
        """Test that DNS resources with DNS data are kept even without IPs."""
        now = utcnow()
        sip = StaticIPAddress(
            id=2,
            ip="10.0.0.2",
            lease_time=30,
            subnet_id=1,
            alloc_type=IpAddressType.AUTO,
            created=now,
            updated=now,
        )

        dnsresource = DNSResource(
            id=1,
            name="test-host",
            domain_id=1,
            created=now,
            updated=now,
        )

        mock_staticipaddress_repository = Mock(StaticIPAddressRepository)
        mock_staticipaddress_repository.get_by_id.return_value = sip
        mock_staticipaddress_repository.delete_by_id.return_value = sip

        mock_dnsresource_repository = Mock(DNSResourceRepository)
        mock_dnsresource_repository.get_dnsresources_for_ip.return_value = [
            dnsresource
        ]
        mock_dnsresource_repository.get_dnsresources_without_ips.return_value = [
            dnsresource.id
        ]
        mock_dnsresource_repository.get_dnsresources_without_dnsdata.return_value = []

        mock_temporal = Mock(TemporalService)

        staticipaddress_service = StaticIPAddressService(
            context=Context(),
            temporal_service=mock_temporal,
            dnsresource_repository=mock_dnsresource_repository,
            staticipaddress_repository=mock_staticipaddress_repository,
        )

        await staticipaddress_service.delete_by_id(id=sip.id)

        # Verify DNS resource was NOT deleted because it has DNS data
        mock_dnsresource_repository.get_dnsresources_without_ips.assert_called_once_with(
            [dnsresource.id]
        )
        mock_dnsresource_repository.get_dnsresources_without_dnsdata.assert_called_once_with(
            [dnsresource.id]
        )
        mock_dnsresource_repository.delete_many_by_ids.assert_not_called()


@pytest.mark.asyncio
class TestStaticIPAddressServiceIntegration:
    async def test_delete_ip_cleans_up_orphaned_dns_resource_integration(
        self, services, fixture
    ):
        """Test that deleting an IP address deletes orphaned DNS resources."""
        domain = await create_test_domain_entry(fixture, name="test.maas")
        subnet = await create_test_subnet_entry(fixture, cidr="10.0.0.0/24")
        sip = (
            await create_test_staticipaddress_entry(
                fixture, subnet=subnet, alloc_type=IpAddressType.AUTO
            )
        )[0]

        # Create DNS resource linked to this IP only
        dnsresource = await create_test_dnsresource_entry(
            fixture, domain, sip, name="test-host"
        )

        # Verify setup: DNS resource exists and is linked to the IP
        dnsrr_before = await services.dnsresources.get_by_id(dnsresource.id)
        assert dnsrr_before is not None
        ips_before = await services.dnsresources.get_ips_for_dnsresource(
            dnsresource.id
        )
        assert len(ips_before) == 1
        assert ips_before[0].id == sip["id"]

        await services.staticipaddress.delete_by_id(sip["id"])

        # Verify the DNS resource was deleted because it became orphaned
        dnsrr_after = await services.dnsresources.get_by_id(dnsresource.id)
        assert dnsrr_after is None

    async def test_delete_ip_keeps_dns_resource_with_other_ips_integration(
        self, services, fixture
    ):
        """Test that DNS resource with other IPs is not deleted."""
        domain = await create_test_domain_entry(fixture, name="test.maas")
        subnet = await create_test_subnet_entry(fixture, cidr="10.0.0.0/24")

        sip1 = (
            await create_test_staticipaddress_entry(
                fixture, subnet=subnet, alloc_type=IpAddressType.AUTO
            )
        )[0]
        sip2 = (
            await create_test_staticipaddress_entry(
                fixture, subnet=subnet, alloc_type=IpAddressType.AUTO
            )
        )[0]

        # Create DNS resource linked to first IP
        dnsresource = await create_test_dnsresource_entry(
            fixture, domain, sip1, name="test-host"
        )

        # Link second IP to the same DNS resource
        await services.dnsresources.link_ip(dnsresource.id, sip2["id"])

        ips_before = await services.dnsresources.get_ips_for_dnsresource(
            dnsresource.id
        )
        assert len(ips_before) == 2

        await services.staticipaddress.delete_by_id(sip1["id"])

        # Verify the DNS resource still exists (has other IP)
        dnsrr_after = await services.dnsresources.get_by_id(dnsresource.id)
        assert dnsrr_after is not None

        ips_after = await services.dnsresources.get_ips_for_dnsresource(
            dnsresource.id
        )
        assert len(ips_after) == 1
        assert ips_after[0].id == sip2["id"]

    async def test_delete_ip_keeps_dns_resource_with_dnsdata_integration(
        self, services, fixture
    ):
        """Test that DNS resource with DNS data records is not deleted."""
        domain = await create_test_domain_entry(fixture, name="test.maas")
        subnet = await create_test_subnet_entry(fixture, cidr="10.0.0.0/24")
        sip = (
            await create_test_staticipaddress_entry(
                fixture, subnet=subnet, alloc_type=IpAddressType.AUTO
            )
        )[0]

        # Create DNS resource linked to this IP
        dnsresource = await create_test_dnsresource_entry(
            fixture, domain, sip, name="test-host"
        )

        # Add DNS data (e.g., CNAME record) to the DNS resource
        await create_test_dnsdata_entry(
            fixture,
            dnsresource,
            rrtype="CNAME",
            rrdata="other-host.test.maas.",
        )

        dnsdata_before = (
            await services.dnsresources.get_dnsdata_for_dnsresource(
                dnsresource.id
            )
        )
        assert len(dnsdata_before) == 1

        await services.staticipaddress.delete_by_id(sip["id"])

        # Verify the DNS resource was NOT deleted (has DNS data)
        dnsrr_after = await services.dnsresources.get_by_id(dnsresource.id)
        assert dnsrr_after is not None

        ips_after = await services.dnsresources.get_ips_for_dnsresource(
            dnsresource.id
        )
        assert len(ips_after) == 0

        # But DNS data still exists
        dnsdata_after = (
            await services.dnsresources.get_dnsdata_for_dnsresource(
                dnsresource.id
            )
        )
        assert len(dnsdata_after) == 1

    async def test_delete_ip_cleans_multiple_dns_resources_integration(
        self, services, fixture
    ):
        """Test that deleting an IP cleans up multiple orphaned DNS resources."""
        domain1 = await create_test_domain_entry(fixture, name="domain1.maas")
        domain2 = await create_test_domain_entry(fixture, name="domain2.maas")
        subnet = await create_test_subnet_entry(fixture, cidr="10.0.0.0/24")
        sip = (
            await create_test_staticipaddress_entry(
                fixture, subnet=subnet, alloc_type=IpAddressType.AUTO
            )
        )[0]

        # Create two DNS resources in different domains, both linked to the same IP
        dnsresource1 = await create_test_dnsresource_entry(
            fixture, domain1, sip, name="host1"
        )
        dnsresource2 = await create_test_dnsresource_entry(
            fixture, domain2, sip, name="host2"
        )

        dnsrr1_before = await services.dnsresources.get_by_id(dnsresource1.id)
        dnsrr2_before = await services.dnsresources.get_by_id(dnsresource2.id)
        assert dnsrr1_before is not None
        assert dnsrr2_before is not None

        await services.staticipaddress.delete_by_id(sip["id"])

        # Verify both DNS resources were deleted (both became orphaned)
        dnsrr1_after = await services.dnsresources.get_by_id(dnsresource1.id)
        dnsrr2_after = await services.dnsresources.get_by_id(dnsresource2.id)
        assert dnsrr1_after is None
        assert dnsrr2_after is None

    async def test_delete_ip_partial_cleanup_integration(
        self, services, fixture
    ):
        """Test mixed scenario: one DNS resource is deleted, another is kept."""
        domain = await create_test_domain_entry(fixture, name="test.maas")
        subnet = await create_test_subnet_entry(fixture, cidr="10.0.0.0/24")

        sip1 = (
            await create_test_staticipaddress_entry(
                fixture, subnet=subnet, alloc_type=IpAddressType.AUTO
            )
        )[0]
        sip2 = (
            await create_test_staticipaddress_entry(
                fixture, subnet=subnet, alloc_type=IpAddressType.AUTO
            )
        )[0]

        # Resource 1: linked to sip1 only (will be orphaned)
        dnsresource1 = await create_test_dnsresource_entry(
            fixture, domain, sip1, name="host1"
        )
        # Resource 2: linked to both IPs (will keep sip2)
        dnsresource2 = await create_test_dnsresource_entry(
            fixture, domain, sip1, name="host2"
        )
        await services.dnsresources.link_ip(dnsresource2.id, sip2["id"])

        await services.staticipaddress.delete_by_id(sip1["id"])

        # Verify dnsresource1 was deleted (orphaned)
        dnsrr1_after = await services.dnsresources.get_by_id(dnsresource1.id)
        assert dnsrr1_after is None

        # Verify dnsresource2 still exists (has sip2)
        dnsrr2_after = await services.dnsresources.get_by_id(dnsresource2.id)
        assert dnsrr2_after is not None
        ips_after = await services.dnsresources.get_ips_for_dnsresource(
            dnsresource2.id
        )
        assert len(ips_after) == 1
        assert ips_after[0].id == sip2["id"]
