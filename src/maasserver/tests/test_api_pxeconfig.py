# Copyright 2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for PXE configuration retrieval from the API."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import httplib
import json

from django.core.urlresolvers import reverse
from django.test.client import RequestFactory
from maasserver import (
    api,
    server_address,
    )
from maasserver.api import find_nodegroup_for_pxeconfig_request
from maasserver.enum import (
    ARCHITECTURE,
    NODE_STATUS,
    )
from maasserver.models import (
    Config,
    MACAddress,
    )
from maasserver.preseed import (
    compose_enlistment_preseed_url,
    compose_preseed_url,
    )
from maasserver.testing.api import AnonAPITestCase
from maasserver.testing.factory import factory
from maastesting.fakemethod import FakeMethod
from maastesting.matchers import ContainsAll
from mock import Mock
from netaddr import IPNetwork
from provisioningserver import kernel_opts
from provisioningserver.kernel_opts import KernelParameters
from testtools.matchers import (
    Contains,
    Equals,
    MatchesListwise,
    StartsWith,
    )


class TestPXEConfigAPI(AnonAPITestCase):

    def get_default_params(self):
        return {
            "local": factory.getRandomIPAddress(),
            "remote": factory.getRandomIPAddress(),
            }

    def get_mac_params(self):
        params = self.get_default_params()
        params['mac'] = factory.make_mac_address().mac_address
        return params

    def get_pxeconfig(self, params=None):
        """Make a request to `pxeconfig`, and return its response dict."""
        if params is None:
            params = self.get_default_params()
        response = self.client.get(reverse('pxeconfig'), params)
        return json.loads(response.content)

    def test_pxeconfig_returns_json(self):
        response = self.client.get(
            reverse('pxeconfig'), self.get_default_params())
        self.assertThat(
            (
                response.status_code,
                response['Content-Type'],
                response.content,
                response.content,
            ),
            MatchesListwise(
                (
                    Equals(httplib.OK),
                    Equals("application/json"),
                    StartsWith(b'{'),
                    Contains('arch'),
                )),
            response)

    def test_pxeconfig_returns_all_kernel_parameters(self):
        self.assertThat(
            self.get_pxeconfig(),
            ContainsAll(KernelParameters._fields))

    def test_pxeconfig_returns_success_for_known_node(self):
        params = self.get_mac_params()
        response = self.client.get(reverse('pxeconfig'), params)
        self.assertEqual(httplib.OK, response.status_code)

    def test_pxeconfig_returns_no_content_for_unknown_node(self):
        params = dict(mac=factory.getRandomMACAddress(delimiter='-'))
        response = self.client.get(reverse('pxeconfig'), params)
        self.assertEqual(httplib.NO_CONTENT, response.status_code)

    def test_pxeconfig_returns_success_for_detailed_but_unknown_node(self):
        architecture = factory.getRandomEnum(ARCHITECTURE)
        arch, subarch = architecture.split('/')
        params = dict(
            self.get_default_params(),
            mac=factory.getRandomMACAddress(delimiter='-'),
            arch=arch,
            subarch=subarch)
        response = self.client.get(reverse('pxeconfig'), params)
        self.assertEqual(httplib.OK, response.status_code)

    def test_pxeconfig_returns_global_kernel_params_for_enlisting_node(self):
        # An 'enlisting' node means it looks like a node with details but we
        # don't know about it yet.  It should still receive the global
        # kernel options.
        value = factory.getRandomString()
        Config.objects.set_config("kernel_opts", value)
        architecture = factory.getRandomEnum(ARCHITECTURE)
        arch, subarch = architecture.split('/')
        params = dict(
            self.get_default_params(),
            mac=factory.getRandomMACAddress(delimiter='-'),
            arch=arch,
            subarch=subarch)
        response = self.client.get(reverse('pxeconfig'), params)
        response_dict = json.loads(response.content)
        self.assertEqual(value, response_dict['extra_opts'])

    def test_pxeconfig_uses_present_boot_image(self):
        release = Config.objects.get_config('commissioning_distro_series')
        nodegroup = factory.make_node_group()
        factory.make_boot_image(
            architecture="amd64", release=release, nodegroup=nodegroup,
            purpose="commissioning")
        params = self.get_default_params()
        params['cluster_uuid'] = nodegroup.uuid
        params_out = self.get_pxeconfig(params)
        self.assertEqual("amd64", params_out["arch"])

    def test_pxeconfig_defaults_to_i386_for_default(self):
        # As a lowest-common-denominator, i386 is chosen when the node is not
        # yet known to MAAS.
        expected_arch = tuple(ARCHITECTURE.i386.split('/'))
        params_out = self.get_pxeconfig()
        observed_arch = params_out["arch"], params_out["subarch"]
        self.assertEqual(expected_arch, observed_arch)

    def test_pxeconfig_uses_fixed_hostname_for_enlisting_node(self):
        self.assertEqual('maas-enlist', self.get_pxeconfig().get('hostname'))

    def test_pxeconfig_uses_enlistment_domain_for_enlisting_node(self):
        self.assertEqual(
            Config.objects.get_config('enlistment_domain'),
            self.get_pxeconfig().get('domain'))

    def test_pxeconfig_splits_domain_from_node_hostname(self):
        host = factory.make_name('host')
        domain = factory.make_name('domain')
        full_hostname = '.'.join([host, domain])
        node = factory.make_node(hostname=full_hostname)
        mac = factory.make_mac_address(node=node)
        params = self.get_default_params()
        params['mac'] = mac.mac_address
        pxe_config = self.get_pxeconfig(params)
        self.assertEqual(host, pxe_config.get('hostname'))
        self.assertNotIn(domain, pxe_config.values())

    def test_pxeconfig_uses_nodegroup_domain_for_node(self):
        mac = factory.make_mac_address()
        params = self.get_default_params()
        params['mac'] = mac
        self.assertEqual(
            mac.node.nodegroup.name,
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
            FakeMethod(result=factory.getRandomString()))

    def test_pxeconfig_has_enlistment_preseed_url_for_default(self):
        self.silence_get_ephemeral_name()
        params = self.get_default_params()
        response = self.client.get(reverse('pxeconfig'), params)
        self.assertEqual(
            compose_enlistment_preseed_url(),
            json.loads(response.content)["preseed_url"])

    def test_pxeconfig_enlistment_preseed_url_detects_request_origin(self):
        self.silence_get_ephemeral_name()
        hostname = factory.make_hostname()
        ng_url = 'http://%s' % hostname
        network = IPNetwork("10.1.1/24")
        ip = factory.getRandomIPInNetwork(network)
        self.patch(server_address, 'gethostbyname', Mock(return_value=ip))
        factory.make_node_group(maas_url=ng_url, network=network)
        params = self.get_default_params()

        # Simulate that the request originates from ip by setting
        # 'REMOTE_ADDR'.
        response = self.client.get(
            reverse('pxeconfig'), params, REMOTE_ADDR=ip)
        self.assertThat(
            json.loads(response.content)["preseed_url"],
            StartsWith(ng_url))

    def test_pxeconfig_enlistment_log_host_url_detects_request_origin(self):
        self.silence_get_ephemeral_name()
        hostname = factory.make_hostname()
        ng_url = 'http://%s' % hostname
        network = IPNetwork("10.1.1/24")
        ip = factory.getRandomIPInNetwork(network)
        mock = self.patch(
            server_address, 'gethostbyname', Mock(return_value=ip))
        factory.make_node_group(maas_url=ng_url, network=network)
        params = self.get_default_params()

        # Simulate that the request originates from ip by setting
        # 'REMOTE_ADDR'.
        response = self.client.get(
            reverse('pxeconfig'), params, REMOTE_ADDR=ip)
        self.assertEqual(
            (ip, hostname),
            (json.loads(response.content)["log_host"], mock.call_args[0][0]))

    def test_pxeconfig_has_preseed_url_for_known_node(self):
        params = self.get_mac_params()
        node = MACAddress.objects.get(mac_address=params['mac']).node
        response = self.client.get(reverse('pxeconfig'), params)
        self.assertEqual(
            compose_preseed_url(node),
            json.loads(response.content)["preseed_url"])

    def test_find_nodegroup_for_pxeconfig_request_uses_cluster_uuid(self):
        # find_nodegroup_for_pxeconfig_request returns the nodegroup
        # identified by the cluster_uuid parameter, if given.  It
        # completely ignores the other node or request details, as shown
        # here by passing a uuid for a different cluster.
        params = self.get_mac_params()
        nodegroup = factory.make_node_group()
        params['cluster_uuid'] = nodegroup.uuid
        request = RequestFactory().get(reverse('pxeconfig'), params)
        self.assertEqual(
            nodegroup,
            find_nodegroup_for_pxeconfig_request(request))

    def test_preseed_url_for_known_node_uses_nodegroup_maas_url(self):
        ng_url = 'http://%s' % factory.make_name('host')
        network = IPNetwork("10.1.1/24")
        ip = factory.getRandomIPInNetwork(network)
        self.patch(server_address, 'gethostbyname', Mock(return_value=ip))
        nodegroup = factory.make_node_group(maas_url=ng_url, network=network)
        params = self.get_mac_params()
        node = MACAddress.objects.get(mac_address=params['mac']).node
        node.nodegroup = nodegroup
        node.save()

        # Simulate that the request originates from ip by setting
        # 'REMOTE_ADDR'.
        response = self.client.get(
            reverse('pxeconfig'), params, REMOTE_ADDR=ip)
        self.assertThat(
            json.loads(response.content)["preseed_url"],
            StartsWith(ng_url))

    def test_get_boot_purpose_unknown_node(self):
        # A node that's not yet known to MAAS is assumed to be enlisting,
        # which uses a "commissioning" image.
        self.assertEqual("commissioning", api.get_boot_purpose(None))

    def test_get_boot_purpose_known_node(self):
        # The following table shows the expected boot "purpose" for each set
        # of node parameters.
        options = [
            ("poweroff", {"status": NODE_STATUS.DECLARED}),
            ("commissioning", {"status": NODE_STATUS.COMMISSIONING}),
            ("poweroff", {"status": NODE_STATUS.FAILED_TESTS}),
            ("poweroff", {"status": NODE_STATUS.MISSING}),
            ("poweroff", {"status": NODE_STATUS.READY}),
            ("poweroff", {"status": NODE_STATUS.RESERVED}),
            ("install", {"status": NODE_STATUS.ALLOCATED, "netboot": True}),
            ("xinstall", {"status": NODE_STATUS.ALLOCATED, "netboot": True}),
            ("local", {"status": NODE_STATUS.ALLOCATED, "netboot": False}),
            ("poweroff", {"status": NODE_STATUS.RETIRED}),
            ]
        node = factory.make_node()
        for purpose, parameters in options:
            if purpose == "xinstall":
                node.use_fastpath_installer()
            for name, value in parameters.items():
                setattr(node, name, value)
            self.assertEqual(purpose, api.get_boot_purpose(node))

    def test_pxeconfig_uses_boot_purpose(self):
        fake_boot_purpose = factory.make_name("purpose")
        self.patch(api, "get_boot_purpose", lambda node: fake_boot_purpose)
        response = self.client.get(reverse('pxeconfig'),
                                   self.get_default_params())
        self.assertEqual(
            fake_boot_purpose,
            json.loads(response.content)["purpose"])

    def test_pxeconfig_returns_fs_host_as_cluster_controller(self):
        # The kernel parameter `fs_host` points to the cluster controller
        # address, which is passed over within the `local` parameter.
        params = self.get_default_params()
        kernel_params = KernelParameters(**self.get_pxeconfig(params))
        self.assertEqual(params["local"], kernel_params.fs_host)

    def test_pxeconfig_returns_extra_kernel_options(self):
        node = factory.make_node()
        extra_kernel_opts = factory.getRandomString()
        Config.objects.set_config('kernel_opts', extra_kernel_opts)
        mac = factory.make_mac_address(node=node)
        params = self.get_default_params()
        params['mac'] = mac.mac_address
        pxe_config = self.get_pxeconfig(params)
        self.assertEqual(extra_kernel_opts, pxe_config['extra_opts'])

    def test_pxeconfig_returns_None_for_extra_kernel_opts(self):
        mac = factory.make_mac_address()
        params = self.get_default_params()
        params['mac'] = mac.mac_address
        pxe_config = self.get_pxeconfig(params)
        self.assertEqual(None, pxe_config['extra_opts'])
