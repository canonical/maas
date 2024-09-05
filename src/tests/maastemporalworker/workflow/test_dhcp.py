import pytest
from sqlalchemy.ext.asyncio import AsyncConnection
from temporalio.testing import ActivityEnvironment

from maasservicelayer.db import Database
from maastemporalworker.workflow.dhcp import (
    ConfigureDHCPParam,
    DHCPConfigActivity,
    FetchHostsForUpdateParam,
    Host,
)
from tests.fixtures.factories.interface import create_test_interface_entry
from tests.fixtures.factories.iprange import create_test_ip_range_entry
from tests.fixtures.factories.node import (
    create_test_machine_entry,
    create_test_rack_controller_entry,
)
from tests.fixtures.factories.reserved_ips import create_test_reserved_ip_entry
from tests.fixtures.factories.secret import create_test_secret
from tests.fixtures.factories.staticipaddress import (
    create_test_staticipaddress_entry,
)
from tests.fixtures.factories.subnet import create_test_subnet_entry
from tests.fixtures.factories.vlan import create_test_vlan_entry
from tests.maasapiserver.fixtures.db import Fixture


@pytest.mark.asyncio
class TestDHCPConfigActivity:
    async def test_get_agents_for_vlans(
        self, fixture: Fixture, db_connection: AsyncConnection, db: Database
    ) -> None:
        rack_controller1 = await create_test_rack_controller_entry(fixture)
        rack_controller2 = await create_test_rack_controller_entry(fixture)
        rack_controller3 = await create_test_rack_controller_entry(fixture)

        vlan = await create_test_vlan_entry(
            fixture,
            primary_rack_id=rack_controller1["id"],
            secondary_rack_id=rack_controller2["id"],
            dhcp_on=True,
        )

        activities = DHCPConfigActivity(db, connection=db_connection)

        result = await activities._get_agents_for_vlans(
            db_connection, {vlan["id"]}
        )

        assert rack_controller3["system_id"] not in result

        assert result == {
            rack_controller1["system_id"],
            rack_controller2["system_id"],
        }

    async def test_get_vlans_for_subnet(
        self, fixture: Fixture, db_connection: AsyncConnection, db: Database
    ) -> None:
        vlans = [
            await create_test_vlan_entry(fixture, dhcp_on=True)
            for _ in range(3)
        ]
        subnets = [
            await create_test_subnet_entry(fixture, vlan_id=vlan["id"])
            for vlan in vlans
            for _ in range(3)
        ]

        activities = DHCPConfigActivity(db, connection=db_connection)

        result = await activities._get_vlans_for_subnets(
            db_connection, [s["id"] for s in subnets]
        )
        assert result == {vlan["id"] for vlan in vlans}

    async def test_get_vlans_for_ip_ranges(
        self, fixture: Fixture, db_connection: AsyncConnection, db: Database
    ) -> None:
        vlans = [
            await create_test_vlan_entry(fixture, dhcp_on=True)
            for _ in range(3)
        ]
        subnets = [
            await create_test_subnet_entry(fixture, vlan_id=vlan["id"])
            for vlan in vlans
        ]
        ip_ranges = [
            await create_test_ip_range_entry(fixture, subnet=subnet)
            for subnet in subnets
        ]

        activities = DHCPConfigActivity(db, connection=db_connection)

        result = await activities._get_vlans_for_ip_ranges(
            db_connection, [ip_range["id"] for ip_range in ip_ranges]
        )
        assert result == {vlan["id"] for vlan in vlans}

    async def test_get_vlans_for_static_ip_addrs(
        self, fixture: Fixture, db_connection: AsyncConnection, db: Database
    ) -> None:
        vlans = [
            await create_test_vlan_entry(fixture, dhcp_on=True)
            for _ in range(3)
        ]
        subnets = [
            await create_test_subnet_entry(fixture, vlan_id=vlan["id"])
            for vlan in vlans
        ]
        ips = [
            (
                await create_test_staticipaddress_entry(
                    fixture, subnet_id=subnet["id"]
                )
            )[0]
            for subnet in subnets
            for _ in range(3)
        ]

        activities = DHCPConfigActivity(db, connection=db_connection)

        result = await activities._get_vlans_for_static_ip_addrs(
            db_connection, [ip["id"] for ip in ips]
        )
        assert result == {vlan["id"] for vlan in vlans}

    async def test_get_vlans_for_reserved_ips(
        self, fixture: Fixture, db_connection: AsyncConnection, db: Database
    ) -> None:
        vlans = [
            await create_test_vlan_entry(fixture, dhcp_on=True)
            for _ in range(3)
        ]
        subnets = [
            await create_test_subnet_entry(fixture, vlan_id=vlan["id"])
            for vlan in vlans
        ]
        reserved_ips = [
            await create_test_reserved_ip_entry(fixture, subnet=subnet)
            for subnet in subnets
        ]

        activities = DHCPConfigActivity(db, connection=db_connection)

        result = await activities._get_vlans_for_reserved_ips(
            db_connection, [ip["id"] for ip in reserved_ips]
        )
        assert result == {vlan["id"] for vlan in vlans}

    async def test_find_agents_for_update(
        self, fixture: Fixture, db_connection: AsyncConnection, db: Database
    ) -> None:
        env = ActivityEnvironment()

        rack_controller1 = await create_test_rack_controller_entry(fixture)
        rack_controller2 = await create_test_rack_controller_entry(fixture)
        rack_controller3 = await create_test_rack_controller_entry(fixture)

        vlan1 = await create_test_vlan_entry(
            fixture,
            primary_rack_id=rack_controller1["id"],
            dhcp_on=True,
        )
        vlan2 = await create_test_vlan_entry(
            fixture,
            primary_rack_id=rack_controller3["id"],
            dhcp_on=True,
        )

        subnet = await create_test_subnet_entry(fixture, vlan_id=vlan2["id"])

        activities = DHCPConfigActivity(db, connection=db_connection)

        result = await env.run(
            activities.find_agents_for_updates,
            ConfigureDHCPParam(
                system_ids=[rack_controller2["system_id"]],
                vlan_ids=[vlan1["id"]],
                subnet_ids=[subnet["id"]],
                static_ip_addr_ids=[],
                ip_range_ids=[],
                reserved_ip_ids=[],
            ),
        )

        for rc in [rack_controller1, rack_controller2, rack_controller3]:
            assert rc["system_id"] in result.agent_system_ids

    async def test_get_hosts_for_static_ip_addrs(
        self, fixture: Fixture, db_connection: AsyncConnection, db: Database
    ) -> None:
        rack = await create_test_rack_controller_entry(fixture)
        vlan = await create_test_vlan_entry(
            fixture, dhcp_on=True, primary_rack_id=rack["id"]
        )
        subnet = await create_test_subnet_entry(fixture, vlan_id=vlan["id"])
        ips = await create_test_staticipaddress_entry(fixture, subnet=subnet)
        machine = await create_test_machine_entry(fixture)
        interface = await create_test_interface_entry(
            fixture, node=machine, ips=ips, vlan_id=vlan["id"]
        )

        activities = DHCPConfigActivity(db, connection=db_connection)

        result = await activities._get_hosts_for_static_ip_addresses(
            db_connection, rack["system_id"], [ip["id"] for ip in ips]
        )
        assert result == [
            Host(
                ip=str(ip["ip"]),
                mac=interface.mac_address,
                hostname=machine["hostname"],
            )
            for ip in ips
        ]

    async def test_get_hosts_for_reserved_ips(
        self, fixture: Fixture, db_connection: AsyncConnection, db: Database
    ) -> None:
        rack = await create_test_rack_controller_entry(fixture)
        vlan = await create_test_vlan_entry(
            fixture, dhcp_on=True, primary_rack_id=rack["id"]
        )
        subnet = await create_test_subnet_entry(fixture, vlan_id=vlan["id"])
        reserved_ip = await create_test_reserved_ip_entry(
            fixture, subnet=subnet
        )

        activities = DHCPConfigActivity(db, connection=db_connection)

        result = await activities._get_hosts_for_reserved_ips(
            db_connection, rack["system_id"], [reserved_ip["id"]]
        )
        assert result == [
            Host(
                ip=str(reserved_ip["ip"]),
                mac=reserved_ip["mac_address"],
                hostname="",
            )
        ]

    async def test_fetch_hosts_for_update(
        self, fixture: Fixture, db_connection: AsyncConnection, db: Database
    ) -> None:
        env = ActivityEnvironment()

        rack = await create_test_rack_controller_entry(fixture)
        vlan = await create_test_vlan_entry(
            fixture, dhcp_on=True, primary_rack_id=rack["id"]
        )
        subnet = await create_test_subnet_entry(fixture, vlan_id=vlan["id"])
        ips = await create_test_staticipaddress_entry(fixture, subnet=subnet)
        machine = await create_test_machine_entry(fixture)
        interface = await create_test_interface_entry(
            fixture, node=machine, ips=ips, vlan_id=vlan["id"]
        )
        reserved_ip = await create_test_reserved_ip_entry(
            fixture, subnet=subnet
        )

        activities = DHCPConfigActivity(db, connection=db_connection)

        result = await env.run(
            activities.fetch_hosts_for_update,
            FetchHostsForUpdateParam(
                system_id=rack["system_id"],
                static_ip_addr_ids=[ip["id"] for ip in ips],
                reserved_ip_ids=[reserved_ip["id"]],
            ),
        )
        for host in [
            Host(
                ip=str(ip["ip"]),
                mac=interface.mac_address,
                hostname=machine["hostname"],
            )
            for ip in ips
        ] + [
            Host(
                ip=str(reserved_ip["ip"]),
                mac=reserved_ip["mac_address"],
                hostname="",
            )
        ]:
            assert host in result.hosts

    async def test_get_omapi_key(
        self, fixture: Fixture, db_connection: AsyncConnection, db: Database
    ) -> None:
        env = ActivityEnvironment()

        key = await create_test_secret(
            fixture, path="omapi-key", value={"secret": "abc"}
        )

        activities = DHCPConfigActivity(db, connection=db_connection)

        result = await env.run(activities.get_omapi_key)

        assert result.key == key.value["secret"]
