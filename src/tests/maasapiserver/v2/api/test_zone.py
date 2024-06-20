import datetime
from typing import Any

from httpx import AsyncClient
import pytest

from maasapiserver.v2.constants import V2_API_PREFIX
from maastesting.factory import factory
from tests.maasapiserver.fixtures.db import Fixture


def bmc_details(**extra_details: Any) -> dict[str, Any]:
    details = {
        "created": datetime.datetime.utcnow(),
        "updated": datetime.datetime.utcnow(),
        "power_type": "manual",
        "ip_address_id": None,
        "architectures": [],
        "bmc_type": 0,
        "capabilities": "[]",
        "cores": 0,
        "cpu_speed": 0,
        "local_storage": 0,
        "memory": 0,
        "name": "tough-mullet",
        "pool_id": None,
        "zone_id": 0,
        "tags": "[]",
        "cpu_over_commit_ratio": 1,
        "memory_over_commit_ratio": 1,
        "default_storage_pool_id": None,
        "power_parameters": {},
        "default_macvlan_mode": None,
        "version": "",
        "created_with_cert_expiration_days": None,
        "created_with_maas_generated_cert": None,
        "created_with_trust_password": None,
        "created_by_commissioning": False,
    }

    details.update(extra_details)
    return details


def zone_details(**extra_details: Any) -> dict[str, Any]:
    details = {
        "created": datetime.datetime.utcnow(),
        "updated": datetime.datetime.utcnow(),
        "name": "default",
        "description": "",
    }
    details.update(extra_details)
    return details


def node_details(**extra_details: Any) -> dict[str, Any]:
    """Return sample details for creating a site."""
    details = {
        "created": datetime.datetime.utcnow(),
        "updated": datetime.datetime.utcnow(),
        "system_id": factory.make_string(),
        "hostname": "test",
        "status": 1,
        "bios_boot_method": None,
        "osystem": "",
        "distro_series": "",
        "architecture": "amd64/generic",
        "min_hwe_kernel": "",
        "hwe_kernel": None,
        "agent_name": "",
        "error_description": "",
        "cpu_count": 0,
        "memory": 0,
        "swap_size": None,
        "power_state": "unknown",
        "power_state_updated": None,
        "error": "",
        "netboot": True,
        "license_key": "",
        "boot_cluster_ip": None,
        "enable_ssh": False,
        "skip_networking": False,
        "skip_storage": False,
        "boot_interface_id": None,
        "gateway_link_ipv4_id": None,
        "gateway_link_ipv6_id": None,
        "owner_id": None,
        "parent_id": None,
        "zone_id": 0,
        "boot_disk_id": None,
        "node_type": 0,
        "domain_id": 0,
        "dns_process_id": None,
        "bmc_id": 1,
        "address_ttl": None,
        "status_expires": datetime.datetime.utcnow(),
        "power_state_queried": None,
        "url": "",
        "managing_process_id": None,
        "last_image_sync": None,
        "previous_status": 0,
        "default_user": "",
        "cpu_speed": 0,
        "current_commissioning_script_set_id": None,
        "current_installation_script_set_id": None,
        "current_testing_script_set_id": None,
        "install_rackd": False,
        "locked": False,
        "pool_id": 0,
        "instance_power_parameters": {},
        "install_kvm": False,
        "hardware_uuid": None,
        "ephemeral_deploy": False,
        "description": "",
        "dynamic": False,
        "register_vmhost": False,
        "last_applied_storage_layout": "",
        "current_config_id": None,
        "enable_hw_sync": False,
        "last_sync": None,
        "sync_interval": None,
    }

    details.update(extra_details)
    return details


@pytest.mark.usefixtures("ensuremaasdb")
@pytest.mark.asyncio
class TestZoneApi:
    async def test_unauthenticated(
        self,
        api_client: AsyncClient,
    ) -> None:
        response = await api_client.get(f"{V2_API_PREFIX}/zones")
        assert response.status_code == 401
        assert response.json() == {"detail": "Invalid session ID"}

    async def test_list_with_no_nodes(
        self, authenticated_api_client: AsyncClient, fixture: Fixture
    ) -> None:
        [zone] = await fixture.get("maasserver_zone")

        zone["created"] = zone["created"].isoformat()
        zone["updated"] = zone["updated"].isoformat()
        zone["devices_count"] = 0
        zone["machines_count"] = 0
        zone["controllers_count"] = 0

        response = await authenticated_api_client.get(f"{V2_API_PREFIX}/zones")
        assert response.status_code == 200
        assert response.json() == [zone]

    async def test_list(
        self, authenticated_api_client: AsyncClient, fixture: Fixture
    ) -> None:
        [zone] = await fixture.get("maasserver_zone")
        await fixture.create(
            "maasserver_bmc", [bmc_details(zone_id=zone["id"])]
        )
        await fixture.create(
            "maasserver_node", [node_details(zone_id=zone["id"])]
        )

        zone["created"] = zone["created"].isoformat()
        zone["updated"] = zone["updated"].isoformat()
        zone["devices_count"] = 0
        zone["machines_count"] = 1
        zone["controllers_count"] = 0

        response = await authenticated_api_client.get(f"{V2_API_PREFIX}/zones")
        assert response.status_code == 200
        assert response.json() == [zone]

    async def test_list_with_multiple_zones(
        self, authenticated_api_client: AsyncClient, fixture: Fixture
    ) -> None:
        [zone1] = await fixture.get("maasserver_zone")
        [zone2] = await fixture.create(
            "maasserver_zone", [zone_details(name="zone2")]
        )
        [bmc1] = await fixture.create(
            "maasserver_bmc", [bmc_details(zone_id=zone1["id"])]
        )
        await fixture.create(
            "maasserver_node",
            [
                node_details(
                    hostname="host1",
                    system_id="foo",
                    bmc_id=bmc1["id"],
                    zone_id=zone1["id"],
                )
            ],
        )
        await fixture.create(
            "maasserver_node",
            [
                node_details(
                    hostname="host2",
                    system_id="bar",
                    bmc_id=bmc1["id"],
                    zone_id=zone1["id"],
                )
            ],
        )

        [bmc2] = await fixture.create(
            "maasserver_bmc", [bmc_details(zone_id=zone2["id"])]
        )
        await fixture.create(
            "maasserver_node",
            [
                node_details(
                    bmc_id=bmc2["id"], node_type=1, zone_id=zone2["id"]
                )
            ],
        )

        zone1["created"] = zone1["created"].isoformat()
        zone1["updated"] = zone1["updated"].isoformat()
        zone1["devices_count"] = 0
        zone1["machines_count"] = 2
        zone1["controllers_count"] = 0
        zone2["created"] = zone2["created"].isoformat()
        zone2["updated"] = zone2["updated"].isoformat()
        zone2["devices_count"] = 1
        zone2["machines_count"] = 0
        zone2["controllers_count"] = 0

        response = await authenticated_api_client.get(f"{V2_API_PREFIX}/zones")
        assert response.status_code == 200
        assert response.json() == [zone1, zone2]
