# Copyright 2013-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for boot configuration retrieval from RPC."""

__all__ = []

import random

from maasserver import server_address
from maasserver.enum import (
    BOOT_RESOURCE_TYPE,
    INTERFACE_TYPE,
    IPADDRESS_TYPE,
    NODE_STATUS,
)
from maasserver.models import (
    Config,
    Event,
    Node,
)
from maasserver.preseed import (
    compose_enlistment_preseed_url,
    compose_preseed_url,
)
from maasserver.rpc import boot as boot_module
from maasserver.rpc.boot import (
    event_log_pxe_request,
    get_config,
)
from maasserver.testing.architecture import make_usable_architecture
from maasserver.testing.config import RegionConfigurationFixture
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import reload_object
from maastesting.matchers import (
    MockCalledOnceWith,
    MockNotCalled,
)
from netaddr import IPNetwork
from provisioningserver.rpc.exceptions import BootConfigNoResponse
from testtools.matchers import (
    ContainsAll,
    StartsWith,
)


class TestGetConfig(MAASServerTestCase):

    def setUp(self):
        super(TestGetConfig, self).setUp()
        self.useFixture(RegionConfigurationFixture())

    def test__returns_all_kernel_parameters(self):
        rack_controller = factory.make_RackController()
        local_ip = factory.make_ip_address()
        remote_ip = factory.make_ip_address()
        self.assertThat(
            get_config(rack_controller.system_id, local_ip, remote_ip),
            ContainsAll([
                "arch",
                "subarch",
                "osystem",
                "release",
                "purpose",
                "hostname",
                "domain",
                "preseed_url",
                "fs_host",
                "log_host",
                "extra_opts",
            ]))

    def test__returns_success_for_known_node(self):
        rack_controller = factory.make_RackController()
        local_ip = factory.make_ip_address()
        remote_ip = factory.make_ip_address()
        node = factory.make_Node_with_Interface_on_Subnet(
            status=NODE_STATUS.DEPLOYING)
        mac = node.get_boot_interface().mac_address
        # Should not raise BootConfigNoResponse.
        get_config(rack_controller.system_id, local_ip, remote_ip, mac=mac)

    def test__raises_BootConfigNoResponse_for_unknown_node(self):
        rack_controller = factory.make_RackController()
        local_ip = factory.make_ip_address()
        remote_ip = factory.make_ip_address()
        mac = factory.make_mac_address(delimiter='-')
        self.assertRaises(
            BootConfigNoResponse, get_config,
            rack_controller.system_id, local_ip, remote_ip, mac=mac)

    def test__returns_success_for_detailed_but_unknown_node(self):
        rack_controller = factory.make_RackController()
        local_ip = factory.make_ip_address()
        remote_ip = factory.make_ip_address()
        architecture = make_usable_architecture(self)
        arch, subarch = architecture.split('/')
        mac = factory.make_mac_address(delimiter='-')
        # Should not raise BootConfigNoResponse.
        get_config(
            rack_controller.system_id, local_ip, remote_ip,
            arch=arch, subarch=subarch, mac=mac)

    def test__returns_global_kernel_params_for_enlisting_node(self):
        # An 'enlisting' node means it looks like a node with details but we
        # don't know about it yet.  It should still receive the global
        # kernel options.
        rack_controller = factory.make_RackController()
        local_ip = factory.make_ip_address()
        remote_ip = factory.make_ip_address()
        value = factory.make_string()
        Config.objects.set_config("kernel_opts", value)
        architecture = make_usable_architecture(self)
        arch, subarch = architecture.split('/')
        mac = factory.make_mac_address(delimiter='-')
        observed_config = get_config(
            rack_controller.system_id, local_ip, remote_ip,
            arch=arch, subarch=subarch, mac=mac)
        self.assertEqual(value, observed_config['extra_opts'])

    def test__uses_present_boot_image(self):
        rack_controller = factory.make_RackController()
        local_ip = factory.make_ip_address()
        remote_ip = factory.make_ip_address()
        osystem = Config.objects.get_config('commissioning_osystem')
        release = Config.objects.get_config('commissioning_distro_series')
        resource_name = '%s/%s' % (osystem, release)
        factory.make_usable_boot_resource(
            rtype=BOOT_RESOURCE_TYPE.SYNCED,
            name=resource_name, architecture='amd64/generic')
        observed_config = get_config(
            rack_controller.system_id, local_ip, remote_ip)
        self.assertEqual("amd64", observed_config["arch"])

    def test__defaults_to_i386_for_default(self):
        # As a lowest-common-denominator, i386 is chosen when the node is not
        # yet known to MAAS.
        rack_controller = factory.make_RackController()
        local_ip = factory.make_ip_address()
        remote_ip = factory.make_ip_address()
        expected_arch = tuple(
            make_usable_architecture(
                self, arch_name="i386", subarch_name="generic").split("/"))
        observed_config = get_config(
            rack_controller.system_id, local_ip, remote_ip)
        observed_arch = observed_config["arch"], observed_config["subarch"]
        self.assertEqual(expected_arch, observed_arch)

    def test__uses_fixed_hostname_for_enlisting_node(self):
        rack_controller = factory.make_RackController()
        local_ip = factory.make_ip_address()
        remote_ip = factory.make_ip_address()
        observed_config = get_config(
            rack_controller.system_id, local_ip, remote_ip)
        self.assertEqual(
            'maas-enlist', observed_config.get('hostname'))

    def test__uses_local_domain_for_enlisting_node(self):
        rack_controller = factory.make_RackController()
        local_ip = factory.make_ip_address()
        remote_ip = factory.make_ip_address()
        observed_config = get_config(
            rack_controller.system_id, local_ip, remote_ip)
        self.assertEqual(
            'local', observed_config.get('domain'))

    def test__splits_domain_from_node_hostname(self):
        rack_controller = factory.make_RackController()
        local_ip = factory.make_ip_address()
        remote_ip = factory.make_ip_address()
        host = factory.make_name('host')
        domainname = factory.make_name('domain')
        domain = factory.make_Domain(name=domainname)
        full_hostname = '.'.join([host, domainname])
        node = factory.make_Node_with_Interface_on_Subnet(
            hostname=full_hostname, domain=domain)
        interface = node.get_boot_interface()
        mac = interface.mac_address
        observed_config = get_config(
            rack_controller.system_id, local_ip, remote_ip, mac=mac)
        self.assertEqual(host, observed_config.get('hostname'))
        self.assertEqual(domainname, observed_config.get('domain'))

    def test__has_enlistment_preseed_url_for_default(self):
        rack_controller = factory.make_RackController()
        local_ip = factory.make_ip_address()
        remote_ip = factory.make_ip_address()
        observed_config = get_config(
            rack_controller.system_id, local_ip, remote_ip)
        self.assertEqual(
            compose_enlistment_preseed_url(),
            observed_config["preseed_url"])

    def test__enlistment_checks_default_min_hwe_kernel(self):
        rack_controller = factory.make_RackController()
        local_ip = factory.make_ip_address()
        remote_ip = factory.make_ip_address()
        arch = 'armhf'
        Config.objects.set_config('default_min_hwe_kernel', 'hwe-v')
        observed_config = get_config(
            rack_controller.system_id, local_ip, remote_ip, arch=arch)
        self.assertEqual(
            "hwe-v",
            observed_config["subarch"])

    def test__has_preseed_url_for_known_node(self):
        rack_controller = factory.make_RackController()
        local_ip = factory.make_ip_address()
        remote_ip = factory.make_ip_address()
        node = factory.make_Node_with_Interface_on_Subnet(
            status=NODE_STATUS.DEPLOYING)
        mac = node.get_boot_interface().mac_address
        observed_config = get_config(
            rack_controller.system_id, local_ip, remote_ip, mac=mac)
        self.assertEqual(
            compose_preseed_url(node, rack_controller),
            observed_config["preseed_url"])

    def test_preseed_url_for_known_node_uses_rack_url(self):
        rack_url = 'http://%s' % factory.make_name('host')
        network = IPNetwork("10.1.1/24")
        local_ip = factory.pick_ip_in_network(network)
        remote_ip = factory.make_ip_address()
        self.patch(
            server_address, 'resolve_hostname').return_value = {local_ip}
        rack_controller = factory.make_RackController(url=rack_url)
        node = factory.make_Node_with_Interface_on_Subnet(
            primary_rack=rack_controller)
        mac = node.get_boot_interface().mac_address
        observed_config = get_config(
            rack_controller.system_id, local_ip, remote_ip, mac=mac)
        self.assertThat(
            observed_config["preseed_url"],
            StartsWith(rack_url))

    def test__uses_boot_purpose_enlistment(self):
        # test that purpose is set to "commissioning" for
        # enlistment (when node is None).
        rack_controller = factory.make_RackController()
        local_ip = factory.make_ip_address()
        remote_ip = factory.make_ip_address()
        arch = 'armhf'
        observed_config = get_config(
            rack_controller.system_id, local_ip, remote_ip, arch=arch)
        self.assertEqual(
            "commissioning",
            observed_config["purpose"])

    def test__returns_enlist_config_if_no_architecture_provided(self):
        rack_controller = factory.make_RackController()
        local_ip = factory.make_ip_address()
        remote_ip = factory.make_ip_address()
        observed_config = get_config(
            rack_controller.system_id, local_ip, remote_ip)
        self.assertEqual('enlist', observed_config['purpose'])

    def test__returns_fs_host_as_cluster_controller(self):
        # The kernel parameter `fs_host` points to the cluster controller
        # address, which is passed over within the `local_ip` parameter.
        rack_controller = factory.make_RackController()
        local_ip = factory.make_ip_address()
        remote_ip = factory.make_ip_address()
        observed_config = get_config(
            rack_controller.system_id, local_ip, remote_ip)
        self.assertEqual(local_ip, observed_config["fs_host"])

    def test__returns_extra_kernel_options(self):
        rack_controller = factory.make_RackController()
        local_ip = factory.make_ip_address()
        remote_ip = factory.make_ip_address()
        extra_kernel_opts = factory.make_string()
        Config.objects.set_config('kernel_opts', extra_kernel_opts)
        observed_config = get_config(
            rack_controller.system_id, local_ip, remote_ip)
        self.assertEqual(extra_kernel_opts, observed_config['extra_opts'])

    def test__returns_empty_string_for_no_extra_kernel_opts(self):
        rack_controller = factory.make_RackController()
        local_ip = factory.make_ip_address()
        remote_ip = factory.make_ip_address()
        observed_config = get_config(
            rack_controller.system_id, local_ip, remote_ip)
        self.assertEqual('', observed_config['extra_opts'])

    def test__returns_commissioning_for_insane_state(self):
        rack_controller = factory.make_RackController()
        local_ip = factory.make_ip_address()
        remote_ip = factory.make_ip_address()
        node = factory.make_Node_with_Interface_on_Subnet(
            status=NODE_STATUS.BROKEN)
        mac = node.get_boot_interface().mac_address
        observed_config = get_config(
            rack_controller.system_id, local_ip, remote_ip, mac=mac)
        # The 'purpose' of the PXE config is 'commissioning' here
        # even if the 'purpose' returned by node.get_boot_purpose
        # is 'poweroff' because MAAS needs to bring the machine
        # up in a commissioning environment in order to power
        # the machine down.
        self.assertEqual('commissioning', observed_config['purpose'])

    def test__returns_commissioning_for_ready_node(self):
        rack_controller = factory.make_RackController()
        local_ip = factory.make_ip_address()
        remote_ip = factory.make_ip_address()
        node = factory.make_Node_with_Interface_on_Subnet(
            status=NODE_STATUS.READY)
        mac = node.get_boot_interface().mac_address
        observed_config = get_config(
            rack_controller.system_id, local_ip, remote_ip, mac=mac)
        self.assertEqual('commissioning', observed_config['purpose'])

    def test__calls_event_log_pxe_request(self):
        rack_controller = factory.make_RackController()
        local_ip = factory.make_ip_address()
        remote_ip = factory.make_ip_address()
        node = factory.make_Node_with_Interface_on_Subnet()
        mac = node.get_boot_interface().mac_address
        event_log_pxe_request = self.patch_autospec(
            boot_module, 'event_log_pxe_request')
        get_config(
            rack_controller.system_id, local_ip, remote_ip, mac=mac)
        self.assertThat(
            event_log_pxe_request,
            MockCalledOnceWith(node, node.get_boot_purpose()))

    def test_event_log_pxe_request_for_known_boot_purpose(self):
        purposes = [
            ("commissioning", "commissioning"),
            ("xinstall", "installation"),
            ("local", "local boot"),
            ("poweroff", "power off")]
        for purpose, description in purposes:
            node = factory.make_Node()
            event_log_pxe_request(node, purpose)
            self.assertEqual(
                description,
                Event.objects.get(node=node).description)

    def test__sets_boot_interface_when_empty(self):
        rack_controller = factory.make_RackController()
        local_ip = factory.make_ip_address()
        remote_ip = factory.make_ip_address()
        node = factory.make_Node_with_Interface_on_Subnet()
        nic = node.get_boot_interface()
        node.boot_interface = None
        node.save()
        mac = nic.mac_address
        get_config(
            rack_controller.system_id, local_ip, remote_ip, mac=mac)
        self.assertEqual(nic, reload_object(node).boot_interface)

    def test__updates_boot_interface_when_changed(self):
        rack_controller = factory.make_RackController()
        local_ip = factory.make_ip_address()
        remote_ip = factory.make_ip_address()
        node = factory.make_Node_with_Interface_on_Subnet()
        node.boot_interface = node.get_boot_interface()
        node.save()
        nic = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node, vlan=node.boot_interface.vlan)
        mac = nic.mac_address
        get_config(
            rack_controller.system_id, local_ip, remote_ip, mac=mac)
        self.assertEqual(nic, reload_object(node).boot_interface)

    def test__doesnt_update_boot_interface_when_same(self):
        rack_controller = factory.make_RackController()
        local_ip = factory.make_ip_address()
        remote_ip = factory.make_ip_address()
        node = factory.make_Node_with_Interface_on_Subnet()
        node.boot_interface = node.get_boot_interface()
        node.save()
        mac = node.boot_interface.mac_address
        node.boot_cluster_ip = local_ip
        node.save()
        mock_save = self.patch(Node, 'save')
        get_config(
            rack_controller.system_id, local_ip, remote_ip, mac=mac)
        self.assertThat(mock_save, MockNotCalled())

    def test__sets_boot_cluster_ip_when_empty(self):
        rack_controller = factory.make_RackController()
        local_ip = factory.make_ip_address()
        remote_ip = factory.make_ip_address()
        node = factory.make_Node_with_Interface_on_Subnet()
        mac = node.get_boot_interface().mac_address
        get_config(
            rack_controller.system_id, local_ip, remote_ip, mac=mac)
        self.assertEqual(local_ip, reload_object(node).boot_cluster_ip)

    def test__updates_boot_cluster_ip_when_changed(self):
        rack_controller = factory.make_RackController()
        local_ip = factory.make_ip_address()
        remote_ip = factory.make_ip_address()
        node = factory.make_Node_with_Interface_on_Subnet()
        node.boot_cluster_ip = factory.make_ipv4_address()
        node.save()
        mac = node.get_boot_interface().mac_address
        get_config(
            rack_controller.system_id, local_ip, remote_ip, mac=mac)
        self.assertEqual(local_ip, reload_object(node).boot_cluster_ip)

    def test__doesnt_update_boot_cluster_ip_when_same(self):
        rack_controller = factory.make_RackController()
        local_ip = factory.make_ip_address()
        remote_ip = factory.make_ip_address()
        node = factory.make_Node_with_Interface_on_Subnet()
        node.boot_interface = node.get_boot_interface()
        mac = node.boot_interface.mac_address
        node.boot_cluster_ip = local_ip
        node.save()
        mock_save = self.patch(Node, 'save')
        get_config(
            rack_controller.system_id, local_ip, remote_ip, mac=mac)
        self.assertThat(mock_save, MockNotCalled())

    def test__updates_bios_boot_method(self):
        rack_controller = factory.make_RackController()
        local_ip = factory.make_ip_address()
        remote_ip = factory.make_ip_address()
        node = factory.make_Node_with_Interface_on_Subnet()
        mac = node.get_boot_interface().mac_address
        get_config(
            rack_controller.system_id, local_ip, remote_ip,
            mac=mac, bios_boot_method="pxe")
        self.assertEqual('pxe', reload_object(node).bios_boot_method)

    def test__doesnt_update_bios_boot_method_when_same(self):
        rack_controller = factory.make_RackController()
        local_ip = factory.make_ip_address()
        remote_ip = factory.make_ip_address()
        node = factory.make_Node_with_Interface_on_Subnet(
            bios_boot_method='uefi')
        nic = node.get_boot_interface()
        mac = nic.mac_address
        node.boot_interface = nic
        node.boot_cluster_ip = local_ip
        node.save()
        mock_save = self.patch(Node, 'save')
        get_config(
            rack_controller.system_id, local_ip, remote_ip,
            mac=mac, bios_boot_method="uefi")
        self.assertThat(mock_save, MockNotCalled())

    def test__sets_boot_interface_vlan_to_match_rack_controller(self):
        rack_controller = factory.make_RackController()
        rack_fabric = factory.make_Fabric()
        rack_vlan = rack_fabric.get_default_vlan()
        rack_interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=rack_controller, vlan=rack_vlan)
        rack_subnet = factory.make_Subnet(vlan=rack_vlan)
        rack_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, subnet=rack_subnet,
            interface=rack_interface)
        remote_ip = factory.make_ip_address()
        node = factory.make_Node_with_Interface_on_Subnet()
        mac = node.get_boot_interface().mac_address
        get_config(
            rack_controller.system_id, rack_ip.ip, remote_ip, mac=mac)
        self.assertEqual(
            rack_vlan, reload_object(node).get_boot_interface().vlan)

    def test__returns_commissioning_os_series_for_other_oses(self):
        osystem = Config.objects.get_config('default_osystem')
        release = Config.objects.get_config('default_distro_series')
        rack_controller = factory.make_RackController()
        local_ip = factory.make_ip_address()
        remote_ip = factory.make_ip_address()
        node = factory.make_Node_with_Interface_on_Subnet(
            status=NODE_STATUS.DEPLOYING,
            osystem="centos",
            distro_series="centos71",
            architecture="amd64/generic",
            primary_rack=rack_controller)
        mac = node.get_boot_interface().mac_address
        observed_config = get_config(
            rack_controller.system_id, local_ip, remote_ip, mac=mac)
        self.assertEqual(osystem, observed_config["osystem"])
        self.assertEqual(release, observed_config["release"])

    def test__commissioning_node_uses_min_hwe_kernel(self):
        rack_controller = factory.make_RackController()
        local_ip = factory.make_ip_address()
        remote_ip = factory.make_ip_address()
        node = factory.make_Node_with_Interface_on_Subnet(
            status=NODE_STATUS.COMMISSIONING,
            min_hwe_kernel="hwe-v")
        mac = node.get_boot_interface().mac_address
        observed_config = get_config(
            rack_controller.system_id, local_ip, remote_ip, mac=mac)
        self.assertEqual(
            "hwe-v",
            observed_config["subarch"])

    def test__returns_ubuntu_os_series_for_ubuntu_xinstall(self):
        distro_series = random.choice(["trusty", "vivid", "wily", "xenial"])
        rack_controller = factory.make_RackController()
        local_ip = factory.make_ip_address()
        remote_ip = factory.make_ip_address()
        node = factory.make_Node_with_Interface_on_Subnet(
            status=NODE_STATUS.DEPLOYING, osystem='ubuntu',
            distro_series=distro_series, architecture="amd64/generic",
            primary_rack=rack_controller)
        mac = node.get_boot_interface().mac_address
        observed_config = get_config(
            rack_controller.system_id, local_ip, remote_ip, mac=mac)
        self.assertEqual(distro_series, observed_config["release"])

    def test__returns_commissioning_os_when_erasing_disks(self):
        commissioning_osystem = factory.make_name("os")
        Config.objects.set_config(
            "commissioning_osystem", commissioning_osystem)
        commissioning_series = factory.make_name("series")
        Config.objects.set_config(
            "commissioning_distro_series", commissioning_series)
        rack_controller = factory.make_RackController()
        local_ip = factory.make_ip_address()
        remote_ip = factory.make_ip_address()
        node = factory.make_Node_with_Interface_on_Subnet(
            status=NODE_STATUS.DISK_ERASING,
            osystem=factory.make_name("centos"),
            distro_series=factory.make_name("release"),
            primary_rack=rack_controller)
        mac = node.get_boot_interface().mac_address
        observed_config = get_config(
            rack_controller.system_id, local_ip, remote_ip, mac=mac)
        self.assertEqual(commissioning_osystem, observed_config['osystem'])
        self.assertEqual(commissioning_series, observed_config['release'])
