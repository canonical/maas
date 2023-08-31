# Copyright 2013-2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


import http.client
import json
import random

from django.conf import settings
from django.urls import reverse

from maasserver.api import machines as machines_module
from maasserver.clusterrpc import boot_images
from maasserver.enum import NODE_STATUS
from maasserver.models import Domain, Machine, Node, NodeMetadata
from maasserver.models.node import PowerInfo
from maasserver.testing.api import APITestCase
from maasserver.testing.architecture import make_usable_architecture
from maasserver.testing.factory import factory
from maasserver.utils import strip_domain
from maasserver.utils.converters import json_load_bytes
from maasserver.utils.orm import get_one, reload_object
from maastesting.matchers import MockNotCalled


class TestEnlistmentAPI(APITestCase.ForAnonymousAndUserAndAdmin):
    """Enlistment tests."""

    def setUp(self):
        super().setUp()
        self.patch(Node, "get_effective_power_info").return_value = PowerInfo(
            False, False, False, False, None, None
        )
        ubuntu = factory.make_default_ubuntu_release_bootable()
        osystem, release = ubuntu.name.split("/")
        self.patch(
            boot_images, "get_common_available_boot_images"
        ).return_value = [
            {"osystem": osystem, "release": release, "purpose": "xinstall"}
        ]

    def test_POST_create_creates_machine(self):
        architecture = make_usable_architecture(self)
        response = self.client.post(
            reverse("machines_handler"),
            {
                "hostname": "diane",
                "architecture": architecture,
                "power_type": "manual",
                "mac_addresses": ["aa:bb:cc:dd:ee:ff", "22:bb:cc:dd:ee:ff"],
            },
        )

        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json_load_bytes(response.content)
        self.assertIn("application/json", response["Content-Type"])
        domain_name = Domain.objects.get_default_domain().name
        self.assertEqual("diane.%s" % domain_name, parsed_result["fqdn"])
        self.assertNotEqual(0, len(parsed_result.get("system_id")))
        [diane] = Machine.objects.filter(hostname="diane")
        self.assertEqual(architecture, diane.architecture)

    def test_POST_new_generates_hostname_if_ip_based_hostname(self):
        Domain.objects.get_or_create(name="domain")
        hostname = "192-168-5-19.domain"
        response = self.client.post(
            reverse("machines_handler"),
            {
                "hostname": hostname,
                "architecture": make_usable_architecture(self),
                "power_type": "manual",
                "mac_addresses": [factory.make_mac_address()],
            },
        )
        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json_load_bytes(response.content)

        system_id = parsed_result.get("system_id")
        machine = Machine.objects.get(system_id=system_id)
        self.assertNotEqual(hostname, machine.hostname)

    def test_POST_create_creates_machine_with_power_parameters(self):
        # We're setting power parameters so we disable start_commissioning to
        # prevent anything from attempting to issue power instructions.
        self.patch(Node, "start_commissioning")
        hostname = factory.make_name("hostname")
        architecture = make_usable_architecture(self)
        power_type = "ipmi"
        power_parameters = {
            "power_address": factory.make_ip_address(),
            "power_user": factory.make_name("power-user"),
            "power_pass": factory.make_name("power-pass"),
        }
        response = self.client.post(
            reverse("machines_handler"),
            {
                "hostname": hostname,
                "architecture": architecture,
                "power_type": power_type,
                "mac_addresses": factory.make_mac_address(),
                "power_parameters": json.dumps(power_parameters),
            },
        )
        self.assertEqual(http.client.OK, response.status_code)
        [machine] = Machine.objects.filter(hostname=hostname)
        for key, value in power_parameters.items():
            self.assertEqual(machine.bmc.get_power_parameters()[key], value)
        self.assertEqual(power_type, machine.power_type)

    def test_POST_create_creates_machine_with_arch_only(self):
        architecture = make_usable_architecture(self, subarch_name="generic")
        response = self.client.post(
            reverse("machines_handler"),
            {
                "hostname": "diane",
                "architecture": architecture.split("/")[0],
                "power_type": "manual",
                "mac_addresses": ["aa:bb:cc:dd:ee:ff", "22:bb:cc:dd:ee:ff"],
            },
        )

        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json_load_bytes(response.content)
        self.assertIn("application/json", response["Content-Type"])
        domain_name = Domain.objects.get_default_domain().name
        self.assertEqual("diane.%s" % domain_name, parsed_result["fqdn"])
        self.assertNotEqual(0, len(parsed_result.get("system_id")))
        [diane] = Machine.objects.filter(hostname="diane")
        self.assertEqual(architecture, diane.architecture)

    def test_POST_create_creates_machine_with_subarchitecture(self):
        # The API allows a Machine to be created.
        architecture = make_usable_architecture(self)
        response = self.client.post(
            reverse("machines_handler"),
            {
                "hostname": "diane",
                "architecture": architecture.split("/")[0],
                "subarchitecture": architecture.split("/")[1],
                "power_type": "manual",
                "mac_addresses": ["aa:bb:cc:dd:ee:ff", "22:bb:cc:dd:ee:ff"],
            },
        )

        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json_load_bytes(response.content)
        self.assertIn("application/json", response["Content-Type"])
        domain_name = Domain.objects.get_default_domain().name
        self.assertEqual("diane.%s" % domain_name, parsed_result["fqdn"])
        self.assertNotEqual(0, len(parsed_result.get("system_id")))
        [diane] = Machine.objects.filter(hostname="diane")
        self.assertEqual(architecture, diane.architecture)

    def test_POST_create_fails_machine_with_double_subarchitecture(self):
        architecture = make_usable_architecture(self)
        response = self.client.post(
            reverse("machines_handler"),
            {
                "hostname": "diane",
                "architecture": architecture,
                "subarchitecture": architecture.split("/")[1],
                "mac_addresses": ["aa:bb:cc:dd:ee:ff", "22:bb:cc:dd:ee:ff"],
            },
        )
        self.assertEqual(http.client.BAD_REQUEST, response.status_code)
        self.assertIn("text/plain", response["Content-Type"])
        self.assertEqual(
            b"Subarchitecture cannot be specified twice.", response.content
        )

    def test_POST_create_associates_mac_addresses(self):
        # The API allows a Machine to be created and associated with MAC
        # Addresses.
        architecture = make_usable_architecture(self)
        self.client.post(
            reverse("machines_handler"),
            {
                "hostname": "diane",
                "architecture": architecture,
                "power_type": "manual",
                "mac_addresses": ["aa:bb:cc:dd:ee:ff", "22:bb:cc:dd:ee:ff"],
            },
        )
        diane = get_one(Machine.objects.filter(hostname="diane"))
        self.assertCountEqual(
            ["aa:bb:cc:dd:ee:ff", "22:bb:cc:dd:ee:ff"],
            [
                interface.mac_address
                for interface in diane.current_config.interface_set.all()
            ],
        )

    def test_POST_create_with_no_hostname_auto_populates_hostname(self):
        architecture = make_usable_architecture(self)
        response = self.client.post(
            reverse("machines_handler"),
            {
                "architecture": architecture,
                "power_type": "manual",
                "mac_addresses": [factory.make_mac_address()],
            },
        )
        machine = Machine.objects.get(
            system_id=json_load_bytes(response.content)["system_id"]
        )
        self.assertNotEqual("", strip_domain(machine.hostname))

    def test_POST_fails_with_bad_operation(self):
        # If the operation ('op=operation_name') specified in the
        # request data is unknown, a 'Bad request' response is returned.
        response = self.client.post(
            reverse("machines_handler"),
            {
                "op": "invalid_operation",
                "hostname": "diane",
                "mac_addresses": ["aa:bb:cc:dd:ee:ff", "invalid"],
            },
        )

        self.assertEqual(http.client.BAD_REQUEST, response.status_code)
        self.assertEqual(
            b"Unrecognised signature: method=POST op=invalid_operation",
            response.content,
        )

    def test_POST_create_rejects_invalid_data(self):
        # If the data provided to create a machine with an invalid MAC
        # Address, a 'Bad request' response is returned.
        response = self.client.post(
            reverse("machines_handler"),
            {
                "hostname": "diane",
                "mac_addresses": ["aa:bb:cc:dd:ee:ff", "invalid"],
            },
        )
        parsed_result = json_load_bytes(response.content)

        self.assertEqual(http.client.BAD_REQUEST, response.status_code)
        self.assertIn("application/json", response["Content-Type"])
        self.assertEqual(
            [
                "One or more MAC addresses is invalid. "
                "('invalid' is not a valid MAC address.)"
            ],
            parsed_result["mac_addresses"],
        )

    def test_POST_invalid_architecture_returns_bad_request(self):
        # If the architecture name provided to create a machine is not a valid
        # architecture name, a 'Bad request' response is returned.
        response = self.client.post(
            reverse("machines_handler"),
            {
                "hostname": "diane",
                "mac_addresses": ["aa:bb:cc:dd:ee:ff"],
                "architecture": "invalid-architecture",
            },
        )
        parsed_result = json_load_bytes(response.content)

        self.assertEqual(http.client.BAD_REQUEST, response.status_code)
        self.assertIn("application/json", response["Content-Type"])
        self.assertEqual(
            {"architecture"}, parsed_result.keys(), response.content
        )

    def test_POST_create_creates_machine_with_domain(self):
        domain = factory.make_Domain()
        # The API allows a Machine to be created.
        architecture = make_usable_architecture(self)
        response = self.client.post(
            reverse("machines_handler"),
            {
                "hostname": "diane",
                "architecture": architecture.split("/")[0],
                "subarchitecture": architecture.split("/")[1],
                "power_type": "manual",
                "mac_addresses": ["aa:bb:cc:dd:ee:ff", "22:bb:cc:dd:ee:ff"],
                "domain": domain.name,
            },
        )

        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json_load_bytes(response.content)
        self.assertIn("application/json", response["Content-Type"])
        self.assertEqual("diane.%s" % domain.name, parsed_result["fqdn"])
        self.assertNotEqual(0, len(parsed_result.get("system_id")))
        [diane] = Machine.objects.filter(hostname="diane")
        self.assertEqual(architecture, diane.architecture)


class TestMachineHostnameEnlistment(APITestCase.ForAnonymousAndUserAndAdmin):
    def setUp(self):
        super().setUp()
        self.patch(Node, "get_effective_power_info").return_value = PowerInfo(
            False, False, False, False, None, None
        )
        ubuntu = factory.make_default_ubuntu_release_bootable()
        osystem, release = ubuntu.name.split("/")
        self.patch(
            boot_images, "get_common_available_boot_images"
        ).return_value = [
            {"osystem": osystem, "release": release, "purpose": "xinstall"}
        ]

    def test_created_machine_gets_default_domain_appended(self):
        hostname_without_domain = factory.make_name("hostname")
        response = self.client.post(
            reverse("machines_handler"),
            {
                "hostname": hostname_without_domain,
                "architecture": make_usable_architecture(self),
                "power_type": "manual",
                "mac_addresses": [factory.make_mac_address()],
            },
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_result = json_load_bytes(response.content)
        expected_hostname = "{}.{}".format(
            hostname_without_domain,
            Domain.objects.get_default_domain().name,
        )
        self.assertEqual(expected_hostname, parsed_result.get("fqdn"))


class TestNonAdminEnlistmentAPI(APITestCase.ForAnonymousAndUser):
    """Enlistment tests for non-admin users."""

    def setUp(self):
        super().setUp()
        self.patch(Node, "get_effective_power_info").return_value = PowerInfo(
            False, False, False, False, None, None
        )

    def test_POST_non_admin_creates_machine_in_declared_state(self):
        # Upon non-admin enlistment, a machine goes into the New
        # state.  Deliberate approval is required before we start
        # reinstalling the system, wiping its disks etc.
        response = self.client.post(
            reverse("machines_handler"),
            {
                "hostname": factory.make_string(),
                "architecture": make_usable_architecture(self),
                "mac_addresses": ["aa:bb:cc:dd:ee:ff"],
            },
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        system_id = json_load_bytes(response.content)["system_id"]
        self.assertEqual(
            NODE_STATUS.NEW, Machine.objects.get(system_id=system_id).status
        )


class TestAnonymousEnlistmentAPI(APITestCase.ForAnonymous):
    """Enlistment tests specific to anonymous users."""

    def setUp(self):
        super().setUp()
        self.patch(Node, "get_effective_power_info").return_value = PowerInfo(
            False, False, False, False, None, None
        )

    def test_POST_accept_not_allowed(self):
        # An anonymous user is not allowed to accept an anonymously
        # enlisted machine.  That would defeat the whole purpose of holding
        # those machines for approval.
        machine_id = factory.make_Node(status=NODE_STATUS.NEW).system_id
        response = self.client.post(
            reverse("machines_handler"),
            {"op": "accept", "machines": [machine_id]},
        )
        self.assertEqual(
            (
                http.client.UNAUTHORIZED,
                b"You must be logged in to accept machines.",
            ),
            (response.status_code, response.content),
        )

    def test_POST_returns_limited_fields(self):
        response = self.client.post(
            reverse("machines_handler"),
            {
                "architecture": make_usable_architecture(self),
                "hostname": factory.make_string(),
                "mac_addresses": ["aa:bb:cc:dd:ee:ff", "22:bb:cc:dd:ee:ff"],
            },
        )
        parsed_result = json_load_bytes(response.content)
        # Limited fields on machine.
        self.assertEqual(
            {
                "system_id",
                "hostname",
                "domain",
                "fqdn",
                "architecture",
                "status",
                "power_type",
                "power_state",
                "zone",
                "status_action",
                "status_message",
                "status_name",
                "node_type",
                "resource_uri",
            },
            parsed_result.keys(),
        )
        # Limited fields on domain.
        self.assertEqual(
            {
                "id",
                "name",
                "ttl",
                "is_default",
                "authoritative",
                "resource_record_count",
            },
            parsed_result["domain"].keys(),
        )
        # Limited fields on zone.
        self.assertEqual(
            {"id", "name", "description"}, parsed_result["zone"].keys()
        )

    def test_POST_create_returns_machine_with_matching_power_parameters(self):
        mock_create_machine = self.patch(machines_module, "create_machine")
        hostname = factory.make_name("hostname")
        architecture = make_usable_architecture(self)
        power_type = "ipmi"
        power_parameters = {
            "power_address": factory.make_ip_address(),
            "power_user": factory.make_name("power-user"),
            "power_pass": factory.make_name("power-pass"),
        }
        machine = factory.make_Machine(
            hostname=hostname,
            status=NODE_STATUS.NEW,
            architecture="",
            power_type=power_type,
            power_parameters=power_parameters,
        )
        # Simulate creating the MAAS IPMI user
        power_parameters["power_user"] = "maas"
        power_parameters["power_pass"] = factory.make_name("power-pass")
        response = self.client.post(
            reverse("machines_handler"),
            {
                "hostname": "maas-enlistment",
                "architecture": architecture,
                "power_type": power_type,
                "mac_addresses": factory.make_mac_address(),
                "power_parameters": json.dumps(power_parameters),
            },
        )
        self.assertEqual(http.client.OK, response.status_code)
        machine = reload_object(machine)
        self.assertEqual(hostname, machine.hostname)
        self.assertEqual(architecture, machine.architecture)
        for key, value in power_parameters.items():
            self.assertEqual(machine.bmc.get_power_parameters()[key], value)
        self.assertThat(mock_create_machine, MockNotCalled())
        self.assertEqual(
            machine.system_id, json_load_bytes(response.content)["system_id"]
        )

    def test_POST_create_returns_machine_with_matching_mac(self):
        hostname = factory.make_name("hostname")
        machine = factory.make_Machine(
            hostname=hostname, status=NODE_STATUS.NEW, architecture=""
        )
        macs = [
            str(factory.make_Interface(node=machine).mac_address)
            for _ in range(3)
        ]
        architecture = make_usable_architecture(self)
        response = self.client.post(
            reverse("machines_handler"),
            {
                "hostname": "maas-enlistment",
                "architecture": architecture,
                "mac_addresses": [
                    # Machine only has to match one MAC address.
                    random.choice(macs),
                    # A MAC address unknown to MAAS shouldn't effect finding
                    # the machine.
                    factory.make_mac_address(),
                ],
            },
        )

        self.assertEqual(http.client.OK, response.status_code)
        machine = reload_object(machine)
        self.assertEqual(hostname, machine.hostname)
        self.assertEqual(architecture, machine.architecture)
        self.assertEqual(
            machine.system_id, json_load_bytes(response.content)["system_id"]
        )

    def test_POST_create_creates_machine(self):
        hostname = factory.make_name("hostname")
        architecture = make_usable_architecture(self)
        response = self.client.post(
            reverse("machines_handler"),
            {
                "hostname": hostname,
                "architecture": architecture,
                "power_type": "manual",
                "mac_addresses": ["aa:bb:cc:dd:ee:ff", "22:bb:cc:dd:ee:ff"],
            },
        )
        self.assertEqual(http.client.OK, response.status_code)
        self.assertFalse(NodeMetadata.objects.filter(key="enlisting").exists())
        [machine] = Machine.objects.filter(hostname=hostname)
        self.assertEqual(architecture, machine.architecture)
        self.assertEqual(
            machine.system_id, json_load_bytes(response.content)["system_id"]
        )

    def test_POST_create_creates_machine_commission(self):
        hostname = factory.make_name("hostname")
        architecture = make_usable_architecture(self)
        response = self.client.post(
            reverse("machines_handler"),
            {
                "hostname": hostname,
                "architecture": architecture,
                "power_type": "manual",
                "mac_addresses": ["aa:bb:cc:dd:ee:ff", "22:bb:cc:dd:ee:ff"],
                "commission": True,
            },
        )
        self.assertEqual(http.client.OK, response.status_code)
        node_metadata = NodeMetadata.objects.get(key="enlisting")
        self.assertEqual("True", node_metadata.value)
        [machine] = Machine.objects.filter(hostname=hostname)
        self.assertEqual(architecture, machine.architecture)
        self.assertEqual(
            machine.system_id, json_load_bytes(response.content)["system_id"]
        )
        self.assertEqual(NODE_STATUS.COMMISSIONING, machine.status)

    def test_POST_create_requires_architecture(self):
        hostname = factory.make_name("hostname")
        response = self.client.post(
            reverse("machines_handler"),
            {
                "hostname": hostname,
                "power_type": "manual",
                "mac_addresses": ["aa:bb:cc:dd:ee:ff", "22:bb:cc:dd:ee:ff"],
            },
        )
        self.assertEqual(http.client.BAD_REQUEST, response.status_code)
        self.assertDictEqual(
            {"architecture": ["This field is required."]},
            json_load_bytes(response.content),
        )

    def test_POST_create_validates_architecture(self):
        hostname = factory.make_name("hostname")
        power_type = "ipmi"
        power_parameters = {
            "power_address": factory.make_ip_address(),
            "power_user": factory.make_name("power-user"),
            "power_pass": factory.make_name("power-pass"),
            "power_driver": "LAN_2_0",
            "mac_address": "",
            "power_boot_type": "auto",
        }
        factory.make_Machine(
            hostname=hostname,
            status=NODE_STATUS.NEW,
            architecture="",
            power_type=power_type,
            power_parameters=power_parameters,
        )
        response = self.client.post(
            reverse("machines_handler"),
            {
                "hostname": "maas-enlistment",
                "architecture": factory.make_name("arch"),
                "power_type": power_type,
                "mac_addresses": factory.make_mac_address(),
                "power_parameters": json.dumps(power_parameters),
            },
        )
        self.assertEqual(http.client.BAD_REQUEST, response.status_code)


class TestSimpleUserLoggedInEnlistmentAPI(APITestCase.ForUser):
    """Enlistment tests from the perspective of regular, non-admin users."""

    def setUp(self):
        super().setUp()
        self.assertFalse(self.user.is_superuser)
        self.patch(Node, "get_effective_power_info").return_value = PowerInfo(
            False, False, False, False, None, None
        )

    def test_POST_accept_not_allowed(self):
        # An non-admin user is not allowed to accept an anonymously
        # enlisted machine.  That would defeat the whole purpose of holding
        # those machines for approval.
        machine_id = factory.make_Node(status=NODE_STATUS.NEW).system_id
        response = self.client.post(
            reverse("machines_handler"),
            {"op": "accept", "machines": [machine_id]},
        )
        self.assertEqual(
            (
                http.client.FORBIDDEN,
                (
                    "You don't have the required permission to accept the "
                    "following machine(s): %s." % machine_id
                ).encode(settings.DEFAULT_CHARSET),
            ),
            (response.status_code, response.content),
        )

    def test_POST_accept_all_does_not_accept_anything(self):
        # It is not an error for a non-admin user to attempt to accept all
        # anonymously enlisted machines, but only those for which he/she has
        # admin privs will be accepted, which currently equates to none of
        # them.
        factory.make_Node(status=NODE_STATUS.NEW),
        factory.make_Node(status=NODE_STATUS.NEW),
        response = self.client.post(
            reverse("machines_handler"), {"op": "accept_all"}
        )
        self.assertEqual(http.client.OK, response.status_code)
        machines_returned = json_load_bytes(response.content)
        self.assertEqual([], machines_returned)

    def test_POST_simple_user_can_set_power_type_and_parameters(self):
        new_power_address = factory.make_ip_address()  # XXX: URLs don't work.
        new_power_id = factory.make_name("power_id")
        response = self.client.post(
            reverse("machines_handler"),
            {
                "architecture": make_usable_architecture(self),
                "power_type": "virsh",
                "power_parameters": json.dumps(
                    {
                        "power_address": new_power_address,
                        "power_id": new_power_id,
                    }
                ),
                "mac_addresses": ["AA:BB:CC:DD:EE:FF"],
            },
        )
        machine = Machine.objects.get(
            system_id=json_load_bytes(response.content)["system_id"]
        )
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual("virsh", machine.power_type)
        self.assertEqual(
            {
                "power_pass": "",
                "power_id": new_power_id,
                "power_address": new_power_address,
            },
            machine.get_power_parameters(),
        )

    def test_POST_returns_limited_fields(self):
        response = self.client.post(
            reverse("machines_handler"),
            {
                "hostname": factory.make_string(),
                "architecture": make_usable_architecture(self),
                "mac_addresses": ["aa:bb:cc:dd:ee:ff", "22:bb:cc:dd:ee:ff"],
            },
        )
        parsed_result = json_load_bytes(response.content)
        self.assertEqual(
            {
                "hostname",
                "description",
                "hardware_uuid",
                "default_gateways",
                "domain",
                "fqdn",
                "owner",
                "owner_data",
                "system_id",
                "architecture",
                "min_hwe_kernel",
                "hwe_kernel",
                "status",
                "locked",
                "osystem",
                "distro_series",
                "netboot",
                "node_type",
                "node_type_name",
                "numanode_set",
                "parent",
                "pod",
                "power_type",
                "power_state",
                "resource_uri",
                "tag_names",
                "ip_addresses",
                "interface_set",
                "cpu_count",
                "cpu_speed",
                "storage",
                "memory",
                "swap_size",
                "pool",
                "zone",
                "disable_ipv4",
                "address_ttl",
                "boot_disk",
                "bios_boot_method",
                "boot_interface",
                "blockdevice_set",
                "physicalblockdevice_set",
                "virtualblockdevice_set",
                "volume_groups",
                "raids",
                "cache_sets",
                "bcaches",
                "status_action",
                "status_message",
                "status_name",
                "special_filesystems",
                "current_commissioning_result_id",
                "current_testing_result_id",
                "current_installation_result_id",
                "commissioning_status",
                "commissioning_status_name",
                "testing_status",
                "testing_status_name",
                "cpu_test_status",
                "cpu_test_status_name",
                "memory_test_status",
                "memory_test_status_name",
                "network_test_status",
                "network_test_status_name",
                "storage_test_status",
                "storage_test_status_name",
                "other_test_status",
                "other_test_status_name",
                "hardware_info",
                "interface_test_status",
                "interface_test_status_name",
                "virtualmachine_id",
                "workload_annotations",
                "last_sync",
                "sync_interval",
                "next_sync",
                "enable_hw_sync",
                "ephemeral_deploy",
            },
            parsed_result.keys(),
        )


class TestAdminLoggedInEnlistmentAPI(APITestCase.ForAdmin):
    """Enlistment tests from the perspective of admin users."""

    def setUp(self):
        super().setUp()
        self.patch(Node, "get_effective_power_info").return_value = PowerInfo(
            False, False, False, False, None, None
        )
        ubuntu = factory.make_default_ubuntu_release_bootable()
        osystem, release = ubuntu.name.split("/")
        self.patch(
            boot_images, "get_common_available_boot_images"
        ).return_value = [
            {"osystem": osystem, "release": release, "purpose": "xinstall"}
        ]

    def test_POST_sets_power_type_if_admin(self):
        response = self.client.post(
            reverse("machines_handler"),
            {
                "architecture": make_usable_architecture(self),
                "power_type": "manual",
                "mac_addresses": ["00:11:22:33:44:55"],
            },
        )
        self.assertEqual(http.client.OK, response.status_code)
        machine = Machine.objects.get(
            system_id=json_load_bytes(response.content)["system_id"]
        )
        self.assertEqual("manual", machine.power_type)
        self.assertEqual({}, machine.get_power_parameters())

    def test_POST_sets_power_parameters_field(self):
        # The api allows the setting of a Machine's power_parameters field.
        # Create a power_parameter valid for the selected power_type.
        new_power_id = factory.make_name("power_id")
        new_power_address = factory.make_ipv4_address()
        new_power_pass = factory.make_name("power_pass")
        response = self.client.post(
            reverse("machines_handler"),
            {
                "architecture": make_usable_architecture(self),
                "power_type": "virsh",
                "power_parameters_power_id": new_power_id,
                "power_parameters_power_pass": new_power_pass,
                "power_parameters_power_address": new_power_address,
                "mac_addresses": ["AA:BB:CC:DD:EE:FF"],
            },
        )

        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        machine = Machine.objects.get(
            system_id=json_load_bytes(response.content)["system_id"]
        )
        self.assertEqual(
            {
                "power_id": new_power_id,
                "power_pass": new_power_pass,
                "power_address": new_power_address,
            },
            reload_object(machine).get_power_parameters(),
        )

    def test_POST_updates_power_parameters_rejects_unknown_param(self):
        hostname = factory.make_string()
        response = self.client.post(
            reverse("machines_handler"),
            {
                "hostname": hostname,
                "architecture": make_usable_architecture(self),
                "power_type": "manual",
                "power_parameters_unknown_param": factory.make_string(),
                "mac_addresses": [factory.make_mac_address()],
            },
        )

        self.assertEqual(
            (
                http.client.BAD_REQUEST,
                {"power_parameters": ["Unknown parameter(s): unknown_param."]},
            ),
            (response.status_code, json_load_bytes(response.content)),
        )
        self.assertFalse(Machine.objects.filter(hostname=hostname).exists())

    def test_POST_new_sets_power_parameters_skip_check(self):
        # The api allows to skip the validation step and set arbitrary
        # power parameters.
        param = factory.make_string()
        response = self.client.post(
            reverse("machines_handler"),
            {
                "architecture": make_usable_architecture(self),
                "power_type": "manual",
                "power_parameters_param": param,
                "power_parameters_skip_check": "true",
                "mac_addresses": ["AA:BB:CC:DD:EE:FF"],
            },
        )

        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        machine = Machine.objects.get(
            system_id=json_load_bytes(response.content)["system_id"]
        )
        self.assertEqual(
            {"param": param}, reload_object(machine).get_power_parameters()
        )

    def test_POST_admin_creates_machine_in_commissioning_state(self):
        # When an admin user enlists a machine, it goes into the
        # Commissioning state.
        response = self.client.post(
            reverse("machines_handler"),
            {
                "hostname": factory.make_string(),
                "architecture": make_usable_architecture(self),
                "power_type": "manual",
                "mac_addresses": ["aa:bb:cc:dd:ee:ff"],
            },
        )
        self.assertEqual(http.client.OK, response.status_code)
        system_id = json_load_bytes(response.content)["system_id"]
        self.assertEqual(
            NODE_STATUS.COMMISSIONING,
            Machine.objects.get(system_id=system_id).status,
        )

    def test_POST_returns_limited_fields(self):
        response = self.client.post(
            reverse("machines_handler"),
            {
                "hostname": factory.make_string(),
                "architecture": make_usable_architecture(self),
                "power_type": "manual",
                "mac_addresses": ["aa:bb:cc:dd:ee:ff", "22:bb:cc:dd:ee:ff"],
            },
        )
        parsed_result = json_load_bytes(response.content)
        self.assertEqual(
            {
                "hostname",
                "description",
                "hardware_uuid",
                "default_gateways",
                "domain",
                "fqdn",
                "owner",
                "owner_data",
                "system_id",
                "architecture",
                "min_hwe_kernel",
                "hwe_kernel",
                "status",
                "locked",
                "osystem",
                "distro_series",
                "netboot",
                "node_type",
                "node_type_name",
                "parent",
                "pod",
                "power_type",
                "power_state",
                "resource_uri",
                "tag_names",
                "ip_addresses",
                "interface_set",
                "cpu_count",
                "cpu_speed",
                "storage",
                "memory",
                "swap_size",
                "zone",
                "pool",
                "disable_ipv4",
                "address_ttl",
                "boot_disk",
                "bios_boot_method",
                "boot_interface",
                "blockdevice_set",
                "numanode_set",
                "physicalblockdevice_set",
                "virtualblockdevice_set",
                "volume_groups",
                "raids",
                "cache_sets",
                "bcaches",
                "status_name",
                "status_message",
                "status_action",
                "special_filesystems",
                "current_commissioning_result_id",
                "current_testing_result_id",
                "current_installation_result_id",
                "commissioning_status",
                "commissioning_status_name",
                "testing_status",
                "testing_status_name",
                "cpu_test_status",
                "cpu_test_status_name",
                "memory_test_status",
                "memory_test_status_name",
                "network_test_status",
                "network_test_status_name",
                "storage_test_status",
                "storage_test_status_name",
                "other_test_status",
                "other_test_status_name",
                "hardware_info",
                "interface_test_status",
                "interface_test_status_name",
                "virtualmachine_id",
                "workload_annotations",
                "last_sync",
                "sync_interval",
                "next_sync",
                "enable_hw_sync",
                "ephemeral_deploy",
            },
            parsed_result.keys(),
        )

    def test_POST_accept_all(self):
        # An admin user can accept all anonymously enlisted machines.
        machines = [
            factory.make_Node(status=NODE_STATUS.NEW),
            factory.make_Node(status=NODE_STATUS.NEW),
        ]
        response = self.client.post(
            reverse("machines_handler"), {"op": "accept_all"}
        )
        self.assertEqual(http.client.OK, response.status_code)
        machines_returned = json_load_bytes(response.content)
        self.assertSetEqual(
            {machine.system_id for machine in machines},
            {machine["system_id"] for machine in machines_returned},
        )
