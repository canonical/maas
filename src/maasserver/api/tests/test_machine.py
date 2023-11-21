# Copyright 2015-2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from base64 import b64encode
from datetime import datetime
import http.client
import logging
from random import choice
from unittest.mock import ANY, call

from django.conf import settings
from django.db import transaction
from django.urls import reverse
from django.utils.http import urlencode
from netaddr import IPAddress, IPNetwork
from testtools.matchers import (
    ContainsDict,
    MatchesListwise,
    MatchesStructure,
    StartsWith,
)
from twisted.internet import defer
import yaml

from maasserver import forms
from maasserver.api import auth
from maasserver.api import machines as machines_module
from maasserver.enum import (
    BRIDGE_TYPE,
    FILESYSTEM_FORMAT_TYPE_CHOICES,
    FILESYSTEM_TYPE,
    INTERFACE_LINK_TYPE,
    INTERFACE_TYPE,
    IPADDRESS_TYPE,
    NODE_STATUS,
    NODE_STATUS_CHOICES,
    NODE_STATUS_CHOICES_DICT,
    NODE_TYPE,
    NODE_TYPE_CHOICES,
    POWER_STATE,
)
from maasserver.exceptions import StaticIPAddressExhaustion
from maasserver.models import Config, Domain, Filesystem, Machine, Node
from maasserver.models import node as node_module
from maasserver.models import NodeKey, NodeUserData, ScriptSet, StaticIPAddress
from maasserver.models.bmc import Pod
from maasserver.models.node import RELEASABLE_STATUSES
from maasserver.models.signals.testing import SignalsDisabled
from maasserver.storage_layouts import (
    MIN_BOOT_PARTITION_SIZE,
    StorageLayoutError,
)
from maasserver.testing.api import (
    APITestCase,
    APITransactionTestCase,
    explain_unexpected_response,
)
from maasserver.testing.architecture import make_usable_architecture
from maasserver.testing.factory import factory
from maasserver.testing.fixtures import RBACEnabled
from maasserver.testing.matchers import HasStatusCode
from maasserver.testing.orm import reload_objects
from maasserver.testing.osystems import make_usable_osystem
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.testing.testclient import MAASSensibleOAuthClient
from maasserver.utils.converters import json_load_bytes
from maasserver.utils.orm import post_commit, reload_object
from maastesting.matchers import (
    Equals,
    MockCalledOnce,
    MockCalledOnceWith,
    MockCallsMatch,
    MockNotCalled,
)
from metadataserver.builtin_scripts import load_builtin_scripts
from metadataserver.builtin_scripts.tests import test_hooks
from metadataserver.enum import SCRIPT_TYPE
from metadataserver.nodeinituser import get_node_init_user
from provisioningserver.refresh.node_info_scripts import (
    COMMISSIONING_OUTPUT_NAME,
    NODE_INFO_SCRIPTS,
)
from provisioningserver.utils.enum import map_enum


class TestMachineAnonAPI(MAASServerTestCase):
    def test_machine_init_user_cannot_access(self):
        token = NodeKey.objects.get_token_for_node(factory.make_Node())
        client = MAASSensibleOAuthClient(get_node_init_user(), token)
        response = client.get(reverse("machines_handler"))
        self.assertThat(response, HasStatusCode(http.client.FORBIDDEN))


class TestMachinesAPILoggedIn(APITestCase.ForUserAndAdmin):
    """A logged-in user can access the API."""

    def setUp(self):
        super().setUp()
        self.patch(node_module, "wait_for_power_command")
        self.patch(node_module.Node, "_start")

    def test_machines_GET_logged_in(self):
        machine = factory.make_Node()
        response = self.client.get(reverse("machines_handler"))
        parsed_result = json_load_bytes(response.content)

        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(
            [machine.system_id],
            [
                parsed_machine.get("system_id")
                for parsed_machine in parsed_result
            ],
        )


class TestMachineAPI(APITestCase.ForUser):
    """Tests for /api/2.0/machines/<machine>/."""

    # XXX: GavinPanella 2016-05-24 bug=1585138: op=acquire does not work for
    # clients authenticated via username and password.
    clientfactories = {"oauth": MAASSensibleOAuthClient}

    def setUp(self):
        super().setUp()
        self.patch(node_module.Node, "_pc_power_control_node")

    def test_handler_path(self):
        self.assertEqual(
            "/MAAS/api/2.0/machines/machine-name/",
            reverse("machine_handler", args=["machine-name"]),
        )

    @staticmethod
    def get_machine_uri(machine):
        """Get the API URI for `machine`."""
        return reverse("machine_handler", args=[machine.system_id])

    def test_GET_returns_machine(self):
        # The api allows for fetching a single Machine (using system_id).
        machine = factory.make_Node()
        response = self.client.get(self.get_machine_uri(machine))

        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json_load_bytes(response.content)
        domain_name = Domain.objects.get_default_domain().name
        self.assertEqual(
            f"{machine.hostname}.{domain_name}", parsed_result["fqdn"]
        )
        self.assertEqual(machine.system_id, parsed_result["system_id"])

    def test_GET_returns_boot_interface_object(self):
        # The api allows for fetching a single Machine (using system_id).
        machine = factory.make_Node(interface=True)
        boot_interface = machine.get_boot_interface()
        response = self.client.get(self.get_machine_uri(machine))

        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json_load_bytes(response.content)
        self.assertEqual(
            boot_interface.id, parsed_result["boot_interface"]["id"]
        )
        self.assertEqual(
            str(boot_interface.mac_address),
            parsed_result["boot_interface"]["mac_address"],
        )

    def test_GET_returns_associated_tag(self):
        machine = factory.make_Node()
        tag = factory.make_Tag()
        machine.tags.add(tag)
        response = self.client.get(self.get_machine_uri(machine))

        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json_load_bytes(response.content)
        self.assertEqual([tag.name], parsed_result["tag_names"])

    def test_GET_returns_bios_boot_method(self):
        machine = factory.make_Node(bios_boot_method="pxe")
        tag = factory.make_Tag()
        machine.tags.add(tag)
        response = self.client.get(self.get_machine_uri(machine))

        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json_load_bytes(response.content)
        self.assertEqual("pxe", parsed_result["bios_boot_method"])

    def test_GET_returns_associated_ip_addresses(self):
        machine = factory.make_Node()
        nic = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=machine)
        subnet = factory.make_Subnet()
        ip = factory.pick_ip_in_network(subnet.get_ipnetwork())
        lease = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.DISCOVERED,
            ip=ip,
            interface=nic,
            subnet=subnet,
        )
        response = self.client.get(self.get_machine_uri(machine))

        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_result = json_load_bytes(response.content)
        self.assertEqual([lease.ip], parsed_result["ip_addresses"])

    def test_GET_returns_interface_set(self):
        machine = factory.make_Node()
        response = self.client.get(self.get_machine_uri(machine))
        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json_load_bytes(response.content)
        self.assertIn("interface_set", parsed_result)

    def test_GET_returns_zone(self):
        machine = factory.make_Node()
        response = self.client.get(self.get_machine_uri(machine))
        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json_load_bytes(response.content)
        self.assertEqual(
            [machine.zone.name, machine.zone.description],
            [
                parsed_result["zone"]["name"],
                parsed_result["zone"]["description"],
            ],
        )

    def test_GET_returns_pool(self):
        pool = factory.make_ResourcePool()
        machine = factory.make_Node(pool=pool)
        response = self.client.get(self.get_machine_uri(machine))
        self.assertEqual(http.client.OK, response.status_code)
        result = json_load_bytes(response.content)
        self.assertEqual(
            result["pool"],
            {
                "id": pool.id,
                "name": pool.name,
                "description": pool.description,
                "resource_uri": reverse(
                    "resourcepool_handler", args=[pool.id]
                ),
            },
        )

    def test_GET_returns_boot_interface(self):
        machine = factory.make_Node(interface=True)
        machine.boot_interface = machine.current_config.interface_set.first()
        machine.save()
        response = self.client.get(self.get_machine_uri(machine))
        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json_load_bytes(response.content)
        self.assertEqual(
            machine.boot_interface.mac_address,
            parsed_result["boot_interface"]["mac_address"],
        )

    def test_GET_returns_hardware_sync_values(self):
        machine = factory.make_Node(enable_hw_sync=True)
        machine.last_sync = datetime.now()
        machine.save()
        response = self.client.get(self.get_machine_uri(machine))
        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json_load_bytes(response.content)
        self.assertEqual(
            machine.last_sync.isoformat()[:-3], parsed_result["last_sync"]
        )
        self.assertEqual(machine.sync_interval, parsed_result["sync_interval"])
        self.assertEqual(
            machine.next_sync.isoformat()[:-3], parsed_result["next_sync"]
        )

    def test_GET_refuses_to_access_nonexistent_machine(self):
        # When fetching a Machine, the api returns a 'Not Found' (404) error
        # if no machine is found.
        url = reverse("machine_handler", args=["invalid-uuid"])

        response = self.client.get(url)

        self.assertEqual(http.client.NOT_FOUND, response.status_code)
        self.assertEqual(
            "No Machine matches the given query.",
            response.content.decode(settings.DEFAULT_CHARSET),
        )

    def test_GET_returns_404_if_machine_name_contains_invld_characters(self):
        # When the requested name contains characters that are invalid for
        # a hostname, the result of the request is a 404 response.
        url = reverse("machine_handler", args=["invalid-uuid-#..."])

        response = self.client.get(url)

        self.assertEqual(http.client.NOT_FOUND, response.status_code)
        self.assertEqual(
            "No Machine matches the given query.",
            response.content.decode(settings.DEFAULT_CHARSET),
        )

    def test_GET_returns_owner_name_when_allocated_to_self(self):
        machine = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=self.user
        )
        response = self.client.get(self.get_machine_uri(machine))
        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json_load_bytes(response.content)
        self.assertEqual(machine.owner.username, parsed_result["owner"])

    def test_GET_returns_virtualmachine(self):
        machine = factory.make_Node()
        vm = factory.make_VirtualMachine(machine=machine)
        response = self.client.get(self.get_machine_uri(machine))
        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json_load_bytes(response.content)
        self.assertEqual(parsed_result["virtualmachine_id"], vm.id)

    def test_GET_permission_denied_when_allocated_to_other_user(self):
        machine = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=factory.make_User()
        )
        response = self.client.get(self.get_machine_uri(machine))
        self.assertEqual(http.client.FORBIDDEN, response.status_code)

    def test_GET_returns_empty_owner_when_not_allocated(self):
        machine = factory.make_Node(status=NODE_STATUS.READY)
        response = self.client.get(self.get_machine_uri(machine))
        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json_load_bytes(response.content)
        self.assertIsNone(parsed_result["owner"])

    def test_GET_returns_physical_block_devices(self):
        machine = factory.make_Node(with_boot_disk=False)
        devices = [
            factory.make_PhysicalBlockDevice(node=machine) for _ in range(3)
        ]
        response = self.client.get(self.get_machine_uri(machine))
        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json_load_bytes(response.content)
        parsed_devices = [
            device["name"]
            for device in parsed_result["physicalblockdevice_set"]
        ]
        self.assertCountEqual(
            [device.name for device in devices], parsed_devices
        )

    def test_GET_rejects_other_node_types(self):
        node = factory.make_Node_with_Interface_on_Subnet(
            owner=self.user,
            node_type=factory.pick_choice(
                NODE_TYPE_CHOICES, but_not=[NODE_TYPE.MACHINE]
            ),
        )
        response = self.client.get(self.get_machine_uri(node))
        self.assertEqual(
            http.client.NOT_FOUND, response.status_code, response.content
        )

    def test_GET_returns_min_hwe_kernel_and_hwe_kernel(self):
        machine = factory.make_Node()
        response = self.client.get(self.get_machine_uri(machine))

        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json_load_bytes(response.content)
        self.assertIsNone(parsed_result["min_hwe_kernel"])
        self.assertIsNone(parsed_result["hwe_kernel"])

    def test_GET_returns_min_hwe_kernel(self):
        machine = factory.make_Node(min_hwe_kernel="hwe-v")
        response = self.client.get(self.get_machine_uri(machine))

        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json_load_bytes(response.content)
        self.assertEqual("hwe-v", parsed_result["min_hwe_kernel"])

    def test_GET_returns_status_message_with_most_recent_event(self):
        """Makes sure the most recent event from this machine is shown in the
        status_message attribute."""
        type_description = "Type description"
        event_type = factory.make_EventType(
            level=logging.INFO, description=type_description
        )
        # The first event won't be returned.
        event = factory.make_Event(
            type=event_type, description="Uninteresting event"
        )
        machine = event.node
        # The second (and last) event will be returned.
        message = "Interesting event"
        factory.make_Event(type=event_type, description=message, node=machine)
        response = self.client.get(self.get_machine_uri(machine))
        parsed_result = json_load_bytes(response.content)
        self.assertEqual(
            f"{type_description} - {message}",
            parsed_result["status_message"],
        )

    def test_GET_returns_status_name(self):
        """GET should display the machine status as a user-friendly string."""
        for status in NODE_STATUS_CHOICES_DICT:
            machine = factory.make_Node(status=status)
            response = self.client.get(self.get_machine_uri(machine))
            parsed_result = json_load_bytes(response.content)
            self.assertEqual(
                NODE_STATUS_CHOICES_DICT[status], parsed_result["status_name"]
            )

    def test_GET_returns_parent(self):
        parent = factory.make_Node()
        machine = factory.make_Node(parent=parent)
        response = self.client.get(self.get_machine_uri(machine))

        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json_load_bytes(response.content)
        self.assertEqual(
            parent.system_id, parsed_result["parent"]["system_id"]
        )
        self.assertEqual(
            reverse("machine_handler", args=[parent.system_id]),
            parsed_result["parent"]["resource_uri"],
        )

    def test_POST_deploy_sets_osystem_and_distro_series(self):
        self.patch(node_module.Node, "_start")
        self.patch(machines_module, "get_curtin_merged_config")
        machine = factory.make_Node(
            owner=self.user,
            interface=True,
            power_type="manual",
            status=NODE_STATUS.READY,
            architecture=make_usable_architecture(self),
        )
        osystem = make_usable_osystem(self)
        distro_series = osystem["default_release"]
        response = self.client.post(
            self.get_machine_uri(machine),
            {"op": "deploy", "distro_series": distro_series},
        )
        self.assertEqual(
            (http.client.OK, machine.system_id),
            (
                response.status_code,
                json_load_bytes(response.content)["system_id"],
            ),
        )
        self.assertEqual(osystem["name"], reload_object(machine).osystem)
        self.assertEqual(distro_series, reload_object(machine).distro_series)

    def test_POST_deploy_validates_distro_series(self):
        machine = factory.make_Node_with_Interface_on_Subnet(
            owner=self.user,
            interface=True,
            power_type="manual",
            status=NODE_STATUS.READY,
            architecture=make_usable_architecture(self),
        )
        invalid_distro_series = factory.make_string()
        response = self.client.post(
            self.get_machine_uri(machine),
            {"op": "deploy", "distro_series": invalid_distro_series},
        )
        self.assertEqual(
            (
                http.client.BAD_REQUEST,
                {
                    "distro_series": [
                        "'%s' is not a valid distro_series.  "
                        "It should be one of: '', 'ubuntu/focal'."
                        % invalid_distro_series
                    ]
                },
            ),
            (response.status_code, json_load_bytes(response.content)),
        )

    def test_POST_deploy_sets_license_key(self):
        self.patch(node_module.Node, "_start")
        self.patch(machines_module, "get_curtin_merged_config")
        machine = factory.make_Node(
            owner=self.user,
            interface=True,
            power_type="manual",
            status=NODE_STATUS.READY,
            architecture=make_usable_architecture(self),
        )
        osystem = make_usable_osystem(self)
        distro_series = osystem["default_release"]
        license_key = factory.make_string()
        self.patch(forms, "validate_license_key").return_value = True
        response = self.client.post(
            self.get_machine_uri(machine),
            {
                "op": "deploy",
                "osystem": osystem["name"],
                "distro_series": distro_series,
                "license_key": license_key,
            },
        )
        self.assertEqual(
            (http.client.OK, machine.system_id),
            (
                response.status_code,
                json_load_bytes(response.content)["system_id"],
            ),
        )
        self.assertEqual(license_key, reload_object(machine).license_key)

    def test_POST_deploy_validates_license_key(self):
        machine = factory.make_Node_with_Interface_on_Subnet(
            owner=self.user,
            interface=True,
            power_type="manual",
            status=NODE_STATUS.READY,
            architecture=make_usable_architecture(self),
        )
        osystem = make_usable_osystem(self)
        distro_series = osystem["default_release"]
        license_key = factory.make_string()
        self.patch(forms, "validate_license_key").return_value = False
        response = self.client.post(
            self.get_machine_uri(machine),
            {
                "op": "deploy",
                "osystem": osystem["name"],
                "distro_series": distro_series,
                "license_key": license_key,
            },
        )
        self.assertEqual(
            (
                http.client.BAD_REQUEST,
                {"license_key": ["Invalid license key."]},
            ),
            (response.status_code, json_load_bytes(response.content)),
        )

    def test_POST_deploy_sets_default_distro_series(self):
        self.patch(node_module.Node, "_start")
        self.patch(machines_module, "get_curtin_merged_config")
        machine = factory.make_Node(
            owner=self.user,
            interface=True,
            power_type="manual",
            status=NODE_STATUS.READY,
            architecture=make_usable_architecture(self),
        )
        osystem = Config.objects.get_config("default_osystem")
        distro_series = Config.objects.get_config("default_distro_series")
        make_usable_osystem(
            self, osystem_name=osystem, releases=[distro_series]
        )
        response = self.client.post(
            self.get_machine_uri(machine), {"op": "deploy"}
        )
        response_info = json_load_bytes(response.content)
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(response_info["osystem"], osystem)
        self.assertEqual(response_info["distro_series"], distro_series)

    def test_POST_deploy_works_if_series_already_set(self):
        self.patch(node_module.Node, "_start")
        self.patch(machines_module, "get_curtin_merged_config")
        osystem = Config.objects.get_config("default_osystem")
        distro_series = Config.objects.get_config("default_distro_series")
        make_usable_osystem(
            self, osystem_name=osystem, releases=[distro_series]
        )
        machine = factory.make_Node(
            owner=self.user,
            interface=True,
            status=NODE_STATUS.ALLOCATED,
            power_type="manual",
            distro_series=distro_series,
            osystem=osystem,
            architecture=make_usable_architecture(self),
        )
        response = self.client.post(
            self.get_machine_uri(machine), {"op": "deploy"}
        )
        response_info = json_load_bytes(response.content)
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(response_info["osystem"], osystem)
        self.assertEqual(response_info["distro_series"], distro_series)

    def test_POST_deploy_fails_when_install_kvm_set_for_diskless(self):
        self.become_admin()
        osystem = Config.objects.get_config("default_osystem")
        distro_series = Config.objects.get_config("default_distro_series")
        make_usable_osystem(
            self, osystem_name=osystem, releases=[distro_series]
        )
        machine = factory.make_Node(
            owner=self.user,
            interface=True,
            status=NODE_STATUS.ALLOCATED,
            power_type="manual",
            distro_series=distro_series,
            osystem=osystem,
            architecture=make_usable_architecture(self),
            ephemeral_deploy=True,
        )
        response = self.client.post(
            self.get_machine_uri(machine),
            {"op": "deploy", "install_kvm": True},
        )
        self.assertEqual(http.client.BAD_REQUEST, response.status_code)
        self.assertEqual(
            b"Cannot deploy as a VM host for ephemeral deployments.",
            response.content,
        )

    def test_POST_deploy_fails_when_install_kvm_set_for_ephemeral_deploy(self):
        self.become_admin()
        osystem = Config.objects.get_config("default_osystem")
        distro_series = Config.objects.get_config("default_distro_series")
        make_usable_osystem(
            self, osystem_name=osystem, releases=[distro_series]
        )
        machine = factory.make_Node(
            owner=self.user,
            interface=True,
            status=NODE_STATUS.ALLOCATED,
            power_type="manual",
            distro_series=distro_series,
            osystem=osystem,
            architecture=make_usable_architecture(self),
            ephemeral_deploy=True,
        )
        response = self.client.post(
            self.get_machine_uri(machine),
            {"op": "deploy", "install_kvm": True},
        )
        self.assertEqual(http.client.BAD_REQUEST, response.status_code)
        self.assertEqual(
            b"Cannot deploy as a VM host for ephemeral deployments.",
            response.content,
        )

    def test_POST_deploy_fails_when_register_vmhost_set_for_diskless(self):
        self.become_admin()
        osystem = Config.objects.get_config("default_osystem")
        distro_series = Config.objects.get_config("default_distro_series")
        make_usable_osystem(
            self, osystem_name=osystem, releases=[distro_series]
        )
        machine = factory.make_Node(
            owner=self.user,
            interface=True,
            status=NODE_STATUS.ALLOCATED,
            power_type="manual",
            distro_series=distro_series,
            osystem=osystem,
            architecture=make_usable_architecture(self),
            ephemeral_deploy=True,
        )
        response = self.client.post(
            self.get_machine_uri(machine),
            {"op": "deploy", "register_vmhost": True},
        )
        self.assertEqual(http.client.BAD_REQUEST, response.status_code)
        self.assertEqual(
            b"Cannot deploy as a VM host for ephemeral deployments.",
            response.content,
        )

    def test_POST_deploy_fails_when_register_vmhost_set_for_ephemeral_deploy(
        self,
    ):
        self.become_admin()
        osystem = Config.objects.get_config("default_osystem")
        distro_series = Config.objects.get_config("default_distro_series")
        make_usable_osystem(
            self, osystem_name=osystem, releases=[distro_series]
        )
        machine = factory.make_Node(
            owner=self.user,
            interface=True,
            status=NODE_STATUS.ALLOCATED,
            power_type="manual",
            distro_series=distro_series,
            osystem=osystem,
            architecture=make_usable_architecture(self),
            ephemeral_deploy=True,
        )
        response = self.client.post(
            self.get_machine_uri(machine),
            {"op": "deploy", "register_vmhost": True},
        )
        self.assertEqual(http.client.BAD_REQUEST, response.status_code)
        self.assertEqual(
            b"Cannot deploy as a VM host for ephemeral deployments.",
            response.content,
        )

    def test_POST_deploy_sets_ephemeral_deploy(self):
        self.patch(node_module.Node, "_start")
        machine = factory.make_Node(
            owner=self.user,
            interface=True,
            power_type="manual",
            status=NODE_STATUS.READY,
            architecture=make_usable_architecture(self),
        )
        self.assertFalse(machine.ephemeral_deploy)
        response = self.client.post(
            self.get_machine_uri(machine),
            {"op": "deploy", "ephemeral_deploy": "true"},
        )
        self.assertEqual(http.client.OK, response.status_code)
        machine = reload_object(machine)
        self.assertTrue(machine.ephemeral_deploy)

    def test_POST_deploy_fails_when_preseed_not_rendered(self):
        mock_get_curtin_merged_config = self.patch(
            machines_module, "get_curtin_merged_config"
        )
        mock_get_curtin_merged_config.side_effect = Exception("error")
        osystem = Config.objects.get_config("default_osystem")
        distro_series = Config.objects.get_config("default_distro_series")
        make_usable_osystem(
            self, osystem_name=osystem, releases=[distro_series]
        )
        machine = factory.make_Node(
            owner=self.user,
            interface=True,
            status=NODE_STATUS.ALLOCATED,
            power_type="manual",
            distro_series=distro_series,
            osystem=osystem,
            architecture=make_usable_architecture(self),
        )
        response = self.client.post(
            self.get_machine_uri(machine), {"op": "deploy"}
        )
        self.assertEqual(http.client.BAD_REQUEST, response.status_code)
        self.assertEqual(b"Failed to render preseed: error", response.content)

    def test_POST_deploy_validates_hwe_kernel_with_default_distro_series(self):
        architecture = make_usable_architecture(self, subarch_name="generic")
        machine = factory.make_Node(
            owner=self.user,
            interface=True,
            power_type="manual",
            status=NODE_STATUS.READY,
            architecture=architecture,
        )
        osystem = Config.objects.get_config("default_osystem")
        distro_series = Config.objects.get_config("default_distro_series")
        make_usable_osystem(
            self, osystem_name=osystem, releases=[distro_series]
        )
        bad_hwe_kernel = "hwe-" + chr(ord(distro_series[0]) - 1)
        response = self.client.post(
            self.get_machine_uri(machine),
            {"op": "deploy", "hwe_kernel": bad_hwe_kernel},
        )
        self.assertEqual(
            (
                http.client.BAD_REQUEST,
                {
                    "hwe_kernel": [
                        "%s is not available for %s/%s on %s."
                        % (
                            bad_hwe_kernel,
                            osystem,
                            distro_series,
                            architecture,
                        )
                    ]
                },
            ),
            (response.status_code, json_load_bytes(response.content)),
        )

    def test_POST_deploy_not_allowed_statuses(self):
        osystem = make_usable_osystem(self)
        distro_series = osystem["default_release"]
        request = {"op": "deploy", "distro_series": distro_series}
        not_allowed_statuses = [
            status
            for status in NODE_STATUS_CHOICES_DICT.keys()
            if status not in [NODE_STATUS.READY, NODE_STATUS.ALLOCATED]
        ]
        for not_allowed_status in not_allowed_statuses:
            machine = factory.make_Node(
                owner=self.user,
                interface=True,
                power_type="manual",
                architecture=make_usable_architecture(self),
                status=not_allowed_status,
            )
            response = self.client.post(self.get_machine_uri(machine), request)
            self.assertEqual(http.client.CONFLICT, response.status_code)
            error_message = response.content.decode("utf-8")
            self.assertEqual(
                "Can't deploy a machine that is in the '{}' state".format(
                    NODE_STATUS_CHOICES_DICT[not_allowed_status]
                ),
                error_message,
            )

    def test_POST_deploy_stores_user_data_base64_encoded(self):
        rack_controller = factory.make_RackController()
        self.patch(
            node_module.RackControllerManager, "filter_by_url_accessible"
        ).return_value = [rack_controller]
        self.patch(node_module.Node, "_power_control_node")
        self.patch(node_module.Node, "_start_deployment")
        self.patch(node_module.Node, "_claim_auto_ips")
        self.patch(machines_module, "get_curtin_merged_config")
        self.patch(
            node_module, "get_maas_facing_server_addresses"
        ).return_value = [IPAddress("127.0.0.1"), IPAddress("::1")]
        machine = factory.make_Node_with_Interface_on_Subnet(
            owner=self.user,
            interface=True,
            power_type="virsh",
            architecture=make_usable_architecture(self),
            status=NODE_STATUS.ALLOCATED,
            bmc_connected_to=rack_controller,
        )

        # assign an IP to both the machine and the rack on the same subnet
        machine_interface = machine.get_boot_interface()
        [auto_ip] = machine_interface.ip_addresses.filter(
            alloc_type=IPADDRESS_TYPE.AUTO
        )
        ip = factory.pick_ip_in_Subnet(auto_ip.subnet)
        auto_ip.ip = ip
        auto_ip.save()
        rack_if = rack_controller.current_config.interface_set.first()
        rack_if.link_subnet(
            INTERFACE_LINK_TYPE.STATIC,
            auto_ip.subnet,
            factory.pick_ip_in_Subnet(auto_ip.subnet),
        )

        osystem = make_usable_osystem(self)
        distro_series = osystem["default_release"]
        user_data = b64encode(
            b"\xff\x00\xff\xfe\xff\xff\xfe"
            + factory.make_string().encode("ascii")
        )
        response = self.client.post(
            self.get_machine_uri(machine),
            {
                "op": "deploy",
                "user_data": user_data.decode("ascii"),
                "distro_series": distro_series,
            },
        )
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(
            user_data, NodeUserData.objects.get_user_data(machine)
        )

    def test_POST_deploy_stores_user_data_plain_text(self):
        rack_controller = factory.make_RackController()
        self.patch(
            node_module.RackControllerManager, "filter_by_url_accessible"
        ).return_value = [rack_controller]
        self.patch(node_module.Node, "_power_control_node")
        self.patch(node_module.Node, "_start_deployment")
        self.patch(node_module.Node, "_claim_auto_ips")
        self.patch(machines_module, "get_curtin_merged_config")
        self.patch(
            node_module, "get_maas_facing_server_addresses"
        ).return_value = [IPAddress("127.0.0.1"), IPAddress("::1")]
        machine = factory.make_Node_with_Interface_on_Subnet(
            owner=self.user,
            interface=True,
            power_type="virsh",
            architecture=make_usable_architecture(self),
            status=NODE_STATUS.ALLOCATED,
            bmc_connected_to=rack_controller,
        )

        # assign an IP to both the machine and the rack on the same subnet
        machine_interface = machine.get_boot_interface()
        [auto_ip] = machine_interface.ip_addresses.filter(
            alloc_type=IPADDRESS_TYPE.AUTO
        )
        ip = factory.pick_ip_in_Subnet(auto_ip.subnet)
        auto_ip.ip = ip
        auto_ip.save()
        rack_if = rack_controller.current_config.interface_set.first()
        rack_if.link_subnet(
            INTERFACE_LINK_TYPE.STATIC,
            auto_ip.subnet,
            factory.pick_ip_in_Subnet(auto_ip.subnet),
        )

        osystem = make_usable_osystem(self)
        distro_series = osystem["default_release"]
        user_data = factory.make_name("user_data")
        response = self.client.post(
            self.get_machine_uri(machine),
            {
                "op": "deploy",
                "user_data": user_data,
                "distro_series": distro_series,
            },
        )
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(
            user_data.encode(), NodeUserData.objects.get_user_data(machine)
        )

    def test_POST_deploy_passes_comment(self):
        self.patch(node_module.Node, "_start")
        self.patch(machines_module, "get_curtin_merged_config")
        rack_controller = factory.make_RackController()
        machine = factory.make_Node(
            owner=self.user,
            interface=True,
            power_type="virsh",
            status=NODE_STATUS.READY,
            architecture=make_usable_architecture(self),
            bmc_connected_to=rack_controller,
        )
        osystem = make_usable_osystem(self)
        distro_series = osystem["default_release"]
        comment = factory.make_name("comment")
        machine_start = self.patch(node_module.Machine, "start")
        machine_start.return_value = False
        self.client.post(
            self.get_machine_uri(machine),
            {
                "op": "deploy",
                "distro_series": distro_series,
                "comment": comment,
            },
        )
        self.assertThat(
            machine_start,
            MockCalledOnceWith(
                self.user,
                user_data=ANY,
                comment=comment,
                install_kvm=ANY,
                register_vmhost=ANY,
                bridge_type=ANY,
                bridge_stp=ANY,
                bridge_fd=ANY,
            ),
        )

    def test_POST_deploy_handles_missing_comment(self):
        machine = factory.make_Node(
            owner=self.user,
            interface=True,
            power_type="manual",
            status=NODE_STATUS.READY,
            architecture=make_usable_architecture(self),
        )
        osystem = make_usable_osystem(self)
        distro_series = osystem["default_release"]
        machine_start = self.patch(node_module.Machine, "start")
        self.patch(machines_module, "get_curtin_merged_config")
        machine_start.return_value = False
        self.client.post(
            self.get_machine_uri(machine),
            {"op": "deploy", "distro_series": distro_series},
        )
        self.assertThat(
            machine_start,
            MockCalledOnceWith(
                self.user,
                user_data=ANY,
                comment=None,
                install_kvm=ANY,
                register_vmhost=ANY,
                bridge_type=ANY,
                bridge_stp=ANY,
                bridge_fd=ANY,
            ),
        )

    def test_POST_deploy_doesnt_reset_power_options_bug_1569102(self):
        self.become_admin()
        self.patch(node_module.Node, "_start")
        self.patch(machines_module, "get_curtin_merged_config")
        rack_controller = factory.make_RackController()
        machine = factory.make_Node(
            owner=self.user,
            interface=True,
            power_type="virsh",
            status=NODE_STATUS.READY,
            architecture=make_usable_architecture(self),
            bmc_connected_to=rack_controller,
        )
        osystem = make_usable_osystem(self)
        distro_series = osystem["default_release"]
        machine_start = self.patch(node_module.Machine, "start")
        machine_start.return_value = False
        response = self.client.post(
            self.get_machine_uri(machine),
            {"op": "deploy", "distro_series": distro_series},
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        response_content = json_load_bytes(response.content)
        self.assertEqual("virsh", response_content["power_type"])

    def test_POST_deploy_allocates_ready_machines(self):
        self.patch(node_module.Node, "_start")
        self.patch(machines_module, "get_curtin_merged_config")
        machine = factory.make_Node(
            status=NODE_STATUS.READY,
            interface=True,
            power_type="manual",
            architecture=make_usable_architecture(self),
        )
        osystem = make_usable_osystem(self)
        distro_series = osystem["default_release"]
        request = {"op": "deploy", "distro_series": distro_series}
        response = self.client.post(self.get_machine_uri(machine), request)
        self.assertEqual(http.client.OK, response.status_code)

    def test_POST_deploy_rejects_node_owned_by_another_user(self):
        self.patch(node_module.Node, "_start")
        user2 = factory.make_User()
        machine = factory.make_Node(
            status=NODE_STATUS.READY,
            owner=user2,
            interface=True,
            power_type="manual",
            architecture=make_usable_architecture(self),
        )
        osystem = make_usable_osystem(self)
        distro_series = osystem["default_release"]
        request = {"op": "deploy", "distro_series": distro_series}
        response = self.client.post(self.get_machine_uri(machine), request)
        self.assertEqual(http.client.FORBIDDEN, response.status_code)

    def test_POST_deploy_passes_agent_name(self):
        self.patch(node_module.Node, "_start")
        self.patch(machines_module, "get_curtin_merged_config")
        machine = factory.make_Node(
            status=NODE_STATUS.READY,
            interface=True,
            power_type="manual",
            architecture=make_usable_architecture(self),
        )
        osystem = make_usable_osystem(self)
        distro_series = osystem["default_release"]
        request = {
            "op": "deploy",
            "distro_series": distro_series,
            "agent_name": factory.make_name(),
            "comment": factory.make_name(),
        }
        response = self.client.post(self.get_machine_uri(machine), request)
        self.assertEqual(http.client.OK, response.status_code)
        machine = reload_object(machine)
        self.assertEqual(request["agent_name"], machine.agent_name)

    def test_POST_deploy_passes_comment_on_acquire(self):
        self.patch(node_module.Node, "_start")
        self.patch(machines_module, "get_curtin_merged_config")
        machine_method = self.patch(node_module.Machine, "acquire")
        machine = factory.make_Node(
            status=NODE_STATUS.READY,
            owner=self.user,
            interface=True,
            power_type="manual",
            architecture=make_usable_architecture(self),
        )
        osystem = make_usable_osystem(self)
        distro_series = osystem["default_release"]
        request = {
            "op": "deploy",
            "distro_series": distro_series,
            "agent_name": factory.make_name(),
            "comment": factory.make_name(),
        }
        self.client.post(self.get_machine_uri(machine), request)
        self.assertThat(
            machine_method,
            MockCalledOnceWith(
                ANY,
                agent_name=ANY,
                bridge_all=False,
                bridge_type=BRIDGE_TYPE.STANDARD,
                bridge_fd=0,
                bridge_stp=False,
                comment=request["comment"],
            ),
        )

    def test_POST_deploy_passes_bridge_settings(self):
        self.patch(node_module.Node, "_start")
        self.patch(machines_module, "get_curtin_merged_config")
        machine_method = self.patch(node_module.Machine, "acquire")
        machine = factory.make_Node(
            status=NODE_STATUS.READY,
            owner=self.user,
            interface=True,
            power_type="manual",
            architecture=make_usable_architecture(self),
        )
        osystem = make_usable_osystem(self)
        distro_series = osystem["default_release"]
        request = {
            "op": "deploy",
            "distro_series": distro_series,
            "bridge_all": True,
            "bridge_type": BRIDGE_TYPE.OVS,
            "bridge_stp": True,
            "bridge_fd": 7,
        }
        self.client.post(self.get_machine_uri(machine), request)
        self.assertThat(
            machine_method,
            MockCalledOnceWith(
                ANY,
                agent_name=ANY,
                bridge_all=True,
                bridge_type=BRIDGE_TYPE.OVS,
                bridge_fd=7,
                bridge_stp=True,
                comment=None,
            ),
        )

    def test_POST_deploy_stores_vcenter_registration_by_default(self):
        self.become_admin()
        self.patch(node_module.Node, "_start")
        self.patch(machines_module, "get_curtin_merged_config")
        machine = factory.make_Node(
            owner=self.user,
            interface=True,
            power_type="manual",
            status=NODE_STATUS.READY,
            architecture=make_usable_architecture(self),
        )
        osystem = make_usable_osystem(self, "esxi", ["6.7"])
        distro_series = osystem["default_release"]
        response = self.client.post(
            self.get_machine_uri(machine),
            {"op": "deploy", "distro_series": distro_series},
        )
        self.assertEqual(
            (http.client.OK, machine.system_id),
            (
                response.status_code,
                json_load_bytes(response.content)["system_id"],
            ),
        )
        self.assertTrue(
            machine.nodemetadata_set.filter(
                key="vcenter_registration"
            ).exists()
        )

    def test_POST_deploy_stores_vcenter_registration_when_defined(self):
        self.become_admin()
        self.patch(node_module.Node, "_start")
        self.patch(machines_module, "get_curtin_merged_config")
        machine = factory.make_Node(
            owner=self.user,
            interface=True,
            power_type="manual",
            status=NODE_STATUS.READY,
            architecture=make_usable_architecture(self),
        )
        osystem = make_usable_osystem(self, "esxi", ["6.7"])
        distro_series = osystem["default_release"]
        response = self.client.post(
            self.get_machine_uri(machine),
            {
                "op": "deploy",
                "distro_series": distro_series,
                "vcenter_registration": True,
            },
        )
        self.assertEqual(
            (http.client.OK, machine.system_id),
            (
                response.status_code,
                json_load_bytes(response.content)["system_id"],
            ),
        )
        self.assertTrue(
            machine.nodemetadata_set.filter(
                key="vcenter_registration"
            ).exists()
        )

    def test_POST_deploy_removes_vcenter_registration_when_false(self):
        self.become_admin()
        self.patch(node_module.Node, "_start")
        self.patch(machines_module, "get_curtin_merged_config")
        machine = factory.make_Node(
            owner=self.user,
            interface=True,
            power_type="manual",
            status=NODE_STATUS.READY,
            architecture=make_usable_architecture(self),
        )
        machine.nodemetadata_set.create(
            key="vcenter_registration", value="True"
        )
        osystem = make_usable_osystem(self, "esxi", ["6.7"])
        distro_series = osystem["default_release"]
        response = self.client.post(
            self.get_machine_uri(machine),
            {
                "op": "deploy",
                "distro_series": distro_series,
                "vcenter_registration": False,
            },
        )
        self.assertEqual(
            (http.client.OK, machine.system_id),
            (
                response.status_code,
                json_load_bytes(response.content)["system_id"],
            ),
        )
        self.assertFalse(
            machine.nodemetadata_set.filter(
                key="vcenter_registration"
            ).exists()
        )

    def test_POST_deploy_sets_vcenter_registration_only_when_esxi(self):
        self.become_admin()
        self.patch(node_module.Node, "_start")
        self.patch(machines_module, "get_curtin_merged_config")
        machine = factory.make_Node(
            owner=self.user,
            interface=True,
            power_type="manual",
            status=NODE_STATUS.READY,
            architecture=make_usable_architecture(self),
        )
        osystem = make_usable_osystem(self)
        distro_series = osystem["default_release"]
        response = self.client.post(
            self.get_machine_uri(machine),
            {
                "op": "deploy",
                "distro_series": distro_series,
                "vcenter_registration": True,
            },
        )
        self.assertEqual(
            (http.client.OK, machine.system_id),
            (
                response.status_code,
                json_load_bytes(response.content)["system_id"],
            ),
        )
        self.assertFalse(
            machine.nodemetadata_set.filter(
                key="vcenter_registration"
            ).exists()
        )

    def test_POST_deploy_sets_vcenter_registration_rbac_admin(self):
        self.patch(node_module.Node, "_start")
        self.patch(machines_module, "get_curtin_merged_config")
        self.patch(auth, "validate_user_external_auth").return_value = True
        rbac = self.useFixture(RBACEnabled())
        self.become_non_local()
        # The api allows the updating of a Machine.
        machine = factory.make_Node(
            hostname="diane",
            owner=self.user,
            interface=True,
            power_type="manual",
            status=NODE_STATUS.READY,
            architecture=make_usable_architecture(self),
        )
        rbac.store.add_pool(machine.pool)
        rbac.store.allow(self.user.username, machine.pool, "admin-machines")
        osystem = make_usable_osystem(self, "esxi", ["6.7"])
        distro_series = osystem["default_release"]
        response = self.client.post(
            self.get_machine_uri(machine),
            {
                "op": "deploy",
                "distro_series": distro_series,
                "vcenter_registration": True,
            },
        )
        self.assertEqual(
            (http.client.OK, machine.system_id),
            (
                response.status_code,
                json_load_bytes(response.content)["system_id"],
            ),
        )
        self.assertTrue(
            machine.nodemetadata_set.filter(
                key="vcenter_registration"
            ).exists()
        )

    def test_POST_deploy_doesnt_set_vcenter_registration_rbac_user(self):
        self.patch(node_module.Node, "_start")
        self.patch(machines_module, "get_curtin_merged_config")
        self.patch(auth, "validate_user_external_auth").return_value = True
        rbac = self.useFixture(RBACEnabled())
        self.become_non_local()
        # The api allows the updating of a Machine.
        machine = factory.make_Node(
            owner=self.user,
            interface=True,
            power_type="manual",
            status=NODE_STATUS.READY,
            architecture=make_usable_architecture(self),
        )
        rbac.store.add_pool(machine.pool)
        rbac.store.allow(self.user.username, machine.pool, "deploy-machines")
        osystem = make_usable_osystem(self, "esxi", ["6.7"])
        distro_series = osystem["default_release"]
        response = self.client.post(
            self.get_machine_uri(machine),
            {
                "op": "deploy",
                "distro_series": distro_series,
                "vcenter_registration": True,
            },
        )
        self.assertEqual(
            (http.client.OK, machine.system_id),
            (
                response.status_code,
                json_load_bytes(response.content)["system_id"],
            ),
        )
        self.assertFalse(
            machine.nodemetadata_set.filter(
                key="vcenter_registration"
            ).exists()
        )

    def test_POST_deploy_distro_series(self):
        self.patch(node_module.Node, "_start")
        self.patch(machines_module, "get_curtin_merged_config")
        self.patch(auth, "validate_user_external_auth").return_value = True
        # The api allows the updating of a Machine.
        machine = factory.make_Node(
            owner=self.user,
            interface=True,
            power_type="manual",
            status=NODE_STATUS.READY,
            architecture=make_usable_architecture(self),
        )
        response = self.client.post(
            self.get_machine_uri(machine),
            {"op": "deploy", "distro_series": "ubuntu/focal"},
        )
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(
            machine.system_id, json_load_bytes(response.content)["system_id"]
        )

    def test_POST_deploy_enable_hw_sync_defaults_to_False(self):
        self.patch(node_module.Node, "_start")
        self.patch(machines_module, "get_curtin_merged_config")
        machine = factory.make_Node(
            owner=self.user,
            interface=True,
            power_type="manual",
            status=NODE_STATUS.READY,
            architecture=make_usable_architecture(self),
        )
        response = self.client.post(
            self.get_machine_uri(machine),
            {"op": "deploy", "distro_series": "ubuntu/focal"},
        )
        self.assertEqual(http.client.OK, response.status_code)
        machine.refresh_from_db()
        self.assertFalse(machine.enable_hw_sync)

    def test_POST_deploy_set_enable_hardware_sync(self):
        self.patch(node_module.Node, "_start")
        self.patch(machines_module, "get_curtin_merged_config")
        machine = factory.make_Node(
            owner=self.user,
            interface=True,
            power_type="manual",
            status=NODE_STATUS.READY,
            architecture=make_usable_architecture(self),
        )
        osystem = make_usable_osystem(
            self, osystem_name="ubuntu", releases=["focal"]
        )
        response = self.client.post(
            self.get_machine_uri(machine),
            {
                "op": "deploy",
                "distro_series": "{}/{}".format(
                    osystem["name"], osystem["default_release"]
                ),
                "enable_hw_sync": True,
            },
        )
        self.assertEqual(http.client.OK, response.status_code)
        machine.refresh_from_db()
        self.assertTrue(machine.enable_hw_sync)

    def test_POST_release_releases_owned_machine(self):
        self.patch(node_module.Machine, "_stop")
        owned_statuses = [NODE_STATUS.RESERVED, NODE_STATUS.ALLOCATED]
        owned_machines = [
            factory.make_Node(
                owner=self.user,
                status=status,
                power_type="virsh",
                power_state=POWER_STATE.ON,
            )
            for status in owned_statuses
        ]
        responses = [
            self.client.post(self.get_machine_uri(machine), {"op": "release"})
            for machine in owned_machines
        ]
        self.assertEqual(
            [http.client.OK] * len(owned_machines),
            [response.status_code for response in responses],
        )
        self.assertCountEqual(
            [NODE_STATUS.RELEASING] * len(owned_machines),
            [
                machine.status
                for machine in reload_objects(Node, owned_machines)
            ],
        )

    def test_POST_release_fails_with_locked(self):
        machine = factory.make_Node(
            owner=self.user,
            status=NODE_STATUS.ALLOCATED,
            locked=True,
            power_type="virsh",
            power_state=POWER_STATE.ON,
        )
        response = self.client.post(
            self.get_machine_uri(machine), {"op": "release"}
        )
        self.assertEqual(http.client.FORBIDDEN, response.status_code)

    def test_POST_release_starts_disk_erasing(self):
        self.patch(node_module.Node, "_start").return_value = defer.succeed(
            None
        )
        machine = factory.make_Node(
            owner=self.user,
            status=NODE_STATUS.DEPLOYED,
            power_type="virsh",
            power_state=POWER_STATE.OFF,
        )
        response = self.client.post(
            self.get_machine_uri(machine), {"op": "release", "erase": "true"}
        )
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(
            NODE_STATUS.DISK_ERASING, reload_object(machine).status
        )

    def test_POST_release_releases_failed_machine(self):
        self.patch(node_module.Machine, "_stop")
        owned_machine = factory.make_Node(
            owner=self.user,
            status=NODE_STATUS.FAILED_DEPLOYMENT,
            power_type="ipmi",
            power_state=POWER_STATE.ON,
        )
        response = self.client.post(
            self.get_machine_uri(owned_machine), {"op": "release"}
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        owned_machine = Machine.objects.get(id=owned_machine.id)
        self.expectThat(owned_machine.status, Equals(NODE_STATUS.RELEASING))
        self.expectThat(owned_machine.owner, Equals(self.user))

    def test_POST_release_does_nothing_for_unowned_machine(self):
        machine = factory.make_Node_with_Interface_on_Subnet(
            status=NODE_STATUS.READY, owner=self.user
        )
        response = self.client.post(
            self.get_machine_uri(machine), {"op": "release"}
        )
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(NODE_STATUS.READY, reload_object(machine).status)

    def test_POST_release_rejects_other_node_types(self):
        node = factory.make_Node_with_Interface_on_Subnet(
            owner=self.user,
            node_type=factory.pick_choice(
                NODE_TYPE_CHOICES, but_not=[NODE_TYPE.MACHINE]
            ),
        )
        response = self.client.post(
            self.get_machine_uri(node), {"op": "release"}
        )
        self.assertEqual(
            http.client.NOT_FOUND, response.status_code, response.content
        )

    def test_POST_release_on_ready_is_noop(self):
        machine = factory.make_Node(status=NODE_STATUS.READY)
        response = self.client.post(
            self.get_machine_uri(machine), {"op": "release"}
        )
        self.assertEqual(http.client.OK, response.status_code)

    def test_POST_release_fails_for_other_machine_states(self):
        releasable_statuses = {
            NODE_STATUS.RELEASING,
            NODE_STATUS.READY,
        } | RELEASABLE_STATUSES
        unreleasable_statuses = [
            status
            for status in map_enum(NODE_STATUS).values()
            if status not in releasable_statuses
        ]
        machines = [
            factory.make_Node(status=status, owner=self.user)
            for status in unreleasable_statuses
        ]
        responses = [
            self.client.post(self.get_machine_uri(machine), {"op": "release"})
            for machine in machines
        ]
        self.assertEqual(
            [http.client.CONFLICT] * len(unreleasable_statuses),
            [response.status_code for response in responses],
        )
        self.assertCountEqual(
            unreleasable_statuses,
            [machine.status for machine in reload_objects(Node, machines)],
        )

    def test_POST_release_in_wrong_state_reports_current_state(self):
        machine = factory.make_Node(
            status=NODE_STATUS.RETIRED, owner=self.user
        )
        response = self.client.post(
            self.get_machine_uri(machine), {"op": "release"}
        )
        self.assertEqual(
            (
                http.client.CONFLICT,
                "Machine cannot be released in its current state ('Retired').",
            ),
            (
                response.status_code,
                response.content.decode(settings.DEFAULT_CHARSET),
            ),
        )

    def test_POST_release_rejects_request_from_unauthorized_user(self):
        machine = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=factory.make_User()
        )
        response = self.client.post(
            self.get_machine_uri(machine), {"op": "release"}
        )
        self.assertEqual(http.client.FORBIDDEN, response.status_code)
        self.assertEqual(NODE_STATUS.ALLOCATED, reload_object(machine).status)

    def test_POST_release_allows_admin_to_release_anyones_machine(self):
        self.patch(node_module.Machine, "_stop")
        machine = factory.make_Node(
            status=NODE_STATUS.ALLOCATED,
            owner=factory.make_User(),
            power_type="ipmi",
            power_state=POWER_STATE.ON,
        )
        self.become_admin()
        response = self.client.post(
            self.get_machine_uri(machine), {"op": "release"}
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        self.assertEqual(NODE_STATUS.RELEASING, reload_object(machine).status)

    def test_POST_release_combines_with_allocate(self):
        self.patch(node_module.Machine, "_stop")
        machine = factory.make_Node(
            status=NODE_STATUS.READY,
            power_type="ipmi",
            power_state=POWER_STATE.ON,
            with_boot_disk=True,
        )
        response = self.client.post(
            reverse("machines_handler"), {"op": "allocate"}
        )
        self.assertEqual(NODE_STATUS.ALLOCATED, reload_object(machine).status)
        machine_uri = json_load_bytes(response.content)["resource_uri"]
        response = self.client.post(machine_uri, {"op": "release"})
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        self.assertEqual(NODE_STATUS.RELEASING, reload_object(machine).status)

    def test_POST_allocate_passes_comment(self):
        factory.make_Node(
            status=NODE_STATUS.READY,
            power_type="ipmi",
            power_state=POWER_STATE.ON,
            with_boot_disk=True,
        )
        machine_method = self.patch(node_module.Machine, "acquire")
        comment = factory.make_name("comment")
        self.client.post(
            reverse("machines_handler"), {"op": "allocate", "comment": comment}
        )
        self.assertThat(
            machine_method,
            MockCalledOnceWith(
                ANY,
                agent_name=ANY,
                bridge_all=False,
                bridge_type=BRIDGE_TYPE.STANDARD,
                bridge_fd=False,
                bridge_stp=False,
                comment=comment,
            ),
        )

    def test_POST_allocate_handles_missing_comment(self):
        factory.make_Node(
            status=NODE_STATUS.READY,
            power_type="ipmi",
            power_state=POWER_STATE.ON,
            with_boot_disk=True,
        )
        machine_method = self.patch(node_module.Machine, "acquire")
        self.client.post(reverse("machines_handler"), {"op": "allocate"})
        self.assertThat(
            machine_method,
            MockCalledOnceWith(
                ANY,
                agent_name=ANY,
                bridge_all=False,
                bridge_type=BRIDGE_TYPE.STANDARD,
                bridge_fd=0,
                bridge_stp=False,
                comment=None,
            ),
        )

    def test_POST_release_frees_hwe_kernel(self):
        self.patch(node_module.Machine, "_stop")
        machine = factory.make_Node(
            owner=self.user,
            status=NODE_STATUS.ALLOCATED,
            power_type="ipmi",
            power_state=POWER_STATE.ON,
            hwe_kernel="hwe-v",
        )
        self.assertEqual("hwe-v", reload_object(machine).hwe_kernel)
        response = self.client.post(
            self.get_machine_uri(machine), {"op": "release"}
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        self.assertEqual(NODE_STATUS.RELEASING, reload_object(machine).status)
        self.assertIsNone(reload_object(machine).hwe_kernel)

    def test_POST_release_passes_comment(self):
        machine = factory.make_Node(
            status=NODE_STATUS.ALLOCATED,
            owner=factory.make_User(),
            power_type="ipmi",
            power_state=POWER_STATE.OFF,
        )
        self.become_admin()
        comment = factory.make_name("comment")
        machine_release = self.patch(node_module.Machine, "release_or_erase")
        self.client.post(
            self.get_machine_uri(machine),
            {"op": "release", "comment": comment},
        )
        self.assertThat(
            machine_release,
            MockCalledOnceWith(
                self.user,
                comment,
                erase=False,
                quick_erase=None,
                secure_erase=None,
                force=None,
            ),
        )

    def test_POST_release_passes_erase_options(self):
        machine = factory.make_Node(
            status=NODE_STATUS.ALLOCATED,
            owner=factory.make_User(),
            power_type="ipmi",
            power_state=POWER_STATE.OFF,
        )
        self.become_admin()
        secure_erase = factory.pick_bool()
        quick_erase = factory.pick_bool()
        machine_release = self.patch(node_module.Machine, "release_or_erase")
        self.client.post(
            self.get_machine_uri(machine),
            {
                "op": "release",
                "erase": True,
                "secure_erase": secure_erase,
                "quick_erase": quick_erase,
            },
        )
        self.assertThat(
            machine_release,
            MockCalledOnceWith(
                self.user,
                None,
                erase=True,
                quick_erase=quick_erase,
                secure_erase=secure_erase,
                force=None,
            ),
        )

    def test_POST_release_passes_force_option(self):
        machine = factory.make_Node(
            status=NODE_STATUS.ALLOCATED,
            owner=factory.make_User(),
            power_type="ipmi",
            power_state=POWER_STATE.OFF,
        )
        self.become_admin()
        force = factory.pick_bool()
        machine_release = self.patch(node_module.Machine, "release_or_erase")
        self.client.post(
            self.get_machine_uri(machine), {"op": "release", "force": force}
        )
        self.assertThat(
            machine_release,
            MockCalledOnceWith(
                self.user,
                None,
                erase=False,
                quick_erase=None,
                secure_erase=None,
                force=force,
            ),
        )

    def test_POST_release_handles_missing_comment(self):
        machine = factory.make_Node(
            status=NODE_STATUS.ALLOCATED,
            owner=factory.make_User(),
            power_type="ipmi",
            power_state=POWER_STATE.OFF,
        )
        self.become_admin()
        machine_release = self.patch(node_module.Machine, "release_or_erase")
        self.client.post(self.get_machine_uri(machine), {"op": "release"})
        self.assertThat(
            machine_release,
            MockCalledOnceWith(
                self.user,
                None,
                erase=False,
                quick_erase=None,
                secure_erase=None,
                force=None,
            ),
        )

    def test_POST_commission_commissions_machine(self):
        self.patch(node_module.Node, "_start").return_value = defer.succeed(
            None
        )
        machine = factory.make_Node(
            status=NODE_STATUS.READY,
            owner=factory.make_User(),
            power_state=POWER_STATE.OFF,
            interface=True,
        )
        self.become_admin()
        response = self.client.post(
            self.get_machine_uri(machine), {"op": "commission"}
        )
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(
            NODE_STATUS.COMMISSIONING, reload_object(machine).status
        )

    def test_POST_commission_commissions_machine_with_options(self):
        load_builtin_scripts()
        factory.make_Script(
            script_type=SCRIPT_TYPE.COMMISSIONING, tags=["bmc-config"]
        )
        self.patch(node_module.Node, "_start").return_value = defer.succeed(
            None
        )
        machine = factory.make_Node(
            status=NODE_STATUS.READY,
            owner=factory.make_User(),
            power_state=POWER_STATE.OFF,
            interface=True,
        )
        self.become_admin()

        commissioning_scripts = [
            factory.make_Script(script_type=SCRIPT_TYPE.COMMISSIONING)
            for _ in range(10)
        ]
        commissioning_script_selected_by_tag = choice(commissioning_scripts)
        commissioning_script_selected_by_name = choice(commissioning_scripts)
        expected_commissioning_scripts = list(NODE_INFO_SCRIPTS)
        expected_commissioning_scripts.append(
            commissioning_script_selected_by_tag.name
        )
        expected_commissioning_scripts.append(
            commissioning_script_selected_by_name.name
        )

        testing_scripts = [
            factory.make_Script(script_type=SCRIPT_TYPE.TESTING)
            for _ in range(10)
        ]
        testing_script_selected_by_tag = choice(testing_scripts)
        testing_script_selected_by_name = choice(testing_scripts)
        expected_testing_scripts = [
            testing_script_selected_by_tag.name,
            testing_script_selected_by_name.name,
        ]

        response = self.client.post(
            self.get_machine_uri(machine),
            {
                "op": "commission",
                "enable_ssh": "true",
                "skip_bmc_config": 1,
                "skip_networking": 1,
                "commissioning_scripts": ",".join(
                    [
                        choice(
                            [
                                tag
                                for tag in commissioning_script_selected_by_tag.tags
                                if "tag" in tag
                            ]
                        ),
                        commissioning_script_selected_by_name.name,
                    ]
                ),
                "testing_scripts": ",".join(
                    [
                        choice(
                            [
                                tag
                                for tag in testing_script_selected_by_tag.tags
                                if "tag" in tag
                            ]
                        ),
                        testing_script_selected_by_name.name,
                    ]
                ),
            },
        )
        self.assertEqual(http.client.OK, response.status_code)
        machine = reload_object(machine)
        commissioning_script_set = machine.current_commissioning_script_set
        testing_script_set = machine.current_testing_script_set
        self.assertTrue(machine.enable_ssh)
        self.assertTrue(machine.skip_networking)
        self.assertCountEqual(
            set(expected_commissioning_scripts),
            [script_result.name for script_result in commissioning_script_set],
        )
        self.assertCountEqual(
            set(expected_testing_scripts),
            [script_result.name for script_result in testing_script_set],
        )

    def test_POST_lock_deployed(self):
        machine = factory.make_Node(
            status=NODE_STATUS.DEPLOYED, owner=self.user
        )
        response = self.client.post(
            self.get_machine_uri(machine), {"op": "lock"}
        )
        self.assertEqual(http.client.OK, response.status_code)
        machine = reload_object(machine)
        self.assertTrue(machine.locked)

    def test_POST_lock_with_comment(self):
        machine = factory.make_Node(
            status=NODE_STATUS.DEPLOYED, owner=self.user
        )
        node_lock = self.patch(node_module.Node, "lock")
        comment = factory.make_name("comment")
        self.client.post(
            self.get_machine_uri(machine), {"op": "lock", "comment": comment}
        )
        self.assertThat(
            node_lock, MockCalledOnceWith(self.user, comment=comment)
        )

    def test_POST_lock_not_deployed(self):
        machine = factory.make_Node(status=NODE_STATUS.READY, owner=self.user)
        response = self.client.post(
            self.get_machine_uri(machine), {"op": "lock"}
        )
        self.assertEqual(http.client.CONFLICT, response.status_code)
        machine = reload_object(machine)
        self.assertFalse(machine.locked)

    def test_POST_lock_locked(self):
        machine = factory.make_Node(
            status=NODE_STATUS.DEPLOYED, locked=True, owner=self.user
        )
        response = self.client.post(
            self.get_machine_uri(machine), {"op": "lock"}
        )
        self.assertEqual(http.client.CONFLICT, response.status_code)

    def test_POST_unlock(self):
        machine = factory.make_Node(locked=True, owner=self.user)
        response = self.client.post(
            self.get_machine_uri(machine), {"op": "unlock"}
        )
        self.assertEqual(http.client.OK, response.status_code)
        machine = reload_object(machine)
        self.assertFalse(machine.locked)

    def test_POST_unlock_with_comment(self):
        machine = factory.make_Node(locked=True, owner=self.user)
        node_unlock = self.patch(node_module.Node, "unlock")
        comment = factory.make_name("comment")
        self.client.post(
            self.get_machine_uri(machine), {"op": "unlock", "comment": comment}
        )
        self.assertThat(
            node_unlock, MockCalledOnceWith(self.user, comment=comment)
        )

    def test_POST_unlock_unlocked(self):
        machine = factory.make_Node(owner=self.user)
        response = self.client.post(
            self.get_machine_uri(machine), {"op": "unlock"}
        )
        self.assertEqual(http.client.CONFLICT, response.status_code)

    def test_PUT_updates_machine_superuser(self):
        self.become_admin()
        # The api allows the updating of a Machine.
        machine = factory.make_Node(
            hostname="diane",
            owner=self.user,
            architecture=make_usable_architecture(self),
            power_type="manual",
        )
        new_description = factory.make_name("description")
        response = self.client.put(
            self.get_machine_uri(machine),
            {"hostname": "francis", "description": new_description},
        )
        parsed_result = json_load_bytes(response.content)

        self.assertEqual(http.client.OK, response.status_code)
        domain_name = Domain.objects.get_default_domain().name
        self.assertEqual("francis.%s" % domain_name, parsed_result["fqdn"])
        self.assertEqual(new_description, parsed_result["description"])
        self.assertEqual(new_description, reload_object(machine).description)
        self.assertEqual(0, Machine.objects.filter(hostname="diane").count())
        self.assertEqual(1, Machine.objects.filter(hostname="francis").count())

    def test_PUT_not_updates_machine_non_superuser(self):
        machine = factory.make_Node(
            hostname="diane",
            owner=self.user,
            architecture=make_usable_architecture(self),
            power_type="manual",
        )
        response = self.client.put(
            self.get_machine_uri(machine), {"hostname": "francis"}
        )

        self.assertEqual(http.client.FORBIDDEN, response.status_code)

    def test_PUT_updates_machine_rbac_pool_admin(self):
        self.patch(auth, "validate_user_external_auth").return_value = True
        rbac = self.useFixture(RBACEnabled())
        self.become_non_local()
        # The api allows the updating of a Machine.
        machine = factory.make_Node(
            hostname="diane",
            owner=self.user,
            architecture=make_usable_architecture(self),
            power_type="manual",
        )
        rbac.store.add_pool(machine.pool)
        rbac.store.allow(self.user.username, machine.pool, "admin-machines")
        response = self.client.put(
            self.get_machine_uri(machine), {"hostname": "francis"}
        )
        parsed_result = json_load_bytes(response.content)

        self.assertEqual(http.client.OK, response.status_code)
        domain_name = Domain.objects.get_default_domain().name
        self.assertEqual("francis.%s" % domain_name, parsed_result["fqdn"])
        self.assertEqual(0, Machine.objects.filter(hostname="diane").count())
        self.assertEqual(1, Machine.objects.filter(hostname="francis").count())

    def test_PUT_not_updates_machine_rbac_pool_user(self):
        self.patch(auth, "validate_user_external_auth").return_value = True
        rbac = self.useFixture(RBACEnabled())
        self.become_non_local()
        # The api allows the updating of a Machine.
        machine = factory.make_Node(
            hostname="diane",
            owner=self.user,
            architecture=make_usable_architecture(self),
            power_type="manual",
        )
        rbac.store.add_pool(machine.pool)
        rbac.store.allow(self.user.username, machine.pool, "deploy-machines")
        response = self.client.put(
            self.get_machine_uri(machine), {"hostname": "francis"}
        )
        self.assertEqual(http.client.FORBIDDEN, response.status_code)

    def test_PUT_denied_if_locked(self):
        self.become_admin()
        machine = factory.make_Node(
            hostname="foo",
            owner=self.user,
            status=NODE_STATUS.DEPLOYED,
            locked=True,
            architecture=make_usable_architecture(self),
            power_type="manual",
        )
        response = self.client.put(
            self.get_machine_uri(machine), {"hostname": "bar"}
        )
        self.assertEqual(http.client.FORBIDDEN, response.status_code)

    def test_PUT_omitted_hostname(self):
        self.become_admin()
        hostname = factory.make_name("hostname")
        arch = make_usable_architecture(self)
        machine = factory.make_Node(
            hostname=hostname,
            owner=self.user,
            architecture=arch,
            power_type="manual",
        )
        response = self.client.put(
            self.get_machine_uri(machine), {"architecture": arch}
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        self.assertTrue(Machine.objects.filter(hostname=hostname).exists())

    def test_PUT_rejects_other_node_types(self):
        self.become_admin()
        node = factory.make_Node_with_Interface_on_Subnet(
            owner=self.user,
            node_type=factory.pick_choice(
                NODE_TYPE_CHOICES, but_not=[NODE_TYPE.MACHINE]
            ),
        )
        response = self.client.put(self.get_machine_uri(node))
        self.assertEqual(
            http.client.NOT_FOUND, response.status_code, response.content
        )

    def test_PUT_ignores_unknown_fields(self):
        self.become_admin()
        machine = factory.make_Node(
            owner=self.user,
            architecture=make_usable_architecture(self),
            power_type="manual",
        )
        field = factory.make_string()
        response = self.client.put(
            self.get_machine_uri(machine), {field: factory.make_string()}
        )

        self.assertEqual(http.client.OK, response.status_code)

    def test_PUT_admin_can_change_power_type(self):
        self.become_admin()
        original_power_type = "ipmi"
        new_power_type = "openbmc"
        machine = factory.make_Node(
            owner=self.user,
            power_type=original_power_type,
            architecture=make_usable_architecture(self),
            interface=True,
        )
        response = self.client.put(
            self.get_machine_uri(machine),
            {
                "power_type": new_power_type,
                "power_parameters_skip_check": "true",
            },
        )

        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(new_power_type, reload_object(machine).power_type)

    def test_PUT_non_admin_cannot_change_power_type(self):
        original_power_type = "ipmi"
        new_power_type = "openbmc"
        machine = factory.make_Node(
            owner=self.user, power_type=original_power_type
        )
        response = self.client.put(
            self.get_machine_uri(machine), {"power_type": new_power_type}
        )

        self.assertEqual(http.client.FORBIDDEN, response.status_code)
        self.assertEqual(
            original_power_type, reload_object(machine).power_type
        )

    def test_resource_uri_points_back_at_machine(self):
        self.become_admin()
        # When a Machine is returned by the API, the field 'resource_uri'
        # provides the URI for this Machine.
        machine = factory.make_Node(
            hostname="diane",
            owner=self.user,
            architecture=make_usable_architecture(self),
            power_type="manual",
        )
        response = self.client.put(
            self.get_machine_uri(machine), {"hostname": "francis"}
        )
        parsed_result = json_load_bytes(response.content)

        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(
            reverse("machine_handler", args=[parsed_result["system_id"]]),
            parsed_result["resource_uri"],
        )

    def test_get_token_with_token(self):
        self.become_admin()
        machine = factory.make_Node()
        token = NodeKey.objects.get_token_for_node(machine)
        response = self.client.get(
            self.get_machine_uri(machine), {"op": "get_token"}
        )
        self.assertEqual(
            json_load_bytes(response.content),
            {
                "token_key": token.key,
                "token_secret": token.secret,
                "consumer_key": token.consumer.key,
            },
        )

    def test_get_token_no_token(self):
        self.become_admin()
        machine = factory.make_Node()
        response = self.client.get(
            self.get_machine_uri(machine), {"op": "get_token"}
        )
        self.assertIsNone(json_load_bytes(response.content))

    def test_get_token_no_admin(self):
        machine = factory.make_Node()
        NodeKey.objects.get_token_for_node(machine)
        response = self.client.get(
            self.get_machine_uri(machine), {"op": "get_token"}
        )
        self.assertEqual(http.client.FORBIDDEN, response.status_code)

    def test_PUT_rejects_invalid_data(self):
        # If the data provided to update a machine is invalid, a 'Bad request'
        # response is returned.
        self.become_admin()
        machine = factory.make_Node(
            hostname="diane",
            owner=self.user,
            architecture=make_usable_architecture(self),
            power_type="manual",
        )
        response = self.client.put(
            self.get_machine_uri(machine), {"hostname": "."}
        )
        parsed_result = json_load_bytes(response.content)

        self.assertEqual(http.client.BAD_REQUEST, response.status_code)
        self.assertEqual(
            {
                "hostname": [
                    "DNS name contains an empty label.",
                    "Nonexistant domain.",
                ]
            },
            parsed_result,
        )

    def test_PUT_refuses_to_update_nonexistent_machine(self):
        # When updating a Machine, the api returns a 'Not Found' (404) error
        # if no machine is found.
        self.become_admin()
        url = reverse("machine_handler", args=["invalid-uuid"])
        response = self.client.put(url)

        self.assertEqual(http.client.NOT_FOUND, response.status_code)

    def test_PUT_updates_power_parameters_field(self):
        # The api allows the updating of a Machine's power_parameters field.
        self.become_admin()
        machine = factory.make_Node(
            owner=self.user,
            power_type="virsh",
            architecture=make_usable_architecture(self),
        )
        # Create a power_parameter valid for the selected power_type.
        new_power_id = factory.make_name("power_id")
        new_power_pass = factory.make_name("power_pass")
        new_power_address = factory.make_ipv4_address()
        response = self.client.put(
            self.get_machine_uri(machine),
            {
                "power_parameters_power_id": new_power_id,
                "power_parameters_power_pass": new_power_pass,
                "power_parameters_power_address": new_power_address,
            },
        )

        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(
            {
                "power_id": new_power_id,
                "power_pass": new_power_pass,
                "power_address": new_power_address,
            },
            reload_object(machine).get_power_parameters(),
        )

    def test_PUT_updates_cpu_memory(self):
        self.become_admin()
        machine = factory.make_Node(
            owner=self.user,
            architecture=make_usable_architecture(self),
            power_type="manual",
        )
        response = self.client.put(
            self.get_machine_uri(machine), {"cpu_count": 1, "memory": 1024}
        )
        self.assertEqual(http.client.OK, response.status_code)
        machine = reload_object(machine)
        self.assertEqual(1, machine.cpu_count)
        self.assertEqual(1024, machine.memory)

    def test_PUT_updates_power_parameters_rejects_unknown_param(self):
        self.become_admin()
        power_parameters = {factory.make_string(): factory.make_string()}
        machine = factory.make_Node(
            owner=self.user,
            power_type="manual",
            power_parameters=power_parameters,
            architecture=make_usable_architecture(self),
        )
        response = self.client.put(
            self.get_machine_uri(machine),
            {"power_parameters_unknown_param": factory.make_string()},
        )

        self.assertEqual(
            (
                http.client.BAD_REQUEST,
                {"power_parameters": ["Unknown parameter(s): unknown_param."]},
            ),
            (response.status_code, json_load_bytes(response.content)),
        )
        self.assertEqual(
            power_parameters, reload_object(machine).get_power_parameters()
        )

    def test_PUT_updates_power_type_default_resets_params(self):
        # If one sets power_type to empty, power_parameter gets
        # reset by default (if skip_check is not set).
        self.become_admin()
        power_parameters = {factory.make_string(): factory.make_string()}
        machine = factory.make_Node(
            owner=self.user,
            power_type="manual",
            power_parameters=power_parameters,
            architecture=make_usable_architecture(self),
        )
        response = self.client.put(
            self.get_machine_uri(machine), {"power_type": ""}
        )

        machine = reload_object(machine)
        self.assertEqual(
            (
                http.client.OK,
                machine.power_type,
                machine.get_power_parameters(),
            ),
            (response.status_code, "", {}),
        )

    def test_PUT_updates_power_type_empty_rejects_params(self):
        # If one sets power_type to empty, one cannot set power_parameters.
        self.become_admin()
        power_parameters = {factory.make_string(): factory.make_string()}
        machine = factory.make_Node(
            owner=self.user,
            power_type="manual",
            power_parameters=power_parameters,
            architecture=make_usable_architecture(self),
        )
        new_param = factory.make_string()
        response = self.client.put(
            self.get_machine_uri(machine),
            {"power_type": "", "power_parameters_address": new_param},
        )

        machine = reload_object(machine)
        self.assertEqual(
            (
                http.client.BAD_REQUEST,
                {"power_parameters": ["Unknown parameter(s): address."]},
            ),
            (response.status_code, json_load_bytes(response.content)),
        )
        self.assertEqual(
            power_parameters, reload_object(machine).get_power_parameters()
        )

    def test_PUT_updates_power_type_empty_skip_check_to_force_params(self):
        # If one sets power_type to empty, it is possible to pass
        # power_parameter_skip_check='true' to force power_parameters.
        # XXX bigjools 2014-01-21 Why is this necessary?
        self.become_admin()
        power_parameters = {factory.make_string(): factory.make_string()}
        machine = factory.make_Node(
            owner=self.user,
            power_type="manual",
            power_parameters=power_parameters,
            architecture=make_usable_architecture(self),
        )
        new_param = factory.make_string()
        response = self.client.put(
            self.get_machine_uri(machine),
            {
                "power_type": "",
                "power_parameters_param": new_param,
                "power_parameters_skip_check": "true",
            },
        )

        machine = reload_object(machine)
        self.assertEqual(
            (
                http.client.OK,
                machine.power_type,
                machine.get_power_parameters(),
            ),
            (response.status_code, "", {"param": new_param}),
        )

    def test_PUT_updates_power_parameters_skip_ckeck(self):
        # With power_parameters_skip_check, arbitrary data
        # can be put in a Machine's power_parameter field.
        self.become_admin()
        machine = factory.make_Node(
            owner=self.user,
            architecture=make_usable_architecture(self),
            power_parameters={},
        )
        new_param = factory.make_string()
        new_value = factory.make_string()
        response = self.client.put(
            self.get_machine_uri(machine),
            {
                "power_parameters_%s" % new_param: new_value,
                "power_parameters_skip_check": "true",
            },
        )

        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(
            {new_param: new_value},
            reload_object(machine).get_power_parameters(),
        )

    def test_PUT_updates_power_parameters_empty_string(self):
        self.become_admin()
        power_parameters = {
            "power_address": factory.make_ip_address(),
            "power_id": factory.make_name("power_id"),
            "power_pass": factory.make_name("power_pass"),
        }
        machine = factory.make_Node(
            owner=self.user,
            power_type="virsh",
            power_parameters=power_parameters,
            architecture=make_usable_architecture(self),
        )
        response = self.client.put(
            self.get_machine_uri(machine), {"power_parameters_power_pass": ""}
        )

        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(
            "", reload_object(machine).get_power_parameters()["power_pass"]
        )

    def test_PUT_sets_zone(self):
        self.become_admin()
        new_zone = factory.make_Zone()
        machine = factory.make_Node(
            architecture=make_usable_architecture(self), power_type="manual"
        )

        response = self.client.put(
            self.get_machine_uri(machine), {"zone": new_zone.name}
        )

        self.assertEqual(http.client.OK, response.status_code)
        machine = reload_object(machine)
        self.assertEqual(new_zone, machine.zone)

    def test_PUT_does_not_set_zone_if_not_present(self):
        self.become_admin()
        new_name = factory.make_name()
        machine = factory.make_Node(
            architecture=make_usable_architecture(self), power_type="manual"
        )
        old_zone = machine.zone

        response = self.client.put(
            self.get_machine_uri(machine), {"hostname": new_name}
        )

        self.assertEqual(http.client.OK, response.status_code)
        machine = reload_object(machine)
        self.assertEqual(
            (old_zone, new_name), (machine.zone, machine.hostname)
        )

    def test_PUT_clears_zone(self):
        self.skipTest(
            "XXX: JeroenVermeulen 2013-12-11 bug=1259872: Clearing the "
            "zone field does not work..."
        )

        self.become_admin()
        machine = factory.make_Node(zone=factory.make_Zone())

        response = self.client.put(self.get_machine_uri(machine), {"zone": ""})

        self.assertEqual(http.client.OK, response.status_code)
        machine = reload_object(machine)
        self.assertIsNone(machine.zone)

    def test_PUT_without_zone_leaves_zone_unchanged(self):
        self.become_admin()
        zone = factory.make_Zone()
        machine = factory.make_Node(
            zone=zone,
            architecture=make_usable_architecture(self),
            power_type="manual",
        )

        response = self.client.put(self.get_machine_uri(machine), {})

        self.assertEqual(http.client.OK, response.status_code)
        machine = reload_object(machine)
        self.assertEqual(zone, machine.zone)

    def test_PUT_requires_admin(self):
        machine = factory.make_Node(
            owner=self.user, architecture=make_usable_architecture(self)
        )
        # PUT the machine with no arguments - should get FORBIDDEN
        response = self.client.put(self.get_machine_uri(machine), {})
        self.assertEqual(http.client.FORBIDDEN, response.status_code)

    def test_PUT_zone_change_requires_admin(self):
        new_zone = factory.make_Zone()
        machine = factory.make_Node(
            owner=self.user, architecture=make_usable_architecture(self)
        )
        old_zone = machine.zone

        response = self.client.put(
            self.get_machine_uri(machine), {"zone": new_zone.name}
        )

        self.assertEqual(http.client.FORBIDDEN, response.status_code)
        # Confirm the machine's physical zone has not been updated.
        machine = reload_object(machine)
        self.assertEqual(old_zone, machine.zone)

    def test_PUT_updates_swap_size(self):
        self.become_admin()
        machine = factory.make_Node(
            owner=self.user,
            architecture=make_usable_architecture(self),
            power_type="manual",
        )
        response = self.client.put(
            reverse("machine_handler", args=[machine.system_id]),
            {"swap_size": 5 * 1000**3},
        )  # Making sure we overflow 32 bits
        parsed_result = json_load_bytes(response.content)
        machine = reload_object(machine)
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(machine.swap_size, parsed_result["swap_size"])

    def test_PUT_updates_swap_size_suffixes(self):
        self.become_admin()
        machine = factory.make_Node(
            owner=self.user,
            architecture=make_usable_architecture(self),
            power_type="manual",
        )

        response = self.client.put(
            reverse("machine_handler", args=[machine.system_id]),
            {"swap_size": "5K"},
        )
        parsed_result = json_load_bytes(response.content)
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(5000, parsed_result["swap_size"])

        response = self.client.put(
            reverse("machine_handler", args=[machine.system_id]),
            {"swap_size": "5M"},
        )
        parsed_result = json_load_bytes(response.content)
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(5000000, parsed_result["swap_size"])

        response = self.client.put(
            reverse("machine_handler", args=[machine.system_id]),
            {"swap_size": "5G"},
        )
        parsed_result = json_load_bytes(response.content)
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(5000000000, parsed_result["swap_size"])

        response = self.client.put(
            reverse("machine_handler", args=[machine.system_id]),
            {"swap_size": "5T"},
        )
        parsed_result = json_load_bytes(response.content)
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(5000000000000, parsed_result["swap_size"])

    def test_PUT_updates_swap_size_invalid_suffix(self):
        self.become_admin()
        machine = factory.make_Node(
            owner=self.user, architecture=make_usable_architecture(self)
        )
        response = self.client.put(
            reverse("machine_handler", args=[machine.system_id]),
            {"swap_size": "5E"},
        )  # We won't support exabytes yet
        parsed_result = json_load_bytes(response.content)
        self.assertEqual(http.client.BAD_REQUEST, response.status_code)
        self.assertEqual(
            "Invalid size for swap: 5E", parsed_result["swap_size"][0]
        )

    def test_DELETE_deletes_machine(self):
        # The api allows to delete a Machine.
        self.become_admin()
        machine = factory.make_Node(owner=self.user)
        system_id = machine.system_id
        response = self.client.delete(self.get_machine_uri(machine))

        self.assertEqual(204, response.status_code)
        self.assertCountEqual([], Machine.objects.filter(system_id=system_id))

    def test_DELETE_rejects_other_node_types(self):
        node = factory.make_Node_with_Interface_on_Subnet(
            owner=self.user,
            node_type=factory.pick_choice(
                NODE_TYPE_CHOICES, but_not=[NODE_TYPE.MACHINE]
            ),
        )
        response = self.client.delete(self.get_machine_uri(node))
        self.assertEqual(
            http.client.NOT_FOUND, response.status_code, response.content
        )

    def test_DELETE_deletes_machine_fails_if_not_admin(self):
        # Only superusers can delete machines.
        machine = factory.make_Node(owner=self.user)
        response = self.client.delete(self.get_machine_uri(machine))

        self.assertEqual(http.client.FORBIDDEN, response.status_code)

    def test_DELETE_forbidden_without_edit_permission(self):
        # A user without the edit permission cannot delete a Machine.
        machine = factory.make_Node()
        response = self.client.delete(self.get_machine_uri(machine))

        self.assertEqual(http.client.FORBIDDEN, response.status_code)

    def test_DELETE_deletes_machine_fails_if_locked(self):
        # Only superusers can delete machines.
        machine = factory.make_Node(
            owner=self.user, status=NODE_STATUS.DEPLOYED, locked=True
        )
        response = self.client.delete(self.get_machine_uri(machine))
        self.assertEqual(http.client.FORBIDDEN, response.status_code)

    def test_DELETE_refuses_to_delete_invisible_machine(self):
        # The request to delete a single machine is denied if the machine isn't
        # visible by the user.
        other_machine = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=factory.make_User()
        )

        response = self.client.delete(self.get_machine_uri(other_machine))

        self.assertEqual(http.client.FORBIDDEN, response.status_code)

    def test_DELETE_refuses_to_delete_nonexistent_machine(self):
        # When deleting a Machine, the api returns a 'Not Found' (404) error
        # if no machine is found.
        url = reverse("machine_handler", args=["invalid-uuid"])
        response = self.client.delete(url)

        self.assertEqual(http.client.NOT_FOUND, response.status_code)

    def test_DELETE_delete_with_force(self):
        self.become_admin()
        vlan = factory.make_VLAN()
        subnet = factory.make_Subnet(vlan=vlan)
        machine = factory.make_Machine_with_Interface_on_Subnet(
            vlan=vlan, subnet=subnet
        )
        ip = factory.make_StaticIPAddress(interface=machine.boot_interface)
        factory.make_Pod(ip_address=ip)
        mock_async_delete = self.patch(Pod, "async_delete")
        response = self.client.delete(
            self.get_machine_uri(machine),
            QUERY_STRING=urlencode({"force": "true"}, doseq=True),
        )
        self.assertEqual(
            http.client.NO_CONTENT,
            response.status_code,
            explain_unexpected_response(http.client.NO_CONTENT, response),
        )
        self.assertThat(mock_async_delete, MockCallsMatch(call()))

    def test_pod_DELETE_delete_without_force(self):
        self.become_admin()
        vlan = factory.make_VLAN()
        subnet = factory.make_Subnet(vlan=vlan)
        machine = factory.make_Machine_with_Interface_on_Subnet(
            vlan=vlan, subnet=subnet
        )
        ip = factory.make_StaticIPAddress(interface=machine.boot_interface)
        factory.make_Pod(ip_address=ip)
        mock_async_delete = self.patch(Pod, "async_delete")
        response = self.client.delete(self.get_machine_uri(machine))
        self.assertEqual(
            http.client.BAD_REQUEST,
            response.status_code,
            explain_unexpected_response(http.client.BAD_REQUEST, response),
        )
        self.assertThat(mock_async_delete, MockNotCalled())


class TestMachineAPITransactional(APITransactionTestCase.ForUser):
    """The following TestMachineAPI tests require APITransactionTestCase."""

    def test_POST_start_returns_error_when_static_ips_exhausted(self):
        self.patch(node_module, "power_driver_check")
        network = IPNetwork("10.0.0.0/30")
        rack_controller = factory.make_RackController()
        subnet = factory.make_Subnet(cidr=str(network.cidr))
        subnet.vlan.dhcp_on = True
        subnet.vlan.primary_rack = rack_controller
        subnet.vlan.save()
        architecture = make_usable_architecture(self)
        machine = factory.make_Node(
            status=NODE_STATUS.ALLOCATED,
            architecture=architecture,
            power_type="virsh",
            owner=self.user,
            power_state=POWER_STATE.OFF,
            bmc_connected_to=rack_controller,
        )
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=machine, vlan=subnet.vlan
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO,
            ip="",
            subnet=subnet,
            interface=interface,
        )

        # Pre-claim the only addresses.
        with transaction.atomic():
            StaticIPAddress.objects.allocate_new(requested_address="10.0.0.1")
            StaticIPAddress.objects.allocate_new(requested_address="10.0.0.2")
            StaticIPAddress.objects.allocate_new(requested_address="10.0.0.3")

        osystem = make_usable_osystem(self)
        distro_series = osystem["default_release"]
        machine.osystem = osystem["name"]
        machine.distro_series = distro_series
        machine.save()

        # Catch the StaticIPAddressExhaustion exception. In a real running
        # WSGI client the exception will be handled and converted to the
        # `SERVICE_UNAVAILABLE` HTTP error. With the unit tests client the
        # error is raised in the post_commit_hooks which are not caught and
        # handled.
        self.assertRaises(
            StaticIPAddressExhaustion,
            self.client.post,
            TestMachineAPI.get_machine_uri(machine),
            {"op": "power_on", "distro_series": distro_series},
        )


class TestSetStorageLayout(APITestCase.ForUser):
    def get_machine_uri(self, machine):
        """Get the API URI for `machine`."""
        return reverse("machine_handler", args=[machine.system_id])

    def test_403_when_not_admin(self):
        machine = factory.make_Node(status=NODE_STATUS.READY)
        response = self.client.post(
            self.get_machine_uri(machine), {"op": "set_storage_layout"}
        )
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_409_when_machine_not_ready(self):
        self.become_admin()
        machine = factory.make_Node(status=NODE_STATUS.ALLOCATED)
        response = self.client.post(
            self.get_machine_uri(machine), {"op": "set_storage_layout"}
        )
        self.assertEqual(
            http.client.CONFLICT, response.status_code, response.content
        )

    def test_400_when_storage_layout_missing(self):
        self.become_admin()
        machine = factory.make_Node(status=NODE_STATUS.READY)
        response = self.client.post(
            self.get_machine_uri(machine), {"op": "set_storage_layout"}
        )
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )
        self.assertEqual(
            {"storage_layout": ["This field is required."]},
            json_load_bytes(response.content),
        )

    def test_400_when_invalid_optional_param(self):
        self.become_admin()
        machine = factory.make_Node(status=NODE_STATUS.READY)
        factory.make_PhysicalBlockDevice(node=machine)
        response = self.client.post(
            self.get_machine_uri(machine),
            {
                "op": "set_storage_layout",
                "storage_layout": "flat",
                "boot_size": MIN_BOOT_PARTITION_SIZE - 1,
            },
        )
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )
        self.assertEqual(
            {
                "boot_size": [
                    "Size is too small. Minimum size is %s."
                    % MIN_BOOT_PARTITION_SIZE
                ]
            },
            json_load_bytes(response.content),
        )

    def test_400_when_no_boot_disk(self):
        self.become_admin()
        machine = factory.make_Node(
            status=NODE_STATUS.READY, with_boot_disk=False
        )
        response = self.client.post(
            self.get_machine_uri(machine),
            {"op": "set_storage_layout", "storage_layout": "flat"},
        )
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )
        self.assertEqual(
            "Machine is missing a boot disk; no storage layout can be "
            "applied.",
            response.content.decode(settings.DEFAULT_CHARSET),
        )

    def test_400_when_layout_error(self):
        self.become_admin()
        machine = factory.make_Node(status=NODE_STATUS.READY)
        mock_set_storage_layout = self.patch(Machine, "set_storage_layout")
        error_msg = factory.make_name("error")
        mock_set_storage_layout.side_effect = StorageLayoutError(error_msg)

        response = self.client.post(
            self.get_machine_uri(machine),
            {"op": "set_storage_layout", "storage_layout": "flat"},
        )
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )
        self.assertEqual(
            "Failed to configure storage layout 'flat': %s" % error_msg,
            response.content.decode(settings.DEFAULT_CHARSET),
        )

    def test_400_when_layout_not_supported(self):
        self.become_admin()
        machine = factory.make_Node(status=NODE_STATUS.READY)
        factory.make_PhysicalBlockDevice(node=machine)
        response = self.client.post(
            self.get_machine_uri(machine),
            {"op": "set_storage_layout", "storage_layout": "bcache"},
        )
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )
        self.assertEqual(
            "Failed to configure storage layout 'bcache': Node doesn't "
            "have an available cache device to setup bcache.",
            response.content.decode(settings.DEFAULT_CHARSET),
        )

    def test_calls_set_storage_layout_on_machine(self):
        self.become_admin()
        machine = factory.make_Node(status=NODE_STATUS.READY)
        mock_set_storage_layout = self.patch(Machine, "set_storage_layout")
        response = self.client.post(
            self.get_machine_uri(machine),
            {"op": "set_storage_layout", "storage_layout": "flat"},
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        self.assertThat(
            mock_set_storage_layout,
            MockCalledOnceWith("flat", params=ANY, allow_fallback=False),
        )


class TestMountSpecial(APITestCase.ForUser):
    """Tests for op=mount_special."""

    def get_machine_uri(self, machine):
        """Get the API URI for `machine`."""
        return reverse("machine_handler", args=[machine.system_id])

    def test_fstype_and_mount_point_is_required_but_options_is_not(self):
        machine = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=self.user
        )
        response = self.client.post(
            self.get_machine_uri(machine), {"op": "mount_special"}
        )
        self.assertEqual(http.client.BAD_REQUEST, response.status_code)
        self.assertEqual(
            {
                "fstype": ["This field is required."],
                "mount_point": ["This field is required."],
            },
            json_load_bytes(response.content),
        )

    def test_fstype_must_be_a_non_storage_type(self):
        machine = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=self.user
        )
        for fstype in Filesystem.TYPES_REQUIRING_STORAGE:
            response = self.client.post(
                self.get_machine_uri(machine),
                {
                    "op": "mount_special",
                    "fstype": fstype,
                    "mount_point": factory.make_absolute_path(),
                },
            )
            self.assertEqual(http.client.BAD_REQUEST, response.status_code)
            self.expectThat(
                json_load_bytes(response.content),
                ContainsDict(
                    {
                        "fstype": MatchesListwise(
                            [StartsWith("Select a valid choice.")]
                        )
                    }
                ),
                "using fstype " + fstype,
            )

    def test_mount_point_must_be_absolute(self):
        machine = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=self.user
        )
        response = self.client.post(
            self.get_machine_uri(machine),
            {
                "op": "mount_special",
                "fstype": FILESYSTEM_TYPE.RAMFS,
                "mount_point": factory.make_name("path"),
            },
        )
        self.assertEqual(http.client.BAD_REQUEST, response.status_code)
        self.assertThat(
            json_load_bytes(response.content),
            ContainsDict(
                {
                    # XXX: Wow, what a lame error from AbsolutePathField!
                    "mount_point": Equals(["Enter a valid value."])
                }
            ),
        )


class TestMountSpecialScenarios(APITestCase.ForUser):
    """Scenario tests for op=mount_special."""

    scenarios = [
        (displayname, {"fstype": name})
        for name, displayname in FILESYSTEM_FORMAT_TYPE_CHOICES
        if name not in Filesystem.TYPES_REQUIRING_STORAGE
    ]

    def get_machine_uri(self, machine):
        """Get the API URI for `machine`."""
        return reverse("machine_handler", args=[machine.system_id])

    def test_machine_representation_includes_non_storage_filesystem(self):
        self.become_admin()
        machine = factory.make_Node(status=NODE_STATUS.READY)
        filesystem = factory.make_Filesystem(
            node_config=machine.current_config,
            fstype=self.fstype,
        )
        response = self.client.get(self.get_machine_uri(machine))
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        self.assertThat(
            json_load_bytes(response.content),
            ContainsDict(
                {
                    "special_filesystems": MatchesListwise(
                        [
                            ContainsDict(
                                {
                                    "fstype": Equals(filesystem.fstype),
                                    "label": Equals(filesystem.label),
                                    "mount_options": Equals(
                                        filesystem.mount_options
                                    ),
                                    "mount_point": Equals(
                                        filesystem.mount_point
                                    ),
                                    "uuid": Equals(filesystem.uuid),
                                }
                            )
                        ]
                    )
                }
            ),
        )

    def test_only_acquired_special_filesystems(self):
        self.become_admin()
        machine = factory.make_Node(status=NODE_STATUS.DEPLOYED)
        factory.make_Filesystem(
            node_config=machine.current_config,
            fstype=self.fstype,
            label="not-acquired",
        )
        filesystem = factory.make_Filesystem(
            node_config=machine.current_config,
            fstype=self.fstype,
            label="acquired",
            acquired=True,
        )
        response = self.client.get(self.get_machine_uri(machine))
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        self.assertThat(
            json_load_bytes(response.content),
            ContainsDict(
                {
                    "special_filesystems": MatchesListwise(
                        [
                            ContainsDict(
                                {
                                    "fstype": Equals(filesystem.fstype),
                                    "label": Equals(filesystem.label),
                                    "mount_options": Equals(
                                        filesystem.mount_options
                                    ),
                                    "mount_point": Equals(
                                        filesystem.mount_point
                                    ),
                                    "uuid": Equals(filesystem.uuid),
                                }
                            )
                        ]
                    )
                }
            ),
        )

    def test_only_not_acquired_special_filesystems(self):
        self.become_admin()
        machine = factory.make_Node(status=NODE_STATUS.READY)
        filesystem = factory.make_Filesystem(
            node_config=machine.current_config,
            fstype=self.fstype,
            label="not-acquired",
        )
        factory.make_Filesystem(
            node_config=machine.current_config,
            fstype=self.fstype,
            label="acquired",
            acquired=True,
        )
        response = self.client.get(self.get_machine_uri(machine))
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        self.assertThat(
            json_load_bytes(response.content),
            ContainsDict(
                {
                    "special_filesystems": MatchesListwise(
                        [
                            ContainsDict(
                                {
                                    "fstype": Equals(filesystem.fstype),
                                    "label": Equals(filesystem.label),
                                    "mount_options": Equals(
                                        filesystem.mount_options
                                    ),
                                    "mount_point": Equals(
                                        filesystem.mount_point
                                    ),
                                    "uuid": Equals(filesystem.uuid),
                                }
                            )
                        ]
                    )
                }
            ),
        )

    def assertCanMountFilesystem(self, machine):
        mount_point = factory.make_absolute_path()
        mount_options = factory.make_name("options")
        response = self.client.post(
            self.get_machine_uri(machine),
            {
                "op": "mount_special",
                "fstype": self.fstype,
                "mount_point": mount_point,
                "mount_options": mount_options,
            },
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        self.assertThat(
            list(machine.current_config.special_filesystems),
            MatchesListwise(
                [
                    MatchesStructure.byEquality(
                        fstype=self.fstype,
                        mount_point=mount_point,
                        mount_options=mount_options,
                        node_config=machine.current_config,
                    )
                ]
            ),
        )

    def test_user_mounts_non_storage_filesystem_on_allocated_machine(self):
        self.assertCanMountFilesystem(
            factory.make_Node(status=NODE_STATUS.ALLOCATED, owner=self.user)
        )

    def test_conflict_to_mount_on_non_ready_allocated_machine(self):
        statuses = {name for name, _ in NODE_STATUS_CHOICES}
        statuses -= {NODE_STATUS.READY, NODE_STATUS.ALLOCATED}
        for status in statuses:
            machine = factory.make_Node(status=status)
            response = self.client.post(
                self.get_machine_uri(machine),
                {
                    "op": "mount_special",
                    "fstype": self.fstype,
                    "mount_point": factory.make_absolute_path(),
                    "mount_options": factory.make_name("options"),
                },
            )
            self.expectThat(
                response.status_code,
                Equals(http.client.CONFLICT),
                "using status %d" % status,
            )

    def test_admin_mounts_non_storage_filesystem_on_allocated_machine(self):
        self.become_admin()
        self.assertCanMountFilesystem(
            factory.make_Node(status=NODE_STATUS.ALLOCATED, owner=self.user)
        )

    def test_admin_mounts_non_storage_filesystem_on_ready_machine(self):
        self.become_admin()
        self.assertCanMountFilesystem(
            factory.make_Node(status=NODE_STATUS.READY)
        )

    def test_admin_cannot_mount_on_non_ready_or_allocated_machine(self):
        self.become_admin()
        statuses = {name for name, _ in NODE_STATUS_CHOICES}
        statuses -= {NODE_STATUS.READY, NODE_STATUS.ALLOCATED}
        for status in statuses:
            machine = factory.make_Node(status=status)
            response = self.client.post(
                self.get_machine_uri(machine),
                {
                    "op": "mount_special",
                    "fstype": self.fstype,
                    "mount_point": factory.make_absolute_path(),
                    "mount_options": factory.make_name("options"),
                },
            )
            self.expectThat(
                response.status_code,
                Equals(http.client.CONFLICT),
                "using status %d" % status,
            )


class TestUnmountSpecial(APITestCase.ForUser):
    """Tests for op=unmount_special."""

    def get_machine_uri(self, machine):
        """Get the API URI for `machine`."""
        return reverse("machine_handler", args=[machine.system_id])

    def test_mount_point_is_required(self):
        machine = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=self.user
        )
        response = self.client.post(
            self.get_machine_uri(machine), {"op": "unmount_special"}
        )
        self.assertEqual(http.client.BAD_REQUEST, response.status_code)
        self.assertEqual(
            {"mount_point": ["This field is required."]},
            json_load_bytes(response.content),
        )

    def test_mount_point_must_be_absolute(self):
        machine = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=self.user
        )
        response = self.client.post(
            self.get_machine_uri(machine),
            {
                "op": "unmount_special",
                "mount_point": factory.make_name("path"),
            },
        )
        self.assertEqual(http.client.BAD_REQUEST, response.status_code)
        self.assertThat(
            json_load_bytes(response.content),
            ContainsDict(
                {
                    # XXX: Wow, what a lame error from AbsolutePathField!
                    "mount_point": Equals(["Enter a valid value."])
                }
            ),
        )


class TestUnmountSpecialScenarios(APITestCase.ForUser):
    """Scenario tests for op=unmount_special."""

    scenarios = [
        (displayname, {"fstype": name})
        for name, displayname in FILESYSTEM_FORMAT_TYPE_CHOICES
        if name not in Filesystem.TYPES_REQUIRING_STORAGE
    ]

    def get_machine_uri(self, machine):
        """Get the API URI for `machine`."""
        return reverse("machine_handler", args=[machine.system_id])

    def assertCanUnmountFilesystem(self, machine):
        filesystem = factory.make_Filesystem(
            node_config=machine.current_config,
            fstype=self.fstype,
            mount_point=factory.make_absolute_path(),
        )
        response = self.client.post(
            self.get_machine_uri(machine),
            {"op": "unmount_special", "mount_point": filesystem.mount_point},
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        self.assertFalse(machine.current_config.special_filesystems.exists())

    def test_user_unmounts_non_storage_filesystem_on_allocated_machine(self):
        self.assertCanUnmountFilesystem(
            factory.make_Node(status=NODE_STATUS.ALLOCATED, owner=self.user)
        )

    def test_conflict_to_unmount_on_non_ready_allocated_machine(self):
        statuses = {name for name, _ in NODE_STATUS_CHOICES}
        statuses -= {NODE_STATUS.READY, NODE_STATUS.ALLOCATED}
        for status in statuses:
            machine = factory.make_Node(status=status)
            filesystem = factory.make_Filesystem(
                node_config=machine.current_config,
                fstype=self.fstype,
                mount_point=factory.make_absolute_path(),
            )
            response = self.client.post(
                self.get_machine_uri(machine),
                {
                    "op": "unmount_special",
                    "mount_point": filesystem.mount_point,
                },
            )
            self.expectThat(
                response.status_code,
                Equals(http.client.CONFLICT),
                "using status %d" % status,
            )

    def test_admin_unmounts_non_storage_filesystem_on_allocated_machine(self):
        self.become_admin()
        self.assertCanUnmountFilesystem(
            factory.make_Node(status=NODE_STATUS.ALLOCATED, owner=self.user)
        )

    def test_admin_unmounts_non_storage_filesystem_on_ready_machine(self):
        self.become_admin()
        self.assertCanUnmountFilesystem(
            factory.make_Node(status=NODE_STATUS.READY)
        )

    def test_admin_cannot_unmount_on_non_ready_or_allocated_machine(self):
        self.become_admin()
        statuses = {name for name, _ in NODE_STATUS_CHOICES}
        statuses -= {NODE_STATUS.READY, NODE_STATUS.ALLOCATED}
        for status in statuses:
            machine = factory.make_Node(status=status)
            filesystem = factory.make_Filesystem(
                node_config=machine.current_config,
                fstype=self.fstype,
                mount_point=factory.make_absolute_path(),
            )
            response = self.client.post(
                self.get_machine_uri(machine),
                {
                    "op": "unmount_special",
                    "mount_point": filesystem.mount_point,
                },
            )
            self.expectThat(
                response.status_code,
                Equals(http.client.CONFLICT),
                "using status %d" % status,
            )


class TestDefaultGateways(APITestCase.ForUser):
    def get_machine_uri(self, machine):
        """Get the API URI for `machine`."""
        return reverse("machine_handler", args=[machine.system_id])

    def test_403_when_not_admin(self):
        machine = factory.make_Node(
            owner=self.user, status=NODE_STATUS.ALLOCATED
        )
        response = self.client.post(
            self.get_machine_uri(machine), {"op": "clear_default_gateways"}
        )
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_clears_default_gateways(self):
        self.become_admin()
        machine = factory.make_Node(
            owner=self.user, status=NODE_STATUS.ALLOCATED
        )
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=machine
        )
        network_v4 = factory.make_ipv4_network()
        subnet_v4 = factory.make_Subnet(
            cidr=str(network_v4.cidr), vlan=interface.vlan
        )
        link_v4 = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO,
            ip="",
            subnet=subnet_v4,
            interface=interface,
        )
        machine.gateway_link_ipv4 = link_v4
        network_v6 = factory.make_ipv6_network()
        subnet_v6 = factory.make_Subnet(
            cidr=str(network_v6.cidr), vlan=interface.vlan
        )
        link_v6 = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO,
            ip="",
            subnet=subnet_v6,
            interface=interface,
        )
        machine.gateway_link_ipv6 = link_v6
        machine.save()
        response = self.client.post(
            self.get_machine_uri(machine), {"op": "clear_default_gateways"}
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        machine = reload_object(machine)
        self.assertIsNone(machine.gateway_link_ipv4)
        self.assertIsNone(machine.gateway_link_ipv6)

    def test_returns_null_gateway_if_no_explicit_gateway_exists(self):
        machine = factory.make_Node(
            owner=self.user, status=NODE_STATUS.ALLOCATED
        )
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=machine
        )
        network_v4 = factory.make_ipv4_network()
        subnet_v4 = factory.make_Subnet(
            cidr=str(network_v4.cidr), vlan=interface.vlan, gateway_ip=None
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO,
            ip="",
            subnet=subnet_v4,
            interface=interface,
        )
        network_v6 = factory.make_ipv6_network()
        subnet_v6 = factory.make_Subnet(
            cidr=str(network_v6.cidr), vlan=interface.vlan, gateway_ip=None
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO,
            ip="",
            subnet=subnet_v6,
            interface=interface,
        )
        response = self.client.get(self.get_machine_uri(machine))
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        response = json_load_bytes(response.content)
        self.assertEqual(
            {
                "ipv4": {"link_id": None, "gateway_ip": None},
                "ipv6": {"link_id": None, "gateway_ip": None},
            },
            response["default_gateways"],
        )

    def test_returns_effective_gateway_if_no_explicit_gateway_set(self):
        machine = factory.make_Node(
            owner=self.user, status=NODE_STATUS.ALLOCATED
        )
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=machine
        )
        network_v4 = factory.make_ipv4_network()
        subnet_v4 = factory.make_Subnet(
            cidr=str(network_v4.cidr), vlan=interface.vlan
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO,
            ip="",
            subnet=subnet_v4,
            interface=interface,
        )
        network_v6 = factory.make_ipv6_network()
        subnet_v6 = factory.make_Subnet(
            cidr=str(network_v6.cidr), vlan=interface.vlan
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO,
            ip="",
            subnet=subnet_v6,
            interface=interface,
        )
        response = self.client.get(self.get_machine_uri(machine))
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        response = json_load_bytes(response.content)
        self.assertEqual(
            {
                "ipv4": {
                    "link_id": None,
                    "gateway_ip": str(subnet_v4.gateway_ip),
                },
                "ipv6": {
                    "link_id": None,
                    "gateway_ip": str(subnet_v6.gateway_ip),
                },
            },
            response["default_gateways"],
        )

    def test_returns_links_if_set(self):
        machine = factory.make_Node(
            owner=self.user, status=NODE_STATUS.ALLOCATED
        )
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=machine
        )
        network_v4 = factory.make_ipv4_network()
        subnet_v4 = factory.make_Subnet(
            cidr=str(network_v4.cidr), vlan=interface.vlan
        )
        link_v4 = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO,
            ip="",
            subnet=subnet_v4,
            interface=interface,
        )
        machine.gateway_link_ipv4 = link_v4
        network_v6 = factory.make_ipv6_network()
        subnet_v6 = factory.make_Subnet(
            cidr=str(network_v6.cidr), vlan=interface.vlan
        )
        link_v6 = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO,
            ip="",
            subnet=subnet_v6,
            interface=interface,
        )
        machine.gateway_link_ipv6 = link_v6
        machine.save()
        response = self.client.get(self.get_machine_uri(machine))
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        response = json_load_bytes(response.content)
        self.assertEqual(
            {
                "ipv4": {
                    "link_id": link_v4.id,
                    "gateway_ip": str(subnet_v4.gateway_ip),
                },
                "ipv6": {
                    "link_id": link_v6.id,
                    "gateway_ip": str(subnet_v6.gateway_ip),
                },
            },
            response["default_gateways"],
        )


class TestGetCurtinConfig(APITestCase.ForUser):
    def get_machine_uri(self, machine):
        """Get the API URI for `machine`."""
        return reverse("machine_handler", args=[machine.system_id])

    def test_500_when_machine_not_in_deployment_state(self):
        machine = factory.make_Node(
            owner=self.user,
            status=factory.pick_enum(
                NODE_STATUS,
                but_not=[
                    NODE_STATUS.DEPLOYING,
                    NODE_STATUS.DEPLOYED,
                    NODE_STATUS.FAILED_DEPLOYMENT,
                ],
            ),
        )
        response = self.client.get(
            self.get_machine_uri(machine), {"op": "get_curtin_config"}
        )
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )

    def test_returns_curtin_config_in_yaml(self):
        machine = factory.make_Node(
            owner=self.user, status=NODE_STATUS.DEPLOYING
        )
        fake_config = {"config": factory.make_name("config")}
        mock_get_curtin_merged_config = self.patch(
            machines_module, "get_curtin_merged_config"
        )
        mock_get_curtin_merged_config.return_value = fake_config
        response = self.client.get(
            self.get_machine_uri(machine), {"op": "get_curtin_config"}
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        self.assertEqual(
            yaml.safe_dump(fake_config, default_flow_style=False),
            response.content.decode(settings.DEFAULT_CHARSET),
        )
        self.assertThat(
            mock_get_curtin_merged_config, MockCalledOnceWith(ANY, machine)
        )


class TestRestoreNetworkingConfiguration(APITestCase.ForUser):
    """Tests for
    /api/2.0/machines/<machine>/?op=restore_networking_configuration"""

    def get_machine_uri(self, machine):
        """Get the API URI for `machine`."""
        return reverse("machine_handler", args=[machine.system_id])

    def test_restore_networking_configuration(self):
        self.become_admin()
        machine = factory.make_Machine(
            status=choice([NODE_STATUS.READY, NODE_STATUS.FAILED_TESTING])
        )
        mock_restore_network_interfaces = self.patch(
            node_module.Machine, "restore_network_interfaces"
        )
        mock_set_initial_networking_config = self.patch(
            node_module.Machine, "set_initial_networking_configuration"
        )
        response = self.client.post(
            self.get_machine_uri(machine),
            {"op": "restore_networking_configuration"},
        )
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(
            machine.system_id, json_load_bytes(response.content)["system_id"]
        )
        self.assertThat(mock_set_initial_networking_config, MockCalledOnce())
        self.assertThat(mock_restore_network_interfaces, MockCalledOnce())

    def test_restore_networking_configuration_no_gateway_link_ipv4_conflict(
        self,
    ):
        # See also LP#2015411
        self.become_admin()
        machine = factory.make_Machine_with_Interface_on_Subnet(
            status=NODE_STATUS.READY
        )

        lxd_script = factory.make_Script(
            name=COMMISSIONING_OUTPUT_NAME,
            script_type=SCRIPT_TYPE.COMMISSIONING,
        )
        commissioning_script_set = (
            ScriptSet.objects.create_commissioning_script_set(
                machine, scripts=[lxd_script.name]
            )
        )
        machine.current_commissioning_script_set = commissioning_script_set
        output = test_hooks.make_lxd_output_json()
        factory.make_ScriptResult(
            script_set=commissioning_script_set,
            script=lxd_script,
            exit_status=0,
            output=output,
            stdout=output,
        )
        # Create NUMA nodes.
        test_hooks.create_numa_nodes(machine)

        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=machine
        )
        network = factory.make_ipv4_network()
        subnet = factory.make_Subnet(cidr=str(network.cidr))

        link_v4 = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_network(network),
            subnet=subnet,
            interface=interface,
        )
        machine.gateway_link_ipv4 = link_v4
        machine.save()

        machine.restore_network_interfaces()
        machine.set_initial_networking_configuration()

        response = self.client.post(
            self.get_machine_uri(machine),
            {"op": "restore_networking_configuration"},
        )

        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(
            machine.system_id, json_load_bytes(response.content)["system_id"]
        )

    def test_restore_networking_configuration_requires_admin(self):
        machine = factory.make_Machine()
        response = self.client.post(
            self.get_machine_uri(machine),
            {"op": "restore_networking_configuration"},
        )
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_restore_networking_configuration_checks_machine_status(self):
        self.become_admin()
        machine = factory.make_Machine(
            status=factory.pick_choice(
                NODE_STATUS_CHOICES,
                but_not=[NODE_STATUS.READY, NODE_STATUS.FAILED_TESTING],
            )
        )
        mock_set_initial_networking_config = self.patch(
            node_module.Machine, "set_initial_networking_configuration"
        )
        response = self.client.post(
            self.get_machine_uri(machine),
            {"op": "restore_networking_configuration"},
        )
        self.assertEqual(http.client.CONFLICT, response.status_code)
        self.assertThat(mock_set_initial_networking_config, MockNotCalled())


class TestRestoreStorageConfiguration(APITestCase.ForUser):
    """Tests for
    /api/2.0/machines/<machine>/?op=restore_storage_configuration"""

    def get_machine_uri(self, machine):
        """Get the API URI for `machine`."""
        return reverse("machine_handler", args=[machine.system_id])

    def test_restore_storage_configuration(self):
        self.become_admin()
        machine = factory.make_Machine(
            status=choice([NODE_STATUS.READY, NODE_STATUS.FAILED_TESTING])
        )
        mock_set_default_storage_layout = self.patch(
            node_module.Machine, "set_default_storage_layout"
        )
        response = self.client.post(
            self.get_machine_uri(machine),
            {"op": "restore_storage_configuration"},
        )
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(
            machine.system_id, json_load_bytes(response.content)["system_id"]
        )
        self.assertThat(mock_set_default_storage_layout, MockCalledOnce())

    def test_restore_storage_configuration_requires_admin(self):
        machine = factory.make_Machine()
        response = self.client.post(
            self.get_machine_uri(machine),
            {"op": "restore_storage_configuration"},
        )
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_restore_storage_configuration_checks_machine_status(self):
        self.become_admin()
        machine = factory.make_Machine(
            status=factory.pick_choice(
                NODE_STATUS_CHOICES,
                but_not=[NODE_STATUS.READY, NODE_STATUS.FAILED_TESTING],
            )
        )
        mock_set_default_storage_layout = self.patch(
            node_module.Machine, "set_default_storage_layout"
        )
        response = self.client.post(
            self.get_machine_uri(machine),
            {"op": "restore_storage_configuration"},
        )
        self.assertEqual(http.client.CONFLICT, response.status_code)
        self.assertThat(mock_set_default_storage_layout, MockNotCalled())


class TestRestoreDefaultConfiguration(APITestCase.ForUser):
    """Tests for
    /api/2.0/machines/<machine>/?op=restore_default_configuration"""

    def get_machine_uri(self, machine):
        """Get the API URI for `machine`."""
        return reverse("machine_handler", args=[machine.system_id])

    def test_restore_default_configuration(self):
        self.become_admin()
        machine = factory.make_Machine(
            status=choice([NODE_STATUS.READY, NODE_STATUS.FAILED_TESTING])
        )
        mock_set_default_storage_layout = self.patch(
            node_module.Machine, "set_default_storage_layout"
        )
        mock_restore_network_interfaces = self.patch(
            node_module.Machine, "restore_network_interfaces"
        )
        mock_set_initial_networking_config = self.patch(
            node_module.Machine, "set_initial_networking_configuration"
        )
        response = self.client.post(
            self.get_machine_uri(machine),
            {"op": "restore_default_configuration"},
        )
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(
            machine.system_id, json_load_bytes(response.content)["system_id"]
        )
        self.assertThat(mock_set_default_storage_layout, MockCalledOnce())
        self.assertThat(mock_restore_network_interfaces, MockCalledOnce())
        self.assertThat(mock_set_initial_networking_config, MockCalledOnce())

    def test_restore_default_configuration_requires_admin(self):
        machine = factory.make_Machine()
        response = self.client.post(
            self.get_machine_uri(machine),
            {"op": "restore_default_configuration"},
        )
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_restore_default_configuration_checks_machine_status(self):
        self.become_admin()
        machine = factory.make_Machine(
            status=factory.pick_choice(
                NODE_STATUS_CHOICES,
                but_not=[NODE_STATUS.READY, NODE_STATUS.FAILED_TESTING],
            )
        )
        mock_restore_default_configuration = self.patch(
            node_module.Machine, "restore_default_configuration"
        )
        response = self.client.post(
            self.get_machine_uri(machine),
            {"op": "restore_default_configuration"},
        )
        self.assertEqual(http.client.CONFLICT, response.status_code)
        self.assertThat(mock_restore_default_configuration, MockNotCalled())


class TestMarkBroken(APITestCase.ForUser):
    def get_node_uri(self, machine):
        """Get the API URI for `machine`."""
        return reverse("machine_handler", args=[machine.system_id])

    def test_mark_broken_changes_status(self):
        node = factory.make_Node(
            status=NODE_STATUS.COMMISSIONING, owner=self.user
        )
        response = self.client.post(
            self.get_node_uri(node), {"op": "mark_broken"}
        )
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(NODE_STATUS.BROKEN, reload_object(node).status)

    def test_mark_broken_updates_error_description(self):
        # 'error_description' parameter was renamed 'comment' for consistency
        # make sure this comment updates the node's error_description
        node = factory.make_Node(
            status=NODE_STATUS.COMMISSIONING, owner=self.user
        )
        comment = factory.make_name("comment")
        response = self.client.post(
            self.get_node_uri(node), {"op": "mark_broken", "comment": comment}
        )
        self.assertEqual(http.client.OK, response.status_code)
        node = reload_object(node)
        self.assertEqual(
            (NODE_STATUS.BROKEN, comment),
            (node.status, node.error_description),
        )

    def test_mark_broken_updates_error_description_compatibility(self):
        # test old 'error_description' parameter is honored for compatibility
        node = factory.make_Node(
            status=NODE_STATUS.COMMISSIONING, owner=self.user
        )
        error_description = factory.make_name("error_description")
        response = self.client.post(
            self.get_node_uri(node),
            {"op": "mark_broken", "error_description": error_description},
        )
        self.assertEqual(http.client.OK, response.status_code)
        node = reload_object(node)
        self.assertEqual(
            (NODE_STATUS.BROKEN, error_description),
            (node.status, node.error_description),
        )

    def test_mark_broken_passes_comment(self):
        node = factory.make_Node(
            status=NODE_STATUS.COMMISSIONING, owner=self.user
        )
        node_mark_broken = self.patch(node_module.Machine, "mark_broken")
        comment = factory.make_name("comment")
        self.client.post(
            self.get_node_uri(node), {"op": "mark_broken", "comment": comment}
        )
        self.assertThat(
            node_mark_broken, MockCalledOnceWith(self.user, comment)
        )

    def test_mark_broken_handles_missing_comment(self):
        node = factory.make_Node(
            status=NODE_STATUS.COMMISSIONING, owner=self.user
        )
        node_mark_broken = self.patch(node_module.Machine, "mark_broken")
        self.client.post(self.get_node_uri(node), {"op": "mark_broken"})
        self.assertThat(node_mark_broken, MockCalledOnceWith(self.user, None))

    def test_mark_broken_requires_ownership(self):
        node = factory.make_Node(status=NODE_STATUS.COMMISSIONING)
        response = self.client.post(
            self.get_node_uri(node), {"op": "mark_broken"}
        )
        self.assertEqual(http.client.FORBIDDEN, response.status_code)

    def test_mark_broken_allowed_from_any_other_state(self):
        self.patch(node_module.Machine, "_stop")
        for status, _ in NODE_STATUS_CHOICES:
            if status == NODE_STATUS.BROKEN:
                continue

            node = factory.make_Node(status=status, owner=self.user)
            response = self.client.post(
                self.get_node_uri(node), {"op": "mark_broken"}
            )
            self.expectThat(
                response.status_code, Equals(http.client.OK), response
            )
            node = reload_object(node)
            self.expectThat(node.status, Equals(NODE_STATUS.BROKEN))


class TestMarkFixed(APITestCase.ForUser):
    def get_node_uri(self, machine):
        """Get the API URI for `machine`."""
        return reverse("machine_handler", args=[machine.system_id])

    def test_mark_fixed_changes_status(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.BROKEN)
        response = self.client.post(
            self.get_node_uri(node), {"op": "mark_fixed"}
        )
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(NODE_STATUS.READY, reload_object(node).status)

    def test_mark_fixed_requires_admin(self):
        node = factory.make_Node(status=NODE_STATUS.BROKEN)
        response = self.client.post(
            self.get_node_uri(node), {"op": "mark_fixed"}
        )
        self.assertEqual(http.client.FORBIDDEN, response.status_code)

    def test_mark_fixed_passes_comment(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.BROKEN)
        node_mark_fixed = self.patch(node_module.Machine, "mark_fixed")
        comment = factory.make_name("comment")
        self.client.post(
            self.get_node_uri(node), {"op": "mark_fixed", "comment": comment}
        )
        self.assertThat(
            node_mark_fixed, MockCalledOnceWith(self.user, comment)
        )

    def test_mark_fixed_handles_missing_comment(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.BROKEN)
        node_mark_fixed = self.patch(node_module.Machine, "mark_fixed")
        self.client.post(self.get_node_uri(node), {"op": "mark_fixed"})
        self.assertThat(node_mark_fixed, MockCalledOnceWith(self.user, None))


class TestRescueMode(APITransactionTestCase.ForUser):
    """Tests for /api/2.0/machines/<machine>/?op=rescue_mode"""

    def get_machine_uri(self, machine):
        """Get the API URI for `machine`."""
        return reverse("machine_handler", args=[machine.system_id])

    def test_rescue_mode_requires_admin(self):
        status = choice((NODE_STATUS.BROKEN, NODE_STATUS.DEPLOYED))
        machine = factory.make_Node(status=status)
        response = self.client.post(
            self.get_machine_uri(machine), {"op": "rescue_mode"}
        )
        self.assertEqual(http.client.FORBIDDEN, response.status_code)

    def test_rescue_mode_changes_state(self):
        self.become_admin()
        status = choice((NODE_STATUS.BROKEN, NODE_STATUS.DEPLOYED))
        machine = factory.make_Node(status=status)
        mock_power_cycle = self.patch(node_module.Machine, "_power_cycle")
        mock_power_cycle.side_effect = lambda: post_commit()

        with SignalsDisabled("power"):
            response = self.client.post(
                self.get_machine_uri(machine), {"op": "rescue_mode"}
            )
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(
            NODE_STATUS.ENTERING_RESCUE_MODE, reload_object(machine).status
        )


class TestExitRescueMode(APITransactionTestCase.ForUser):
    """Tests for /api/2.0/machines/<machine>/?op=exit_rescue_mode"""

    def get_machine_uri(self, machine):
        """Get the API URI for `machine`."""
        return reverse("machine_handler", args=[machine.system_id])

    def test_exit_rescue_mode_requires_admin(self):
        machine = factory.make_Node(status=NODE_STATUS.RESCUE_MODE)
        response = self.client.post(
            self.get_machine_uri(machine), {"op": "exit_rescue_mode"}
        )
        self.assertEqual(http.client.FORBIDDEN, response.status_code)

    def test_exit_rescue_mode_changes_state(self):
        self.become_admin()
        previous_status = choice((NODE_STATUS.BROKEN, NODE_STATUS.DEPLOYED))
        machine = factory.make_Node(
            status=NODE_STATUS.RESCUE_MODE, previous_status=previous_status
        )
        mock_power_cycle = self.patch(node_module.Machine, "_power_cycle")
        mock_power_cycle.side_effect = lambda: post_commit()
        mock__stop = self.patch(node_module.Machine, "_stop")
        mock__stop.side_effect = lambda user: post_commit()

        with SignalsDisabled("power"):
            response = self.client.post(
                self.get_machine_uri(machine), {"op": "exit_rescue_mode"}
            )
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(
            NODE_STATUS.EXITING_RESCUE_MODE, reload_object(machine).status
        )
