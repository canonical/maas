# Copyright 2013-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for PXE configuration retrieval from the API."""

__all__ = []

import http.client
import json
from unittest import skip

from crochet import TimeoutError
from django.conf import settings
from django.core.urlresolvers import reverse
from django.test.client import RequestFactory
from maasserver import (
    preseed as preseed_module,
    server_address,
)
from maasserver.api import pxeconfig as pxeconfig_module
from maasserver.api.pxeconfig import (
    event_log_pxe_request,
    find_rack_controller_for_pxeconfig_request,
    get_boot_image,
)
from maasserver.clusterrpc.testing.boot_images import make_rpc_boot_image
from maasserver.enum import (
    BOOT_RESOURCE_TYPE,
    INTERFACE_TYPE,
    NODE_STATUS,
)
from maasserver.models import (
    Config,
    Event,
    Interface,
    Node,
)
from maasserver.preseed import (
    compose_enlistment_preseed_url,
    compose_preseed_url,
)
from maasserver.testing.architecture import make_usable_architecture
from maasserver.testing.config import RegionConfigurationFixture
from maasserver.testing.factory import factory
from maasserver.testing.orm import reload_object
from maasserver.testing.testcase import MAASServerTestCase
from maastesting.fakemethod import FakeMethod
from maastesting.matchers import (
    MockCalledOnceWith,
    MockNotCalled,
)
from mock import sentinel
from netaddr import IPNetwork
from provisioningserver import kernel_opts
from provisioningserver.kernel_opts import KernelParameters
from provisioningserver.rpc.exceptions import NoConnectionsAvailable
from testtools.matchers import (
    Contains,
    ContainsAll,
    Equals,
    Is,
    MatchesListwise,
    StartsWith,
)


class TestGetBootImage(MAASServerTestCase):

    def setUp(self):
        super().setUp()
        self.rackcontroller = factory.make_RackController()

    def test__returns_None_when_connection_unavailable(self):
        self.patch(
            pxeconfig_module,
            'get_boot_images_for').side_effect = NoConnectionsAvailable
        self.assertEqual(
            None,
            get_boot_image(
                self.rackcontroller, sentinel.osystem,
                sentinel.architecture, sentinel.subarchitecture,
                sentinel.series, sentinel.purpose))

    def test__returns_None_when_timeout_error(self):
        self.patch(
            pxeconfig_module,
            'get_boot_images_for').side_effect = TimeoutError
        self.assertEqual(
            None,
            get_boot_image(
                self.rackcontroller, sentinel.osystem,
                sentinel.architecture, sentinel.subarchitecture,
                sentinel.series, sentinel.purpose))

    def test__returns_matching_image(self):
        subarch = factory.make_name('subarch')
        purpose = factory.make_name('purpose')
        boot_image = make_rpc_boot_image(
            subarchitecture=subarch, purpose=purpose)
        other_images = [make_rpc_boot_image() for _ in range(3)]
        self.patch(
            pxeconfig_module,
            'get_boot_images_for').return_value = other_images + [boot_image]
        self.assertEqual(
            boot_image,
            get_boot_image(
                self.rackcontroller, sentinel.osystem,
                sentinel.architecture, subarch,
                sentinel.series, purpose))

    def test__returns_None_on_no_matching_image(self):
        subarch = factory.make_name('subarch')
        purpose = factory.make_name('purpose')
        other_images = [make_rpc_boot_image() for _ in range(3)]
        self.patch(
            pxeconfig_module,
            'get_boot_images_for').return_value = other_images
        self.assertEqual(
            None,
            get_boot_image(
                self.rackcontroller, sentinel.osystem,
                sentinel.architecture, subarch,
                sentinel.series, purpose))

    def test__returns_None_immediately_if_purpose_is_local(self):
        self.patch(pxeconfig_module, 'get_boot_images_for')
        self.expectThat(
            get_boot_image(
                self.rackcontroller, sentinel.osystem,
                sentinel.architecture, sentinel.subarchitecture,
                sentinel.series, "local"),
            Is(None))
        self.expectThat(pxeconfig_module.get_boot_images_for, MockNotCalled())


class TestPXEConfigAPI(MAASServerTestCase):
    def setUp(self):
        super(TestPXEConfigAPI, self).setUp()
        self.useFixture(RegionConfigurationFixture())

    def get_default_params(self, rack_controller=None):
        if rack_controller is None:
            rack_controller = factory.make_RackController()
        return {
            "local": factory.make_ipv4_address(),
            "remote": factory.make_ipv4_address(),
            "rackcontroller_id": rack_controller.system_id,
            }

    def get_mac_params(self):
        node = factory.make_Node_with_Interface_on_Subnet(
            status=NODE_STATUS.DEPLOYING)
        arch, subarch = node.split_arch()
        image = make_rpc_boot_image(
            osystem=node.get_osystem(), release=node.get_distro_series(),
            architecture=arch, subarchitecture=subarch,
            purpose='install')
        self.patch(
            preseed_module,
            'get_boot_images_for').return_value = [image]
        params = self.get_default_params()
        params['mac'] = node.get_boot_interface().mac_address
        return params

    def get_pxeconfig(self, params=None):
        """Make a request to `pxeconfig`, and return its response dict."""
        if params is None:
            params = self.get_default_params()
        response = self.client.get(reverse('pxeconfig'), params)
        return json.loads(response.content.decode(settings.DEFAULT_CHARSET))

    @skip("XXX: GavinPanella 2016-02-24 bug=1549206: Fails spuriously.")
    def test_pxeconfig_returns_json(self):
        params = self.get_default_params()
        response = self.client.get(
            reverse('pxeconfig'), params)
        self.assertThat(
            (
                response.status_code,
                response['Content-Type'],
                response.content,
                response.content.decode(settings.DEFAULT_CHARSET),
            ),
            MatchesListwise(
                (
                    Equals(http.client.OK),
                    Equals("application/json"),
                    StartsWith(b'{'),
                    Contains('arch'),
                )),
            response)

    def test_pxeconfig_returns_all_kernel_parameters(self):
        params = self.get_default_params()
        self.assertThat(
            self.get_pxeconfig(params),
            ContainsAll(KernelParameters._fields))

    def test_pxeconfig_returns_success_for_known_node(self):
        params = self.get_mac_params()
        response = self.client.get(reverse('pxeconfig'), params)
        self.assertEqual(http.client.OK, response.status_code)

    def test_pxeconfig_returns_no_content_for_unknown_node(self):
        params = dict(
            mac=factory.make_mac_address(delimiter='-'),
            local=factory.make_ipv4_address())
        response = self.client.get(reverse('pxeconfig'), params)
        self.assertEqual(http.client.NO_CONTENT, response.status_code)

    def test_pxeconfig_returns_success_for_detailed_but_unknown_node(self):
        architecture = make_usable_architecture(self)
        arch, subarch = architecture.split('/')
        rack = factory.make_RackController()
        params = dict(
            self.get_default_params(),
            mac=factory.make_mac_address(delimiter='-'),
            arch=arch,
            subarch=subarch,
            rackcontroller_id=rack.system_id)
        response = self.client.get(reverse('pxeconfig'), params)
        self.assertEqual(http.client.OK, response.status_code)

    def test_pxeconfig_returns_global_kernel_params_for_enlisting_node(self):
        # An 'enlisting' node means it looks like a node with details but we
        # don't know about it yet.  It should still receive the global
        # kernel options.
        value = factory.make_string()
        Config.objects.set_config("kernel_opts", value)
        architecture = make_usable_architecture(self)
        arch, subarch = architecture.split('/')
        rack = factory.make_RackController()
        params = dict(
            self.get_default_params(),
            mac=factory.make_mac_address(delimiter='-'),
            arch=arch,
            subarch=subarch,
            rackcontroller_id=rack.system_id)
        response = self.client.get(reverse('pxeconfig'), params)
        response_dict = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))
        self.assertEqual(value, response_dict['extra_opts'])

    def test_pxeconfig_uses_present_boot_image(self):
        osystem = Config.objects.get_config('commissioning_osystem')
        release = Config.objects.get_config('commissioning_distro_series')
        resource_name = '%s/%s' % (osystem, release)
        factory.make_usable_boot_resource(
            rtype=BOOT_RESOURCE_TYPE.SYNCED,
            name=resource_name, architecture='amd64/generic')
        params = self.get_default_params()
        params_out = self.get_pxeconfig(params)
        self.assertEqual("amd64", params_out["arch"])

    def test_pxeconfig_defaults_to_i386_for_default(self):
        # As a lowest-common-denominator, i386 is chosen when the node is not
        # yet known to MAAS.
        expected_arch = tuple(
            make_usable_architecture(
                self, arch_name="i386", subarch_name="generic").split("/"))
        params = self.get_default_params()
        params_out = self.get_pxeconfig(params)
        observed_arch = params_out["arch"], params_out["subarch"]
        self.assertEqual(expected_arch, observed_arch)

    def test_pxeconfig_uses_fixed_hostname_for_enlisting_node(self):
        params = self.get_default_params()
        self.assertEqual(
            'maas-enlist', self.get_pxeconfig(params).get('hostname'))

    def test_pxeconfig_uses_local_domain_for_enlisting_node(self):
        params = self.get_default_params()
        self.assertEqual(
            "local",
            self.get_pxeconfig(params).get('domain'))

    def test_pxeconfig_splits_domain_from_node_hostname(self):
        host = factory.make_name('host')
        domainname = factory.make_name('domain')
        domain = factory.make_Domain(name=domainname)
        full_hostname = '.'.join([host, domainname])
        node = factory.make_Node_with_Interface_on_Subnet(
            hostname=full_hostname, domain=domain)
        interface = node.get_boot_interface()
        params = self.get_default_params()
        params['mac'] = interface.mac_address
        pxe_config = self.get_pxeconfig(params)
        self.assertEqual(host, pxe_config.get('hostname'))
        self.assertNotIn(domain, pxe_config.values())

    def test_pxeconfig_uses_domain_for_node(self):
        node = factory.make_Node_with_Interface_on_Subnet()
        interface = node.get_boot_interface()
        params = self.get_default_params()
        params['mac'] = interface.mac_address
        self.assertEqual(
            node.domain.name,
            self.get_pxeconfig(params).get('domain'))

    def get_without_param(self, param):
        """Request a `pxeconfig()` response, but omit `param` from request."""
        params = self.get_params()
        del params[param]
        return self.client.get(reverse('pxeconfig'), params)

    def silence_get_ephemeral_name(self):
        # Silence `get_ephemeral_name` to avoid having to fetch the
        # ephemeral name from the filesystem.
        self.patch(
            kernel_opts, 'get_ephemeral_name',
            FakeMethod(result=factory.make_string()))

    def test_pxeconfig_has_enlistment_preseed_url_for_default(self):
        self.silence_get_ephemeral_name()
        params = self.get_default_params()
        response = self.client.get(reverse('pxeconfig'), params)
        self.assertEqual(
            compose_enlistment_preseed_url(),
            json.loads(response.content.decode(
                settings.DEFAULT_CHARSET))["preseed_url"])

    def test_pxeconfig_enlistment_preseed_url_detects_request_origin(self):
        self.silence_get_ephemeral_name()
        hostname = factory.make_hostname()
        rack_url = 'http://%s' % hostname
        network = IPNetwork("10.1.1/24")
        ip = factory.pick_ip_in_network(network)
        self.patch(server_address, 'resolve_hostname').return_value = {ip}
        rack_controller = factory.make_RackController(url=rack_url)
        subnet = factory.make_Subnet(cidr=str(network.cidr), dhcp_on=True)
        subnet.vlan.primary_rack = rack_controller
        subnet.vlan.save()
        params = self.get_default_params(rack_controller)
        del params['rackcontroller_id']

        # Simulate that the request originates from ip by setting
        # 'REMOTE_ADDR'.
        response = self.client.get(
            reverse('pxeconfig'), params, REMOTE_ADDR=ip)
        self.assertThat(
            json.loads(
                response.content.decode(
                    settings.DEFAULT_CHARSET))["preseed_url"],
            StartsWith(rack_url))

    def test_pxeconfig_enlistment_log_host_url_detects_request_origin(self):
        self.silence_get_ephemeral_name()
        hostname = factory.make_hostname()
        rack_url = 'http://%s' % hostname
        network = IPNetwork("10.1.1/24")
        ip = factory.pick_ip_in_network(network)
        mock = self.patch(server_address, 'resolve_hostname')
        mock.return_value = {ip}
        rack_controller = factory.make_RackController(url=rack_url)
        subnet = factory.make_Subnet(cidr=str(network.cidr), dhcp_on=True)
        subnet.vlan.primary_rack = rack_controller
        subnet.vlan.save()
        params = self.get_default_params(rack_controller)
        del params['rackcontroller_id']

        # Simulate that the request originates from ip by setting
        # 'REMOTE_ADDR'.
        response = self.client.get(
            reverse('pxeconfig'), params, REMOTE_ADDR=ip)
        self.assertEqual(
            (ip, hostname),
            (json.loads(
                response.content.decode(
                    settings.DEFAULT_CHARSET))["log_host"],
             mock.call_args[0][0]))

    def test_pxeconfig_enlistment_checks_default_min_hwe_kernel(self):
        params = self.get_default_params()
        params['arch'] = 'armhf'
        Config.objects.set_config('default_min_hwe_kernel', 'hwe-v')
        response = self.client.get(reverse('pxeconfig'), params)
        self.assertEqual(
            "hwe-v",
            json.loads(
                response.content.decode(settings.DEFAULT_CHARSET))["subarch"])

    def test_pxeconfig_has_preseed_url_for_known_node(self):
        params = self.get_mac_params()
        node = Interface.objects.get(mac_address=params['mac']).node
        response = self.client.get(reverse('pxeconfig'), params)
        self.assertEqual(
            compose_preseed_url(node),
            json.loads(
                response.content.decode(
                    settings.DEFAULT_CHARSET))["preseed_url"])

    def test_find_rack_for_pxeconfig_request_uses_rack_system_id(self):
        params = self.get_mac_params()
        rack = factory.make_RackController()
        params['rackcontroller_id'] = rack.system_id
        request = RequestFactory().get(reverse('pxeconfig'), params)
        self.assertEqual(
            rack,
            find_rack_controller_for_pxeconfig_request(request))

    def test_preseed_url_for_known_node_uses_rack_url(self):
        rack_url = 'http://%s' % factory.make_name('host')
        network = IPNetwork("10.1.1/24")
        ip = factory.pick_ip_in_network(network)
        self.patch(server_address, 'resolve_hostname').return_value = {ip}
        rack_controller = factory.make_RackController(url=rack_url)
        node = factory.make_Node_with_Interface_on_Subnet(
            primary_rack=rack_controller)
        params = self.get_default_params()
        params['mac'] = str(node.get_boot_interface().mac_address)

        # Simulate that the request originates from ip by setting
        # 'REMOTE_ADDR'.
        response = self.client.get(
            reverse('pxeconfig'), params, REMOTE_ADDR=ip)
        self.assertThat(
            json.loads(
                response.content.decode(
                    settings.DEFAULT_CHARSET))["preseed_url"],
            StartsWith(rack_url))

    def test_pxeconfig_uses_boot_purpose_enlistment(self):
        # test that purpose is set to "commissioning" for
        # enlistment (when node is None).
        params = self.get_default_params()
        params['arch'] = 'armhf'
        response = self.client.get(reverse('pxeconfig'), params)
        self.assertEqual(
            "commissioning",
            json.loads(
                response.content.decode(settings.DEFAULT_CHARSET))["purpose"])

    def test_pxeconfig_returns_enlist_config_if_no_architecture_provided(self):
        params = self.get_default_params()
        pxe_config = self.get_pxeconfig(params)
        self.assertEqual('enlist', pxe_config['purpose'])

    def test_pxeconfig_returns_fs_host_as_cluster_controller(self):
        # The kernel parameter `fs_host` points to the cluster controller
        # address, which is passed over within the `local` parameter.
        params = self.get_default_params()
        kernel_params = KernelParameters(**self.get_pxeconfig(params))
        self.assertEqual(params["local"], kernel_params.fs_host)

    def test_pxeconfig_returns_extra_kernel_options(self):
        extra_kernel_opts = factory.make_string()
        Config.objects.set_config('kernel_opts', extra_kernel_opts)
        params = self.get_mac_params()
        pxe_config = self.get_pxeconfig(params)
        self.assertEqual(extra_kernel_opts, pxe_config['extra_opts'])

    def test_pxeconfig_returns_None_for_extra_kernel_opts(self):
        params = self.get_mac_params()
        pxe_config = self.get_pxeconfig(params)
        self.assertEqual(None, pxe_config['extra_opts'])

    def test_pxeconfig_returns_commissioning_for_insane_state(self):
        node = factory.make_Node_with_Interface_on_Subnet(
            status=NODE_STATUS.BROKEN)
        nic = node.get_boot_interface()
        params = self.get_default_params()
        params['mac'] = nic.mac_address
        pxe_config = self.get_pxeconfig(params)
        # The 'purpose' of the PXE config is 'commissioning' here
        # even if the 'purpose' returned by node.get_boot_purpose
        # is 'poweroff' because MAAS needs to bring the machine
        # up in a commissioning environment in order to power
        # the machine down.
        self.assertEqual('commissioning', pxe_config['purpose'])

    def test_pxeconfig_returns_commissioning_for_ready_node(self):
        node = factory.make_Node_with_Interface_on_Subnet(
            status=NODE_STATUS.READY)
        nic = node.get_boot_interface()
        params = self.get_default_params()
        params['mac'] = nic.mac_address
        pxe_config = self.get_pxeconfig(params)
        self.assertEqual('commissioning', pxe_config['purpose'])

    def test_pxeconfig_returns_image_subarch_not_node_subarch(self):
        # In the scenario such as deploying trusty on an hwe-s subarch
        # node, the code will have fallen back to using trusty's generic
        # image as per the supported_subarches on the image. However,
        # pxeconfig needs to make sure the image path refers to the
        # subarch from the image, rather than the requested one.
        osystem = 'ubuntu'
        release = Config.objects.get_config('default_distro_series')
        rack = factory.make_RackController()
        generic_image = make_rpc_boot_image(
            osystem=osystem, release=release,
            architecture="amd64", subarchitecture="generic",
            purpose='install')
        hwe_s_image = make_rpc_boot_image(
            osystem=osystem, release=release,
            architecture="amd64", subarchitecture="hwe-s",
            purpose='install')
        self.patch(
            preseed_module,
            'get_boot_images_for').return_value = [generic_image, hwe_s_image]
        self.patch(
            pxeconfig_module,
            'get_boot_images_for').return_value = [generic_image, hwe_s_image]
        node = factory.make_Node_with_Interface_on_Subnet(
            status=NODE_STATUS.DEPLOYING,
            architecture="amd64/hwe-s",
            primary_rack=rack)
        params = self.get_default_params()
        params['rackcontroller_id'] = rack.system_id
        params['mac'] = node.get_boot_interface().mac_address
        params['arch'] = "amd64"
        params['subarch'] = "hwe-s"

        params_out = self.get_pxeconfig(params)
        self.assertEqual("hwe-s", params_out["subarch"])

    def test_pxeconfig_calls_event_log_pxe_request(self):
        node = factory.make_Node_with_Interface_on_Subnet()
        nic = node.get_boot_interface()
        params = self.get_default_params()
        params['mac'] = nic.mac_address
        event_log_pxe_request = self.patch_autospec(
            pxeconfig_module, 'event_log_pxe_request')
        self.client.get(reverse('pxeconfig'), params)
        self.assertThat(
            event_log_pxe_request,
            MockCalledOnceWith(node, node.get_boot_purpose()))

    def test_event_log_pxe_request_for_known_boot_purpose(self):
        purposes = [
            ("commissioning", "commissioning"),
            ("install", "d-i install"),
            ("xinstall", "curtin install"),
            ("local", "local boot"),
            ("poweroff", "power off")]
        for purpose, description in purposes:
            node = factory.make_Node()
            event_log_pxe_request(node, purpose)
            self.assertEqual(
                description,
                Event.objects.get(node=node).description)

    def test_pxeconfig_sets_boot_interface_when_empty(self):
        node = factory.make_Node_with_Interface_on_Subnet()
        nic = node.get_boot_interface()
        node.boot_interface = None
        node.save()
        params = self.get_default_params()
        params['mac'] = nic.mac_address
        self.client.get(reverse('pxeconfig'), params)
        node = reload_object(node)
        self.assertEqual(nic, node.boot_interface)

    def test_pxeconfig_updates_boot_interface_when_changed(self):
        node = factory.make_Node_with_Interface_on_Subnet()
        node.boot_interface = node.get_boot_interface()
        node.save()
        nic = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node, vlan=node.boot_interface.vlan)
        params = self.get_default_params()
        params['mac'] = nic.mac_address
        self.client.get(reverse('pxeconfig'), params)
        node = reload_object(node)
        self.assertEqual(nic, node.boot_interface)

    def test_pxeconfig_doesnt_update_boot_interface_when_same(self):
        node = factory.make_Node_with_Interface_on_Subnet()
        node.boot_interface = node.get_boot_interface()
        node.save()
        params = self.get_default_params()
        params['mac'] = node.boot_interface.mac_address
        node.boot_cluster_ip = params['local']
        node.save()
        mock_save = self.patch(Node, 'save')
        self.client.get(reverse('pxeconfig'), params)
        self.assertThat(mock_save, MockNotCalled())

    def test_pxeconfig_sets_boot_cluster_ip_when_empty(self):
        node = factory.make_Node_with_Interface_on_Subnet()
        params = self.get_default_params()
        params['mac'] = node.get_boot_interface().mac_address
        self.client.get(reverse('pxeconfig'), params)
        node = reload_object(node)
        self.assertEqual(params['local'], node.boot_cluster_ip)

    def test_pxeconfig_updates_boot_cluster_ip_when_changed(self):
        node = factory.make_Node_with_Interface_on_Subnet()
        node.boot_cluster_ip = factory.make_ipv4_address()
        node.save()
        params = self.get_default_params()
        params['mac'] = node.get_boot_interface().mac_address
        self.client.get(reverse('pxeconfig'), params)
        node = reload_object(node)
        self.assertEqual(params['local'], node.boot_cluster_ip)

    def test_pxeconfig_doesnt_update_boot_cluster_ip_when_same(self):
        node = factory.make_Node_with_Interface_on_Subnet()
        node.boot_interface = node.get_boot_interface()
        params = self.get_default_params()
        params['mac'] = node.boot_interface.mac_address
        node.boot_cluster_ip = params['local']
        node.save()
        mock_save = self.patch(Node, 'save')
        self.client.get(reverse('pxeconfig'), params)
        self.assertThat(mock_save, MockNotCalled())

    def test_pxeconfig_updates_bios_boot_method(self):
        node = factory.make_Node_with_Interface_on_Subnet()
        nic = node.get_boot_interface()
        params = self.get_default_params()
        params['mac'] = nic.mac_address
        params['bios_boot_method'] = 'pxe'
        self.client.get(reverse('pxeconfig'), params)
        node = reload_object(node)
        self.assertEqual('pxe', node.bios_boot_method)

    def test_pxeconfig_doesnt_update_bios_boot_method_when_same(self):
        node = factory.make_Node_with_Interface_on_Subnet(
            bios_boot_method='uefi')
        nic = node.get_boot_interface()
        params = self.get_default_params()
        params['mac'] = nic.mac_address
        params['bios_boot_method'] = 'uefi'
        node.boot_interface = nic
        node.boot_cluster_ip = params['local']
        node.save()
        mock_save = self.patch(Node, 'save')
        self.client.get(reverse('pxeconfig'), params)
        self.assertThat(mock_save, MockNotCalled())

    def test_pxeconfig_returns_commissioning_os_series_for_other_oses(self):
        osystem = Config.objects.get_config('default_osystem')
        release = Config.objects.get_config('default_distro_series')
        os_image = make_rpc_boot_image(purpose='xinstall')
        architecture = '%s/%s' % (
            os_image['architecture'], os_image['subarchitecture'])
        self.patch(
            preseed_module,
            'get_boot_images_for').return_value = [os_image]
        self.patch(
            pxeconfig_module,
            'get_boot_images_for').return_value = [os_image]
        rack_controller = factory.make_RackController()
        node = factory.make_Node_with_Interface_on_Subnet(
            status=NODE_STATUS.DEPLOYING,
            osystem=os_image['osystem'],
            distro_series=os_image['release'],
            architecture=architecture,
            primary_rack=rack_controller)
        params = self.get_default_params()
        params['rackcontroller_id'] = rack_controller.system_id
        params['mac'] = node.get_boot_interface().mac_address
        params_out = self.get_pxeconfig(params)
        self.assertEqual(osystem, params_out["osystem"])
        self.assertEqual(release, params_out["release"])

    def test_pxeconfig_commissioning_node_uses_min_hwe_kernel(self):
        node = factory.make_Node_with_Interface_on_Subnet(
            min_hwe_kernel="hwe-v")
        nic = node.get_boot_interface()
        self.patch(Node, 'get_boot_purpose').return_value = "commissioning"
        params = self.get_default_params()
        params['mac'] = nic.mac_address
        response = self.client.get(reverse('pxeconfig'), params)
        self.assertEqual(
            "hwe-v",
            json.loads(
                response.content.decode(settings.DEFAULT_CHARSET))["subarch"])

    def test_pxeconfig_returns_ubuntu_os_series_for_ubuntu_xinstall(self):
        ubuntu_image = make_rpc_boot_image(
            osystem='ubuntu', purpose='xinstall')
        architecture = '%s/%s' % (
            ubuntu_image['architecture'], ubuntu_image['subarchitecture'])
        self.patch(
            preseed_module,
            'get_boot_images_for').return_value = [ubuntu_image]
        self.patch(
            pxeconfig_module,
            'get_boot_images_for').return_value = [ubuntu_image]
        rack_controller = factory.make_RackController()
        node = factory.make_Node_with_Interface_on_Subnet(
            status=NODE_STATUS.DEPLOYING, osystem='ubuntu',
            distro_series=ubuntu_image['release'], architecture=architecture,
            primary_rack=rack_controller)
        params = self.get_default_params()
        params['rackcontroller_id'] = rack_controller.system_id
        params['mac'] = node.get_boot_interface().mac_address
        params_out = self.get_pxeconfig(params)
        self.assertEqual(ubuntu_image['release'], params_out["release"])

    def test_pxeconfig_returns_commissioning_os_when_erasing_disks(self):
        commissioning_osystem = factory.make_name("os")
        Config.objects.set_config(
            "commissioning_osystem", commissioning_osystem)
        commissioning_series = factory.make_name("series")
        Config.objects.set_config(
            "commissioning_distro_series", commissioning_series)
        rack_controller = factory.make_RackController()
        node = factory.make_Node_with_Interface_on_Subnet(
            status=NODE_STATUS.DISK_ERASING,
            osystem=factory.make_name("centos"),
            distro_series=factory.make_name("release"),
            primary_rack=rack_controller)
        params = self.get_default_params()
        params['rackcontroller_id'] = rack_controller.system_id
        params['mac'] = node.get_boot_interface().mac_address
        params_out = self.get_pxeconfig(params)
        self.assertEqual(commissioning_osystem, params_out['osystem'])
        self.assertEqual(commissioning_series, params_out['release'])
