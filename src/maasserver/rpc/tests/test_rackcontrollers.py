# Copyright 2016-2022 Canonical Ltd. This software is licnesed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


import random
from unittest.mock import sentinel
from urllib.parse import urlparse

from fixtures import FakeLogger

from maasserver import locks, worker_user
from maasserver.enum import INTERFACE_TYPE, IPADDRESS_TYPE, NODE_TYPE
from maasserver.models import RackController, RegionController
from maasserver.rpc import rackcontrollers
from maasserver.rpc.rackcontrollers import (
    register,
    report_neighbours,
    update_foreign_dhcp,
    update_state,
)
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import reload_object
from maastesting.matchers import DocTestMatches, MockCalledOnceWith
from metadataserver.builtin_scripts import load_builtin_scripts
from provisioningserver.enum import CONTROLLER_INSTALL_TYPE
from provisioningserver.rpc.exceptions import NoSuchScope


class TestRegisterRackController(MAASServerTestCase):
    def setUp(self):
        super().setUp()
        self.this_region = factory.make_RegionController()
        mock_running = self.patch(
            RegionController.objects, "get_running_controller"
        )
        mock_running.return_value = self.this_region

    def test_sets_owner_to_worker_when_none(self):
        node = factory.make_Node()
        rack_registered = register(system_id=node.system_id)
        self.assertEqual(worker_user.get_worker_user(), rack_registered.owner)

    def test_leaves_owner_when_owned(self):
        user = factory.make_User()
        node = factory.make_Machine(owner=user)
        rack_registered = register(system_id=node.system_id)
        self.assertEqual(user, rack_registered.owner)

    def test_finds_existing_node_by_system_id(self):
        node = factory.make_Node()
        rack_registered = register(system_id=node.system_id)
        self.assertEqual(node.system_id, rack_registered.system_id)

    def test_finds_existing_node_by_hostname(self):
        node = factory.make_Node()
        rack_registered = register(hostname=node.hostname)
        self.assertEqual(node.system_id, rack_registered.system_id)

    def test_finds_existing_node_by_mac(self):
        node = factory.make_Node()
        nic = factory.make_Interface(node=node)
        interfaces = {
            nic.name: {
                "type": "physical",
                "mac_address": nic.mac_address,
                "parents": [],
                "links": [],
                "enabled": True,
            }
        }
        rack_registered = register(interfaces=interfaces)
        self.assertEqual(node.system_id, rack_registered.system_id)

    def test_find_existing_keeps_type(self):
        node_type = random.choice(
            (NODE_TYPE.RACK_CONTROLLER, NODE_TYPE.REGION_AND_RACK_CONTROLLER)
        )
        node = factory.make_Node(node_type=node_type)
        register(system_id=node.system_id)
        self.assertEqual(node_type, node.node_type)

    def test_logs_finding_existing_node(self):
        logger = self.useFixture(FakeLogger("maas"))
        node = factory.make_Node(node_type=NODE_TYPE.RACK_CONTROLLER)
        register(system_id=node.system_id)
        self.assertEqual(
            "Existing rack controller '%s' running version 2.2 or below has "
            "connected to region '%s'."
            % (node.hostname, self.this_region.hostname),
            logger.output.strip(),
        )

    def test_logs_finding_existing_node_with_version(self):
        logger = self.useFixture(FakeLogger("maas"))
        node = factory.make_Node(node_type=NODE_TYPE.RACK_CONTROLLER)
        register(system_id=node.system_id, version="2.10.0")
        self.assertEqual(
            "Existing rack controller '%s' running version 2.10.0 has "
            "connected to region '%s'."
            % (node.hostname, self.this_region.hostname),
            logger.output.strip(),
        )

    def test_converts_region_controller(self):
        node = factory.make_Node(node_type=NODE_TYPE.REGION_CONTROLLER)
        rack_registered = register(system_id=node.system_id)
        self.assertEqual(
            rack_registered.node_type, NODE_TYPE.REGION_AND_RACK_CONTROLLER
        )

    def test_logs_converting_region_controller(self):
        logger = self.useFixture(FakeLogger("maas"))
        node = factory.make_Node(node_type=NODE_TYPE.REGION_CONTROLLER)
        register(system_id=node.system_id)
        self.assertEqual(
            "Region controller '%s' running version 2.2 or below converted "
            "into a region and rack controller.\n" % node.hostname,
            logger.output,
        )

    def test_logs_converting_region_controller_with_version(self):
        logger = self.useFixture(FakeLogger("maas"))
        node = factory.make_Node(node_type=NODE_TYPE.REGION_CONTROLLER)
        register(system_id=node.system_id, version="2.10.0")
        self.assertEqual(
            "Region controller '%s' running version 2.10.0 converted "
            "into a region and rack controller.\n" % node.hostname,
            logger.output,
        )

    def test_converts_existing_node(self):
        node = factory.make_Machine()
        rack_registered = register(system_id=node.system_id)
        self.assertEqual(rack_registered.node_type, NODE_TYPE.RACK_CONTROLLER)
        reload_object(node)
        self.assertFalse(node.should_be_dynamically_deleted())

    def test_logs_converting_existing_node(self):
        logger = self.useFixture(FakeLogger("maas"))
        node = factory.make_Node(node_type=NODE_TYPE.MACHINE)
        register(system_id=node.system_id)
        self.assertEqual(
            "Region controller '%s' converted '%s' running version 2.2 or "
            "below into a rack controller.\n"
            % (self.this_region.hostname, node.hostname),
            logger.output,
        )

    def test_logs_converting_existing_node_with_version(self):
        logger = self.useFixture(FakeLogger("maas"))
        node = factory.make_Node(node_type=NODE_TYPE.MACHINE)
        register(system_id=node.system_id, version="1.10.2")
        self.assertEqual(
            "Region controller '%s' converted '%s' running version 1.10.2 "
            "into a rack controller.\n"
            % (self.this_region.hostname, node.hostname),
            logger.output,
        )

    def test_creates_new_rackcontroller(self):
        existing_machine = factory.make_Machine()
        rack_mac = factory.make_mac_address()
        interfaces = {
            factory.make_name("eth0"): {
                "type": "physical",
                "mac_address": rack_mac,
                "parents": [],
                "links": [],
                "enabled": True,
            }
        }
        rack_controller = register(interfaces=interfaces)
        self.assertNotEqual(
            existing_machine.system_id, rack_controller.system_id
        )
        self.assertTrue(rack_controller.should_be_dynamically_deleted())

    def test_always_has_current_commissioning_script_set(self):
        load_builtin_scripts()
        hostname = factory.make_name("hostname")
        register(hostname=hostname)
        rack = RackController.objects.get(hostname=hostname)
        self.assertIsNotNone(rack.current_commissioning_script_set)

    def test_logs_creating_new_rackcontroller(self):
        logger = self.useFixture(FakeLogger("maas"))
        hostname = factory.make_name("hostname")
        register(hostname=hostname)
        self.assertEqual(
            "New rack controller '%s' running version 2.2 or below was "
            "created by region '%s' upon first connection."
            % (hostname, self.this_region.hostname),
            logger.output.strip(),
        )

    def test_logs_creating_new_rackcontroller_with_version(self):
        logger = self.useFixture(FakeLogger("maas"))
        hostname = factory.make_name("hostname")
        register(hostname=hostname, version="2.10.0")
        self.assertEqual(
            "New rack controller '%s' running version 2.10.0 was "
            "created by region '%s' upon first connection."
            % (hostname, self.this_region.hostname),
            logger.output.strip(),
        )

    def test_sets_version_of_controller(self):
        version = "1.10.2"
        node = factory.make_Node(node_type=NODE_TYPE.MACHINE)
        register(system_id=node.system_id, version=version)
        self.assertEqual(version, node.as_rack_controller().version)

    def test_registers_with_startup_lock_held(self):
        lock_status = []

        def record_lock_status(*args):
            lock_status.append(locks.startup.is_locked())
            return None  # Simulate that no rack found.

        find = self.patch(rackcontrollers, "find")
        find.side_effect = record_lock_status

        register()

        self.assertEqual([True], lock_status)

    def test_sets_url(self):
        load_builtin_scripts()
        rack_controller = factory.make_RackController()
        interfaces = {
            factory.make_name("eth0"): {
                "type": "physical",
                "mac_address": factory.make_mac_address(),
                "parents": [],
                "links": [],
                "enabled": True,
            }
        }
        url = "http://%s/MAAS" % factory.make_name("host")
        rack_registered = register(
            rack_controller.system_id,
            interfaces=interfaces,
            url=urlparse(url),
            is_loopback=False,
        )
        self.assertEqual(url, rack_registered.url)
        rack_registered = register(
            rack_controller.system_id,
            interfaces=interfaces,
            url=urlparse("http://localhost/MAAS/"),
            is_loopback=True,
        )
        self.assertEqual("", rack_registered.url)

    def test_creates_rackcontroller_domain(self):
        # Create a domain if a newly registered rackcontroller uses a FQDN
        # as the hostname, but the domain does not already existing in MAAS,
        hostname = "newcontroller.example.com"
        interfaces = {
            factory.make_name("eth0"): {
                "type": "physical",
                "mac_address": factory.make_mac_address(),
                "parents": [],
                "links": [],
                "enabled": True,
            }
        }
        url = "http://%s/MAAS" % factory.make_name("host")
        rack_registered = register(
            "rack-id-foo",
            interfaces=interfaces,
            url=urlparse(url),
            is_loopback=False,
            hostname=hostname,
        )
        self.assertEqual("newcontroller", rack_registered.hostname)
        self.assertEqual("example.com", rack_registered.domain.name)
        self.assertFalse(rack_registered.domain.authoritative)

    def test_reuses_rackcontroller_domain(self):
        # If a domain name already exists for a FQDN hostname, it is
        # not modified.
        factory.make_Domain("example.com", authoritative=True)
        hostname = "newcontroller.example.com"
        interfaces = {
            factory.make_name("eth0"): {
                "type": "physical",
                "mac_address": factory.make_mac_address(),
                "parents": [],
                "links": [],
                "enabled": True,
            }
        }
        url = "http://%s/MAAS" % factory.make_name("host")
        rack_registered = register(
            "rack-id-foo",
            interfaces=interfaces,
            url=urlparse(url),
            is_loopback=False,
            hostname=hostname,
        )
        self.assertEqual("newcontroller", rack_registered.hostname)
        self.assertEqual("example.com", rack_registered.domain.name)
        self.assertTrue(rack_registered.domain.authoritative)


class TestUpdateForeignDHCP(MAASServerTestCase):
    def test_doesnt_fail_if_interface_missing(self):
        rack_controller = factory.make_RackController()
        # No error should be raised.
        update_foreign_dhcp(
            rack_controller.system_id, factory.make_name("eth"), None
        )

    def test_clears_external_dhcp_on_vlan(self):
        rack_controller = factory.make_RackController(interface=False)
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=rack_controller
        )
        interface.vlan.external_dhcp = factory.make_ip_address()
        interface.vlan.save()
        update_foreign_dhcp(rack_controller.system_id, interface.name, None)
        self.assertIsNone(reload_object(interface.vlan).external_dhcp)

    def test_sets_external_dhcp_when_not_managed_vlan(self):
        rack_controller = factory.make_RackController(interface=False)
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=rack_controller
        )
        dhcp_ip = factory.make_ip_address()
        update_foreign_dhcp(rack_controller.system_id, interface.name, dhcp_ip)
        self.assertEqual(dhcp_ip, reload_object(interface.vlan).external_dhcp)

    def test_logs_warning_for_external_dhcp_on_interface_no_vlan(self):
        rack_controller = factory.make_RackController(interface=False)
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=rack_controller
        )
        dhcp_ip = factory.make_ip_address()
        interface.vlan = None
        interface.save()
        logger = self.useFixture(FakeLogger())
        update_foreign_dhcp(rack_controller.system_id, interface.name, dhcp_ip)
        self.assertThat(
            logger.output,
            DocTestMatches(
                "...DHCP server on an interface with no VLAN defined..."
            ),
        )

    def test_clears_external_dhcp_when_managed_vlan(self):
        rack_controller = factory.make_RackController(interface=False)
        fabric = factory.make_Fabric()
        vlan = fabric.get_default_vlan()
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=rack_controller, vlan=vlan
        )
        subnet = factory.make_Subnet()
        dhcp_ip = factory.pick_ip_in_Subnet(subnet)
        vlan.dhcp_on = True
        vlan.primary_rack = rack_controller
        vlan.external_dhcp = dhcp_ip
        vlan.save()
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=dhcp_ip,
            subnet=subnet,
            interface=interface,
        )
        update_foreign_dhcp(rack_controller.system_id, interface.name, dhcp_ip)
        self.assertIsNone(reload_object(interface.vlan).external_dhcp)


class TestReportNeighbours(MAASServerTestCase):
    def test_calls_report_neighbours_on_rack_controller(self):
        rack_controller = factory.make_RackController()
        patched_report_neighbours = self.patch(
            RackController, "report_neighbours"
        )
        report_neighbours(rack_controller.system_id, sentinel.neighbours)
        self.assertThat(
            patched_report_neighbours, MockCalledOnceWith(sentinel.neighbours)
        )


class TestUpdateState(MAASServerTestCase):
    def test_scope_versions_snap(self):
        rack = factory.make_RackController()
        versions = {
            "snap": {
                "current": {
                    "revision": "1234",
                    "version": "3.0.0~alpha1-111-g.deadbeef",
                },
                "channel": "3.0/stable",
                "update": {
                    "revision": "5678",
                    "version": "3.0.0~alpha2-222-g.cafecafe",
                },
                "cohort": "abc123",
            },
        }
        update_state(rack.system_id, "versions", versions)
        controller_info = rack.controllerinfo
        self.assertEqual(
            controller_info.install_type, CONTROLLER_INSTALL_TYPE.SNAP
        )
        self.assertEqual(
            controller_info.version, "3.0.0~alpha1-111-g.deadbeef"
        )
        self.assertEqual(
            controller_info.update_version, "3.0.0~alpha2-222-g.cafecafe"
        )
        self.assertEqual(controller_info.update_origin, "3.0/stable")
        self.assertEqual(controller_info.snap_revision, "1234")
        self.assertEqual(controller_info.snap_update_revision, "5678")
        self.assertEqual(controller_info.snap_cohort, "abc123")

    def test_scope_versions_deb(self):
        rack = factory.make_RackController()
        versions = {
            "deb": {
                "current": {
                    "version": "3.0.0~alpha1-111-g.deadbeef",
                    "origin": "http://archive.ubuntu.com/ focal/main",
                },
                "update": {
                    "version": "3.0.0~alpha2-222-g.cafecafe",
                    "origin": "http://archive.ubuntu.com/ focal/main",
                },
            },
        }
        update_state(rack.system_id, "versions", versions)
        controller_info = rack.controllerinfo
        self.assertEqual(
            controller_info.install_type, CONTROLLER_INSTALL_TYPE.DEB
        )
        self.assertEqual(
            controller_info.version, "3.0.0~alpha1-111-g.deadbeef"
        )
        self.assertEqual(
            controller_info.update_version, "3.0.0~alpha2-222-g.cafecafe"
        )
        self.assertEqual(
            controller_info.update_origin,
            "http://archive.ubuntu.com/ focal/main",
        )
        self.assertEqual(controller_info.snap_revision, "")
        self.assertEqual(controller_info.snap_update_revision, "")
        self.assertEqual(controller_info.snap_cohort, "")

    def test_scope_versions_other(self):
        rack = factory.make_RackController()
        update_state(rack.system_id, "versions", {"something": "else"})
        # no ControllerInfo is created as the state is not updated
        self.assertFalse(hasattr(rack, "controllerinfo"))

    def test_scope_unhandled(self):
        rack = factory.make_RackController()
        self.assertRaises(
            NoSuchScope, update_state, rack.system_id, "other", {}
        )
