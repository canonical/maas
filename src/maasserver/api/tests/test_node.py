# Copyright 2013-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the Node API."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
)

str = None

__metaclass__ = type
__all__ = []

from base64 import b64encode
from cStringIO import StringIO
import httplib
import json
import sys

import bson
from django.core.urlresolvers import reverse
from django.db import transaction
from maasserver import forms
from maasserver.enum import (
    INTERFACE_TYPE,
    IPADDRESS_TYPE,
    NODE_BOOT,
    NODE_STATUS,
    NODE_STATUS_CHOICES,
    NODE_STATUS_CHOICES_DICT,
    POWER_STATE,
)
from maasserver.fields import (
    MAC,
    MAC_ERROR_MSG,
)
from maasserver.models import (
    Config,
    interface as interface_module,
    Node,
    node as node_module,
    NodeGroup,
    StaticIPAddress,
)
from maasserver.models.node import RELEASABLE_STATUSES
from maasserver.storage_layouts import (
    MIN_BOOT_PARTITION_SIZE,
    StorageLayoutError,
)
from maasserver.testing.api import (
    APITestCase,
    APITransactionTestCase,
)
from maasserver.testing.architecture import make_usable_architecture
from maasserver.testing.factory import factory
from maasserver.testing.oauthclient import OAuthAuthenticatedClient
from maasserver.testing.orm import (
    reload_object,
    reload_objects,
)
from maasserver.testing.osystems import make_usable_osystem
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import post_commit
from maastesting.matchers import (
    Equals,
    MockCalledOnceWith,
    MockNotCalled,
)
from metadataserver.models import (
    commissioningscript,
    NodeKey,
    NodeUserData,
)
from metadataserver.nodeinituser import get_node_init_user
from mock import ANY
from netaddr import IPAddress
from provisioningserver.rpc.exceptions import PowerActionAlreadyInProgress
from provisioningserver.utils.enum import map_enum
from testtools.matchers import (
    HasLength,
    Not,
)


class NodeAnonAPITest(MAASServerTestCase):

    def setUp(self):
        super(NodeAnonAPITest, self).setUp()
        self.patch(node_module, 'power_on_node')
        self.patch(node_module, 'power_off_node')

    def test_anon_nodes_GET(self):
        # Anonymous requests to the API without a specified operation
        # get a "Bad Request" response.
        response = self.client.get(reverse('nodes_handler'))

        self.assertEqual(httplib.BAD_REQUEST, response.status_code)

    def test_anon_api_doc(self):
        # The documentation is accessible to anon users.
        self.patch(sys, "stderr", StringIO())
        response = self.client.get(reverse('api-doc'))
        self.assertEqual(httplib.OK, response.status_code)
        # No error or warning are emitted by docutils.
        self.assertEqual("", sys.stderr.getvalue())

    def test_node_init_user_cannot_access(self):
        token = NodeKey.objects.get_token_for_node(factory.make_Node())
        client = OAuthAuthenticatedClient(get_node_init_user(), token)
        response = client.get(reverse('nodes_handler'), {'op': 'list'})
        self.assertEqual(httplib.FORBIDDEN, response.status_code)


class NodesAPILoggedInTest(MAASServerTestCase):

    def setUp(self):
        super(NodesAPILoggedInTest, self).setUp()
        self.patch(node_module, 'wait_for_power_command')

    def test_nodes_GET_logged_in(self):
        # A (Django) logged-in user can access the API.
        self.client_log_in()
        node = factory.make_Node()
        response = self.client.get(reverse('nodes_handler'), {'op': 'list'})
        parsed_result = json.loads(response.content)

        self.assertEqual(httplib.OK, response.status_code)
        self.assertEqual(
            [node.system_id],
            [parsed_node.get('system_id') for parsed_node in parsed_result])


class TestNodeAPI(APITestCase):
    """Tests for /api/1.0/nodes/<node>/."""

    def setUp(self):
        super(TestNodeAPI, self).setUp()
        self.patch(node_module, 'power_on_node')
        self.patch(node_module, 'power_off_node')

    def test_handler_path(self):
        self.assertEqual(
            '/api/1.0/nodes/node-name/',
            reverse('node_handler', args=['node-name']))

    @staticmethod
    def get_node_uri(node):
        """Get the API URI for `node`."""
        return reverse('node_handler', args=[node.system_id])

    def test_GET_returns_node(self):
        # The api allows for fetching a single Node (using system_id).
        node = factory.make_Node()
        response = self.client.get(self.get_node_uri(node))

        self.assertEqual(httplib.OK, response.status_code)
        parsed_result = json.loads(response.content)
        nodegroup = NodeGroup.objects.ensure_master()
        domain_name = nodegroup.name
        self.assertEqual(
            "%s.%s" % (node.hostname, domain_name),
            parsed_result['hostname'])
        self.assertEqual(node.system_id, parsed_result['system_id'])

    def test_GET_returns_associated_tag(self):
        node = factory.make_Node()
        tag = factory.make_Tag()
        node.tags.add(tag)
        response = self.client.get(self.get_node_uri(node))

        self.assertEqual(httplib.OK, response.status_code)
        parsed_result = json.loads(response.content)
        self.assertEqual([tag.name], parsed_result['tag_names'])

    def test_GET_returns_associated_ip_addresses(self):
        node = factory.make_Node(disable_ipv4=False)
        nic = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        subnet = factory.make_Subnet()
        ip = factory.pick_ip_in_network(subnet.get_ipnetwork())
        lease = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.DISCOVERED, ip=ip,
            interface=nic, subnet=subnet)
        response = self.client.get(self.get_node_uri(node))

        self.assertEqual(
            httplib.OK, response.status_code, response.content)
        parsed_result = json.loads(response.content)
        self.assertEqual([lease.ip], parsed_result['ip_addresses'])

    def test_GET_returns_associated_routers(self):
        macs = [MAC('aa:bb:cc:dd:ee:ff'), MAC('00:11:22:33:44:55')]
        node = factory.make_Node(routers=macs)
        response = self.client.get(self.get_node_uri(node))

        self.assertEqual(
            httplib.OK, response.status_code, response.content)
        parsed_result = json.loads(response.content)
        self.assertItemsEqual(
            [mac.get_raw() for mac in macs], parsed_result['routers'])

    def test_GET_returns_zone(self):
        node = factory.make_Node()
        response = self.client.get(self.get_node_uri(node))
        self.assertEqual(httplib.OK, response.status_code)
        parsed_result = json.loads(response.content)
        self.assertEqual(
            [node.zone.name, node.zone.description],
            [
                parsed_result['zone']['name'],
                parsed_result['zone']['description']])

    def test_GET_returns_boot_type(self):
        node = factory.make_Node()
        response = self.client.get(self.get_node_uri(node))
        self.assertEqual(httplib.OK, response.status_code)
        parsed_result = json.loads(response.content)
        self.assertEqual(
            node.boot_type, parsed_result['boot_type'])

    def test_GET_returns_pxe_mac(self):
        node = factory.make_Node(interface=True)
        node.boot_interface = node.interface_set.first()
        node.save()
        response = self.client.get(self.get_node_uri(node))
        self.assertEqual(httplib.OK, response.status_code)
        parsed_result = json.loads(response.content)
        expected_result = {
            'mac_address': node.boot_interface.mac_address.get_raw(),
        }
        self.assertEqual(
            expected_result, parsed_result['pxe_mac'])

    def test_GET_refuses_to_access_nonexistent_node(self):
        # When fetching a Node, the api returns a 'Not Found' (404) error
        # if no node is found.
        url = reverse('node_handler', args=['invalid-uuid'])

        response = self.client.get(url)

        self.assertEqual(httplib.NOT_FOUND, response.status_code)
        self.assertEqual("Not Found", response.content)

    def test_GET_returns_404_if_node_name_contains_invalid_characters(self):
        # When the requested name contains characters that are invalid for
        # a hostname, the result of the request is a 404 response.
        url = reverse('node_handler', args=['invalid-uuid-#...'])

        response = self.client.get(url)

        self.assertEqual(httplib.NOT_FOUND, response.status_code)
        self.assertEqual("Not Found", response.content)

    def test_GET_returns_owner_name_when_allocated_to_self(self):
        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=self.logged_in_user)
        response = self.client.get(self.get_node_uri(node))
        self.assertEqual(httplib.OK, response.status_code)
        parsed_result = json.loads(response.content)
        self.assertEqual(node.owner.username, parsed_result["owner"])

    def test_GET_returns_owner_name_when_allocated_to_other_user(self):
        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=factory.make_User())
        response = self.client.get(self.get_node_uri(node))
        self.assertEqual(httplib.OK, response.status_code)
        parsed_result = json.loads(response.content)
        self.assertEqual(node.owner.username, parsed_result["owner"])

    def test_GET_returns_empty_owner_when_not_allocated(self):
        node = factory.make_Node(status=NODE_STATUS.READY)
        response = self.client.get(self.get_node_uri(node))
        self.assertEqual(httplib.OK, response.status_code)
        parsed_result = json.loads(response.content)
        self.assertEqual(None, parsed_result["owner"])

    def test_GET_returns_physical_block_devices(self):
        node = factory.make_Node()
        devices = [
            factory.make_PhysicalBlockDevice(node=node)
            for _ in range(3)
        ]
        response = self.client.get(self.get_node_uri(node))
        self.assertEqual(httplib.OK, response.status_code)
        parsed_result = json.loads(response.content)
        parsed_devices = [
            device['name']
            for device in parsed_result['physicalblockdevice_set']
        ]
        self.assertItemsEqual(
            [device.name for device in devices], parsed_devices)

    def test_GET_rejects_device(self):
        node = factory.make_Node(
            installable=False, owner=self.logged_in_user)
        response = self.client.get(self.get_node_uri(node))
        self.assertEqual(
            httplib.NOT_FOUND, response.status_code, response.content)

    def test_GET_returns_min_hwe_kernel_and_hwe_kernel(self):
        node = factory.make_Node()
        response = self.client.get(self.get_node_uri(node))

        self.assertEqual(httplib.OK, response.status_code)
        parsed_result = json.loads(response.content)
        self.assertEqual(None, parsed_result['min_hwe_kernel'])
        self.assertEqual(None, parsed_result['hwe_kernel'])

    def test_GET_returns_min_hwe_kernel(self):
        node = factory.make_Node(min_hwe_kernel="hwe-v")
        response = self.client.get(self.get_node_uri(node))

        self.assertEqual(httplib.OK, response.status_code)
        parsed_result = json.loads(response.content)
        self.assertEqual("hwe-v", parsed_result['min_hwe_kernel'])

    def test_GET_returns_substatus_message_with_most_recent_event(self):
        """Makes sure the most recent event from this node is shown in the
        substatus_message attribute."""
        # The first event won't be returned.
        event = factory.make_Event(description="Uninteresting event")
        node = event.node
        # The second (and last) event will be returned.
        message = "Interesting event"
        factory.make_Event(description=message, node=node)
        response = self.client.get(self.get_node_uri(node))
        parsed_result = json.loads(response.content)
        self.assertEqual(message, parsed_result['substatus_message'])

    def test_GET_returns_substatus_name(self):
        """GET should display the node status as a user-friendly string."""
        for status in NODE_STATUS_CHOICES_DICT:
            node = factory.make_Node(status=status)
            response = self.client.get(self.get_node_uri(node))
            parsed_result = json.loads(response.content)
            self.assertEqual(NODE_STATUS_CHOICES_DICT[status],
                             parsed_result['substatus_name'])

    def test_POST_stop_checks_permission(self):
        node = factory.make_Node()
        node_stop = self.patch(node, 'stop')
        response = self.client.post(self.get_node_uri(node), {'op': 'stop'})
        self.assertEqual(httplib.FORBIDDEN, response.status_code)
        self.assertThat(node_stop, MockNotCalled())

    def test_POST_stop_rejects_device(self):
        node = factory.make_Node(
            installable=False, owner=self.logged_in_user)
        response = self.client.post(self.get_node_uri(node), {'op': 'stop'})
        self.assertEqual(
            httplib.NOT_FOUND, response.status_code, response.content)

    def test_POST_stop_returns_nothing_if_node_was_not_stopped(self):
        # The node may not be stopped because, for example, its power type
        # does not support it. In this case the node is not returned to the
        # caller.
        node = factory.make_Node(owner=self.logged_in_user)
        node_stop = self.patch(node_module.Node, 'stop')
        node_stop.return_value = False
        response = self.client.post(self.get_node_uri(node), {'op': 'stop'})
        self.assertEqual(httplib.OK, response.status_code)
        self.assertIsNone(json.loads(response.content))
        self.assertThat(node_stop, MockCalledOnceWith(
            ANY, stop_mode=ANY, comment=None))

    def test_POST_stop_returns_node(self):
        node = factory.make_Node(owner=self.logged_in_user)
        self.patch(node_module.Node, 'stop').return_value = True
        response = self.client.post(self.get_node_uri(node), {'op': 'stop'})
        self.assertEqual(httplib.OK, response.status_code)
        self.assertEqual(
            node.system_id, json.loads(response.content)['system_id'])

    def test_POST_stop_may_be_repeated(self):
        node = factory.make_Node(
            owner=self.logged_in_user, interface=True,
            power_type='ether_wake')
        self.patch(node, 'stop')
        self.client.post(self.get_node_uri(node), {'op': 'stop'})
        response = self.client.post(self.get_node_uri(node), {'op': 'stop'})
        self.assertEqual(httplib.OK, response.status_code)

    def test_POST_stop_stops_nodes(self):
        node = factory.make_Node(owner=self.logged_in_user)
        node_stop = self.patch(node_module.Node, 'stop')
        stop_mode = factory.make_name('stop_mode')
        comment = factory.make_name('comment')
        self.client.post(
            self.get_node_uri(node),
            {'op': 'stop', 'stop_mode': stop_mode, 'comment': comment})
        self.assertThat(
            node_stop,
            MockCalledOnceWith(
                self.logged_in_user, stop_mode=stop_mode, comment=comment))

    def test_POST_stop_handles_missing_comment(self):
        node = factory.make_Node(owner=self.logged_in_user)
        node_stop = self.patch(node_module.Node, 'stop')
        stop_mode = factory.make_name('stop_mode')
        self.client.post(
            self.get_node_uri(node), {'op': 'stop', 'stop_mode': stop_mode})
        self.assertThat(
            node_stop,
            MockCalledOnceWith(
                self.logged_in_user, stop_mode=stop_mode, comment=None))

    def test_POST_stop_returns_503_when_power_op_already_in_progress(self):
        node = factory.make_Node(owner=self.logged_in_user)
        exc_text = factory.make_name("exc_text")
        self.patch(
            node_module.Node,
            'stop').side_effect = PowerActionAlreadyInProgress(exc_text)
        response = self.client.post(self.get_node_uri(node), {'op': 'stop'})
        self.assertResponseCode(httplib.SERVICE_UNAVAILABLE, response)
        self.assertIn(exc_text, response.content)

    def test_POST_start_checks_permission(self):
        node = factory.make_Node(owner=factory.make_User())
        response = self.client.post(self.get_node_uri(node), {'op': 'start'})
        self.assertEqual(httplib.FORBIDDEN, response.status_code)

    def test_POST_start_checks_ownership(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        response = self.client.post(self.get_node_uri(node), {'op': 'start'})
        self.assertEqual(httplib.CONFLICT, response.status_code)
        self.assertEqual(
            "Can't start node: it hasn't been allocated.", response.content)

    def test_POST_start_returns_node(self):
        node = factory.make_Node(
            owner=self.logged_in_user, interface=True,
            power_type='ether_wake',
            architecture=make_usable_architecture(self))
        osystem = make_usable_osystem(self)
        distro_series = osystem['default_release']
        response = self.client.post(
            self.get_node_uri(node),
            {
                'op': 'start',
                'distro_series': distro_series,
            })
        self.assertEqual(httplib.OK, response.status_code)
        self.assertEqual(
            node.system_id, json.loads(response.content)['system_id'])

    def test_POST_start_rejects_device(self):
        node = factory.make_Node(
            installable=False, owner=self.logged_in_user)
        response = self.client.post(self.get_node_uri(node), {'op': 'start'})
        self.assertEqual(
            httplib.NOT_FOUND, response.status_code, response.content)

    def test_POST_start_sets_osystem_and_distro_series(self):
        node = factory.make_Node(
            owner=self.logged_in_user, interface=True,
            power_type='ether_wake',
            architecture=make_usable_architecture(self))
        osystem = make_usable_osystem(self)
        distro_series = osystem['default_release']
        response = self.client.post(
            self.get_node_uri(node), {
                'op': 'start',
                'distro_series': distro_series
            })
        self.assertEqual(
            (httplib.OK, node.system_id),
            (response.status_code, json.loads(response.content)['system_id']))
        self.assertEqual(
            osystem['name'], reload_object(node).osystem)
        self.assertEqual(
            distro_series, reload_object(node).distro_series)

    def test_POST_start_validates_distro_series(self):
        node = factory.make_Node(
            owner=self.logged_in_user, interface=True,
            power_type='ether_wake',
            architecture=make_usable_architecture(self))
        invalid_distro_series = factory.make_string()
        response = self.client.post(
            self.get_node_uri(node),
            {'op': 'start', 'distro_series': invalid_distro_series})
        self.assertEqual(
            (
                httplib.BAD_REQUEST,
                {'distro_series': [
                    "'%s' is not a valid distro_series.  "
                    "It should be one of: ''." %
                    invalid_distro_series]}
            ),
            (response.status_code, json.loads(response.content)))

    def test_POST_start_sets_license_key(self):
        node = factory.make_Node(
            owner=self.logged_in_user, interface=True,
            power_type='ether_wake',
            architecture=make_usable_architecture(self))
        osystem = make_usable_osystem(self)
        distro_series = osystem['default_release']
        license_key = factory.make_string()
        self.patch(forms, 'validate_license_key_for').return_value = True
        response = self.client.post(
            self.get_node_uri(node), {
                'op': 'start',
                'osystem': osystem['name'],
                'distro_series': distro_series,
                'license_key': license_key,
            })
        self.assertEqual(
            (httplib.OK, node.system_id),
            (response.status_code, json.loads(response.content)['system_id']))
        self.assertEqual(
            license_key, reload_object(node).license_key)

    def test_POST_start_validates_license_key(self):
        node = factory.make_Node(
            owner=self.logged_in_user, interface=True,
            power_type='ether_wake',
            architecture=make_usable_architecture(self))
        osystem = make_usable_osystem(self)
        distro_series = osystem['default_release']
        license_key = factory.make_string()
        self.patch(forms, 'validate_license_key_for').return_value = False
        response = self.client.post(
            self.get_node_uri(node), {
                'op': 'start',
                'osystem': osystem['name'],
                'distro_series': distro_series,
                'license_key': license_key,
            })
        self.assertEqual(
            (
                httplib.BAD_REQUEST,
                {'license_key': [
                    "Invalid license key."]}
            ),
            (response.status_code, json.loads(response.content)))

    def test_POST_start_sets_default_distro_series(self):
        node = factory.make_Node(
            owner=self.logged_in_user, interface=True,
            power_type='ether_wake',
            architecture=make_usable_architecture(self))
        osystem = Config.objects.get_config('default_osystem')
        distro_series = Config.objects.get_config('default_distro_series')
        make_usable_osystem(
            self, osystem_name=osystem, releases=[distro_series])
        response = self.client.post(self.get_node_uri(node), {'op': 'start'})
        response_info = json.loads(response.content)
        self.assertEqual(httplib.OK, response.status_code)
        self.assertEqual(response_info['osystem'], osystem)
        self.assertEqual(response_info['distro_series'], distro_series)

    def test_POST_start_fails_with_no_boot_source(self):
        node = factory.make_Node(
            owner=self.logged_in_user, interface=True,
            power_type='ether_wake',
            architecture=make_usable_architecture(self))
        response = self.client.post(self.get_node_uri(node), {'op': 'start'})
        self.assertEqual(
            (
                httplib.BAD_REQUEST,
                {'distro_series': [
                    "'%s' is not a valid distro_series.  "
                    "It should be one of: ''." %
                    Config.objects.get_config('default_distro_series')]}
            ),
            (response.status_code, json.loads(response.content)))

    def test_POST_start_validates_hwe_kernel_with_default_distro_series(self):
        architecture = make_usable_architecture(self, subarch_name="generic")
        node = factory.make_Node(
            owner=self.logged_in_user, interface=True,
            power_type='ether_wake',
            architecture=architecture)
        osystem = Config.objects.get_config('default_osystem')
        distro_series = Config.objects.get_config('default_distro_series')
        make_usable_osystem(
            self, osystem_name=osystem, releases=[distro_series])
        bad_hwe_kernel = 'hwe-' + chr(ord(distro_series[0]) - 1)
        response = self.client.post(
            self.get_node_uri(node),
            {
                'op': 'start',
                'hwe_kernel': bad_hwe_kernel,
            })
        self.assertEqual(
            (
                httplib.BAD_REQUEST,
                {'hwe_kernel': [
                    "%s is not available for %s/%s on %s."
                    % (bad_hwe_kernel, osystem, distro_series, architecture)]}
            ),
            (response.status_code, json.loads(response.content)))

    def test_POST_start_may_be_repeated(self):
        node = factory.make_Node(
            owner=self.logged_in_user, interface=True,
            power_type='ether_wake',
            architecture=make_usable_architecture(self))
        osystem = make_usable_osystem(self)
        distro_series = osystem['default_release']
        request = {
            'op': 'start',
            'distro_series': distro_series,
            }
        self.client.post(self.get_node_uri(node), request)
        response = self.client.post(self.get_node_uri(node), request)
        self.assertEqual(httplib.OK, response.status_code)

    def test_POST_start_stores_user_data(self):
        node = factory.make_Node(
            owner=self.logged_in_user, interface=True,
            power_type='ether_wake',
            architecture=make_usable_architecture(self))
        osystem = make_usable_osystem(self)
        distro_series = osystem['default_release']
        user_data = (
            b'\xff\x00\xff\xfe\xff\xff\xfe' +
            factory.make_string().encode('ascii'))
        response = self.client.post(
            self.get_node_uri(node), {
                'op': 'start',
                'user_data': b64encode(user_data),
                'distro_series': distro_series,
            })
        self.assertEqual(httplib.OK, response.status_code)
        self.assertEqual(user_data, NodeUserData.objects.get_user_data(node))

    def test_POST_start_passes_comment(self):
        node = factory.make_Node(
            owner=self.logged_in_user, interface=True,
            power_type='ether_wake',
            architecture=make_usable_architecture(self))
        osystem = make_usable_osystem(self)
        distro_series = osystem['default_release']
        comment = factory.make_name('comment')
        node_start = self.patch(node_module.Node, 'start')
        node_start.return_value = False
        self.client.post(
            self.get_node_uri(node), {
                'op': 'start',
                'user_data': None,
                'distro_series': distro_series,
                'comment': comment,
            })
        self.assertThat(node_start, MockCalledOnceWith(
            self.logged_in_user, user_data=ANY, comment=comment))

    def test_POST_start_handles_missing_comment(self):
        node = factory.make_Node(
            owner=self.logged_in_user, interface=True,
            power_type='ether_wake',
            architecture=make_usable_architecture(self))
        osystem = make_usable_osystem(self)
        distro_series = osystem['default_release']
        node_start = self.patch(node_module.Node, 'start')
        node_start.return_value = False
        self.client.post(
            self.get_node_uri(node), {
                'op': 'start',
                'user_data': None,
                'distro_series': distro_series,
            })
        self.assertThat(node_start, MockCalledOnceWith(
            self.logged_in_user, user_data=ANY, comment=None))

    def test_POST_release_releases_owned_node(self):
        self.patch(node_module, 'power_off_node')
        self.patch(node_module.Node, 'start_transition_monitor')
        owned_statuses = [
            NODE_STATUS.RESERVED,
            NODE_STATUS.ALLOCATED,
        ]
        owned_nodes = [
            factory.make_Node(
                owner=self.logged_in_user, status=status, power_type='ipmi',
                power_state=POWER_STATE.ON)
            for status in owned_statuses]
        responses = [
            self.client.post(self.get_node_uri(node), {'op': 'release'})
            for node in owned_nodes]
        self.assertEqual(
            [httplib.OK] * len(owned_nodes),
            [response.status_code for response in responses])
        self.assertItemsEqual(
            [NODE_STATUS.RELEASING] * len(owned_nodes),
            [node.status for node in reload_objects(Node, owned_nodes)])

    def test_POST_release_releases_failed_node(self):
        self.patch(node_module, 'power_off_node')
        self.patch(node_module.Node, 'start_transition_monitor')
        owned_node = factory.make_Node(
            owner=self.logged_in_user,
            status=NODE_STATUS.FAILED_DEPLOYMENT,
            power_type='ipmi', power_state=POWER_STATE.ON)
        response = self.client.post(
            self.get_node_uri(owned_node), {'op': 'release'})
        self.assertEqual(
            httplib.OK, response.status_code, response.content)
        owned_node = Node.objects.get(id=owned_node.id)
        self.expectThat(owned_node.status, Equals(NODE_STATUS.RELEASING))
        self.expectThat(owned_node.owner, Equals(self.logged_in_user))

    def test_POST_release_does_nothing_for_unowned_node(self):
        node = factory.make_Node(
            status=NODE_STATUS.READY, owner=self.logged_in_user)
        response = self.client.post(
            self.get_node_uri(node), {'op': 'release'})
        self.assertEqual(httplib.OK, response.status_code)
        self.assertEqual(NODE_STATUS.READY, reload_object(node).status)

    def test_POST_release_rejects_device(self):
        node = factory.make_Node(
            installable=False, owner=self.logged_in_user)
        response = self.client.post(self.get_node_uri(node), {'op': 'release'})
        self.assertEqual(
            httplib.NOT_FOUND, response.status_code, response.content)

    def test_POST_release_forbidden_if_user_cannot_edit_node(self):
        node = factory.make_Node(status=NODE_STATUS.READY)
        response = self.client.post(
            self.get_node_uri(node), {'op': 'release'})
        self.assertEqual(httplib.FORBIDDEN, response.status_code)

    def test_POST_release_fails_for_other_node_states(self):
        releasable_statuses = (
            RELEASABLE_STATUSES + [
                NODE_STATUS.RELEASING,
                NODE_STATUS.READY
            ])
        unreleasable_statuses = [
            status
            for status in map_enum(NODE_STATUS).values()
            if status not in releasable_statuses
        ]
        nodes = [
            factory.make_Node(status=status, owner=self.logged_in_user)
            for status in unreleasable_statuses]
        responses = [
            self.client.post(self.get_node_uri(node), {'op': 'release'})
            for node in nodes]
        self.assertEqual(
            [httplib.CONFLICT] * len(unreleasable_statuses),
            [response.status_code for response in responses])
        self.assertItemsEqual(
            unreleasable_statuses,
            [node.status for node in reload_objects(Node, nodes)])

    def test_POST_release_in_wrong_state_reports_current_state(self):
        node = factory.make_Node(
            status=NODE_STATUS.RETIRED, owner=self.logged_in_user)
        response = self.client.post(
            self.get_node_uri(node), {'op': 'release'})
        self.assertEqual(
            (
                httplib.CONFLICT,
                "Node cannot be released in its current state ('Retired').",
            ),
            (response.status_code, response.content))

    def test_POST_release_rejects_request_from_unauthorized_user(self):
        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=factory.make_User())
        response = self.client.post(
            self.get_node_uri(node), {'op': 'release'})
        self.assertEqual(httplib.FORBIDDEN, response.status_code)
        self.assertEqual(NODE_STATUS.ALLOCATED, reload_object(node).status)

    def test_POST_release_allows_admin_to_release_anyones_node(self):
        self.patch(node_module, 'power_off_node')
        self.patch(node_module.Node, 'start_transition_monitor')
        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=factory.make_User(),
            power_type='ipmi', power_state=POWER_STATE.ON)
        self.become_admin()
        response = self.client.post(
            self.get_node_uri(node), {'op': 'release'})
        self.assertEqual(httplib.OK, response.status_code, response.content)
        self.assertEqual(NODE_STATUS.RELEASING, reload_object(node).status)

    def test_POST_release_combines_with_acquire(self):
        self.patch(node_module, 'power_off_node')
        self.patch(node_module.Node, 'start_transition_monitor')
        node = factory.make_Node(
            status=NODE_STATUS.READY, power_type='ipmi',
            power_state=POWER_STATE.ON, with_boot_disk=True)
        response = self.client.post(
            reverse('nodes_handler'), {'op': 'acquire'})
        self.assertEqual(NODE_STATUS.ALLOCATED, reload_object(node).status)
        node_uri = json.loads(response.content)['resource_uri']
        response = self.client.post(node_uri, {'op': 'release'})
        self.assertEqual(httplib.OK, response.status_code, response.content)
        self.assertEqual(NODE_STATUS.RELEASING, reload_object(node).status)

    def test_POST_acquire_passes_comment(self):
        factory.make_Node(
            status=NODE_STATUS.READY, power_type='ipmi',
            power_state=POWER_STATE.ON, with_boot_disk=True)
        node_method = self.patch(node_module.Node, 'acquire')
        comment = factory.make_name('comment')
        self.client.post(
            reverse('nodes_handler'),
            {'op': 'acquire', 'comment': comment})
        self.assertThat(
            node_method, MockCalledOnceWith(
                ANY, ANY, agent_name=ANY, comment=comment))

    def test_POST_acquire_handles_missing_comment(self):
        factory.make_Node(
            status=NODE_STATUS.READY, power_type='ipmi',
            power_state=POWER_STATE.ON, with_boot_disk=True)
        node_method = self.patch(node_module.Node, 'acquire')
        self.client.post(
            reverse('nodes_handler'), {'op': 'acquire'})
        self.assertThat(
            node_method, MockCalledOnceWith(
                ANY, ANY, agent_name=ANY, comment=None))

    def test_POST_release_frees_hwe_kernel(self):
        self.patch(node_module, 'power_off_node')
        self.patch(node_module.Node, 'start_transition_monitor')
        node = factory.make_Node(
            owner=self.logged_in_user, status=NODE_STATUS.ALLOCATED,
            power_type='ipmi', power_state=POWER_STATE.ON,
            hwe_kernel='hwe-v')
        self.assertEqual('hwe-v', reload_object(node).hwe_kernel)
        response = self.client.post(self.get_node_uri(node), {'op': 'release'})
        self.assertEqual(httplib.OK, response.status_code, response.content)
        self.assertEqual(NODE_STATUS.RELEASING, reload_object(node).status)
        self.assertEqual(None, reload_object(node).hwe_kernel)

    def test_POST_release_passes_comment(self):
        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=factory.make_User(),
            power_type='ipmi', power_state=POWER_STATE.OFF)
        self.become_admin()
        comment = factory.make_name('comment')
        node_release = self.patch(node_module.Node, 'release_or_erase')
        self.client.post(
            self.get_node_uri(node),
            {'op': 'release', 'comment': comment})
        self.assertThat(
            node_release,
            MockCalledOnceWith(self.logged_in_user, comment))

    def test_POST_release_handles_missing_comment(self):
        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=factory.make_User(),
            power_type='ipmi', power_state=POWER_STATE.OFF)
        self.become_admin()
        node_release = self.patch(node_module.Node, 'release_or_erase')
        self.client.post(
            self.get_node_uri(node), {'op': 'release'})
        self.assertThat(
            node_release,
            MockCalledOnceWith(self.logged_in_user, None))

    def test_POST_commission_commissions_node(self):
        node = factory.make_Node(
            status=NODE_STATUS.READY, owner=factory.make_User(),
            power_state=POWER_STATE.OFF)
        self.become_admin()
        response = self.client.post(
            self.get_node_uri(node), {'op': 'commission'})
        self.assertEqual(httplib.OK, response.status_code)
        self.assertEqual(NODE_STATUS.COMMISSIONING, reload_object(node).status)

    def test_POST_commission_commissions_node_with_options(self):
        node = factory.make_Node(
            status=NODE_STATUS.READY, owner=factory.make_User(),
            power_state=POWER_STATE.OFF)
        self.become_admin()
        response = self.client.post(self.get_node_uri(node), {
            'op': 'commission',
            'enable_ssh': "true",
            'block_poweroff': True,
            'skip_networking': 1,
            })
        self.assertEqual(httplib.OK, response.status_code)
        node = reload_object(node)
        self.assertTrue(node.enable_ssh)
        self.assertTrue(node.block_poweroff)
        self.assertTrue(node.skip_networking)

    def test_PUT_updates_node(self):
        self.become_admin()
        # The api allows the updating of a Node.
        node = factory.make_Node(
            hostname='diane', owner=self.logged_in_user,
            architecture=make_usable_architecture(self))
        response = self.client.put(
            self.get_node_uri(node), {'hostname': 'francis'})
        parsed_result = json.loads(response.content)

        self.assertEqual(httplib.OK, response.status_code)
        nodegroup = NodeGroup.objects.ensure_master()
        domain_name = nodegroup.name
        self.assertEqual(
            'francis.%s' % domain_name, parsed_result['hostname'])
        self.assertEqual(0, Node.objects.filter(hostname='diane').count())
        self.assertEqual(1, Node.objects.filter(hostname='francis').count())

    def test_PUT_omitted_hostname(self):
        self.become_admin()
        hostname = factory.make_name('hostname')
        arch = make_usable_architecture(self)
        node = factory.make_Node(
            hostname=hostname, owner=self.logged_in_user, architecture=arch)
        response = self.client.put(
            self.get_node_uri(node),
            {'architecture': arch})
        self.assertEqual(httplib.OK, response.status_code, response.content)
        self.assertTrue(Node.objects.filter(hostname=hostname).exists())

    def test_PUT_rejects_device(self):
        self.become_admin()
        node = factory.make_Node(
            installable=False, owner=self.logged_in_user)
        response = self.client.put(self.get_node_uri(node))
        self.assertEqual(
            httplib.NOT_FOUND, response.status_code, response.content)

    def test_PUT_ignores_unknown_fields(self):
        self.become_admin()
        node = factory.make_Node(
            owner=self.logged_in_user,
            architecture=make_usable_architecture(self))
        field = factory.make_string()
        response = self.client.put(
            self.get_node_uri(node),
            {field: factory.make_string()}
        )

        self.assertEqual(httplib.OK, response.status_code)

    def test_PUT_admin_can_change_power_type(self):
        self.become_admin()
        original_power_type = factory.pick_power_type()
        new_power_type = factory.pick_power_type(but_not=original_power_type)
        node = factory.make_Node(
            owner=self.logged_in_user,
            power_type=original_power_type,
            architecture=make_usable_architecture(self))
        response = self.client.put(
            self.get_node_uri(node), {'power_type': new_power_type})

        self.assertEqual(httplib.OK, response.status_code)
        self.assertEqual(
            new_power_type, reload_object(node).power_type)

    def test_PUT_non_admin_cannot_change_power_type(self):
        original_power_type = factory.pick_power_type()
        new_power_type = factory.pick_power_type(but_not=original_power_type)
        node = factory.make_Node(
            owner=self.logged_in_user, power_type=original_power_type)
        response = self.client.put(
            self.get_node_uri(node), {'power_type': new_power_type})

        self.assertEqual(httplib.FORBIDDEN, response.status_code)
        self.assertEqual(
            original_power_type, reload_object(node).power_type)

    def test_resource_uri_points_back_at_node(self):
        self.become_admin()
        # When a Node is returned by the API, the field 'resource_uri'
        # provides the URI for this Node.
        node = factory.make_Node(
            hostname='diane', owner=self.logged_in_user,
            architecture=make_usable_architecture(self))
        response = self.client.put(
            self.get_node_uri(node), {'hostname': 'francis'})
        parsed_result = json.loads(response.content)

        self.assertEqual(httplib.OK, response.status_code)
        self.assertEqual(
            reverse('node_handler', args=[parsed_result['system_id']]),
            parsed_result['resource_uri'])

    def test_PUT_rejects_invalid_data(self):
        # If the data provided to update a node is invalid, a 'Bad request'
        # response is returned.
        self.become_admin()
        node = factory.make_Node(
            hostname='diane', owner=self.logged_in_user,
            architecture=make_usable_architecture(self))
        response = self.client.put(
            self.get_node_uri(node), {'hostname': '.'})
        parsed_result = json.loads(response.content)

        self.assertEqual(httplib.BAD_REQUEST, response.status_code)
        self.assertEqual(
            {'hostname': ["DNS name contains an empty label."]},
            parsed_result)

    def test_PUT_refuses_to_update_nonexistent_node(self):
        # When updating a Node, the api returns a 'Not Found' (404) error
        # if no node is found.
        self.become_admin()
        url = reverse('node_handler', args=['invalid-uuid'])
        response = self.client.put(url)

        self.assertEqual(httplib.NOT_FOUND, response.status_code)

    def test_PUT_updates_power_parameters_field(self):
        # The api allows the updating of a Node's power_parameters field.
        self.become_admin()
        node = factory.make_Node(
            owner=self.logged_in_user,
            power_type='ether_wake',
            architecture=make_usable_architecture(self))
        # Create a power_parameter valid for the selected power_type.
        new_power_address = factory.make_mac_address()
        response = self.client.put(
            self.get_node_uri(node),
            {'power_parameters_mac_address': new_power_address})

        self.assertEqual(httplib.OK, response.status_code)
        self.assertEqual(
            {'mac_address': new_power_address},
            reload_object(node).power_parameters)

    def test_PUT_updates_cpu_memory(self):
        self.become_admin()
        node = factory.make_Node(
            owner=self.logged_in_user,
            power_type=factory.pick_power_type(),
            architecture=make_usable_architecture(self))
        response = self.client.put(
            self.get_node_uri(node),
            {'cpu_count': 1, 'memory': 1024})
        self.assertEqual(httplib.OK, response.status_code)
        node = reload_object(node)
        self.assertEqual(1, node.cpu_count)
        self.assertEqual(1024, node.memory)

    def test_PUT_updates_power_parameters_accepts_only_mac_for_wol(self):
        self.become_admin()
        node = factory.make_Node(
            owner=self.logged_in_user,
            power_type='ether_wake',
            architecture=make_usable_architecture(self))
        # Create an invalid power_parameter for WoL (not a valid
        # MAC address).
        new_power_address = factory.make_string()
        response = self.client.put(
            self.get_node_uri(node),
            {'power_parameters_mac_address': new_power_address})
        error_msg = MAC_ERROR_MSG % {'value': new_power_address}
        self.assertEqual(
            (
                httplib.BAD_REQUEST,
                {'power_parameters': ["MAC Address: %s" % error_msg]},
            ),
            (response.status_code, json.loads(response.content)))

    def test_PUT_updates_power_parameters_rejects_unknown_param(self):
        self.become_admin()
        power_parameters = factory.make_string()
        node = factory.make_Node(
            owner=self.logged_in_user,
            power_type='ether_wake',
            power_parameters=power_parameters,
            architecture=make_usable_architecture(self))
        response = self.client.put(
            self.get_node_uri(node),
            {'power_parameters_unknown_param': factory.make_string()})

        self.assertEqual(
            (
                httplib.BAD_REQUEST,
                {'power_parameters': ["Unknown parameter(s): unknown_param."]}
            ),
            (response.status_code, json.loads(response.content)))
        self.assertEqual(
            power_parameters, reload_object(node).power_parameters)

    def test_PUT_updates_power_type_default_resets_params(self):
        # If one sets power_type to empty, power_parameter gets
        # reset by default (if skip_check is not set).
        self.become_admin()
        power_parameters = factory.make_string()
        node = factory.make_Node(
            owner=self.logged_in_user,
            power_type='ether_wake',
            power_parameters=power_parameters,
            architecture=make_usable_architecture(self))
        response = self.client.put(
            self.get_node_uri(node),
            {'power_type': ''})

        node = reload_object(node)
        self.assertEqual(
            (httplib.OK, node.power_type, node.power_parameters),
            (response.status_code, '', ''))

    def test_PUT_updates_power_type_empty_rejects_params(self):
        # If one sets power_type to empty, one cannot set power_parameters.
        self.become_admin()
        power_parameters = factory.make_string()
        node = factory.make_Node(
            owner=self.logged_in_user,
            power_type='ether_wake',
            power_parameters=power_parameters,
            architecture=make_usable_architecture(self))
        new_param = factory.make_string()
        response = self.client.put(
            self.get_node_uri(node),
            {
                'power_type': '',
                'power_parameters_address': new_param,
            })

        node = reload_object(node)
        self.assertEqual(
            (
                httplib.BAD_REQUEST,
                {'power_parameters': ["Unknown parameter(s): address."]}
            ),
            (response.status_code, json.loads(response.content)))
        self.assertEqual(
            power_parameters, reload_object(node).power_parameters)

    def test_PUT_updates_power_type_empty_skip_check_to_force_params(self):
        # If one sets power_type to empty, it is possible to pass
        # power_parameter_skip_check='true' to force power_parameters.
        # XXX bigjools 2014-01-21 Why is this necessary?
        self.become_admin()
        power_parameters = factory.make_string()
        node = factory.make_Node(
            owner=self.logged_in_user,
            power_type='ether_wake',
            power_parameters=power_parameters,
            architecture=make_usable_architecture(self))
        new_param = factory.make_string()
        response = self.client.put(
            self.get_node_uri(node),
            {
                'power_type': '',
                'power_parameters_param': new_param,
                'power_parameters_skip_check': 'true',
            })

        node = reload_object(node)
        self.assertEqual(
            (httplib.OK, node.power_type, node.power_parameters),
            (response.status_code, '', {'param': new_param}))

    def test_PUT_updates_power_parameters_skip_ckeck(self):
        # With power_parameters_skip_check, arbitrary data
        # can be put in a Node's power_parameter field.
        self.become_admin()
        node = factory.make_Node(
            owner=self.logged_in_user,
            architecture=make_usable_architecture(self))
        new_param = factory.make_string()
        new_value = factory.make_string()
        response = self.client.put(
            self.get_node_uri(node),
            {
                'power_parameters_%s' % new_param: new_value,
                'power_parameters_skip_check': 'true',
            })

        self.assertEqual(httplib.OK, response.status_code)
        self.assertEqual(
            {new_param: new_value}, reload_object(node).power_parameters)

    def test_PUT_updates_power_parameters_empty_string(self):
        self.become_admin()
        node = factory.make_Node(
            owner=self.logged_in_user,
            power_type='ether_wake',
            power_parameters=factory.make_string(),
            architecture=make_usable_architecture(self))
        response = self.client.put(
            self.get_node_uri(node),
            {'power_parameters_mac_address': ''})

        self.assertEqual(httplib.OK, response.status_code)
        self.assertEqual(
            {'mac_address': ''},
            reload_object(node).power_parameters)

    def test_PUT_sets_zone(self):
        self.become_admin()
        new_zone = factory.make_Zone()
        node = factory.make_Node(architecture=make_usable_architecture(self))

        response = self.client.put(
            self.get_node_uri(node), {'zone': new_zone.name})

        self.assertEqual(httplib.OK, response.status_code)
        node = reload_object(node)
        self.assertEqual(new_zone, node.zone)

    def test_PUT_does_not_set_zone_if_not_present(self):
        self.become_admin()
        new_name = factory.make_name()
        node = factory.make_Node(architecture=make_usable_architecture(self))
        old_zone = node.zone

        response = self.client.put(
            self.get_node_uri(node), {'hostname': new_name})

        self.assertEqual(httplib.OK, response.status_code)
        node = reload_object(node)
        self.assertEqual((old_zone, new_name), (node.zone, node.hostname))

    def test_PUT_clears_zone(self):
        self.skip(
            "XXX: JeroenVermeulen 2013-12-11 bug=1259872: Clearing the "
            "zone field does not work...")

        self.become_admin()
        node = factory.make_Node(zone=factory.make_Zone())

        response = self.client.put(self.get_node_uri(node), {'zone': ''})

        self.assertEqual(httplib.OK, response.status_code)
        node = reload_object(node)
        self.assertEqual(None, node.zone)

    def test_PUT_without_zone_leaves_zone_unchanged(self):
        self.become_admin()
        zone = factory.make_Zone()
        node = factory.make_Node(
            zone=zone, architecture=make_usable_architecture(self))

        response = self.client.put(self.get_node_uri(node), {})

        self.assertEqual(httplib.OK, response.status_code)
        node = reload_object(node)
        self.assertEqual(zone, node.zone)

    def test_PUT_requires_admin(self):
        node = factory.make_Node(
            owner=self.logged_in_user,
            architecture=make_usable_architecture(self))
        # PUT the node with no arguments - should get FORBIDDEN
        response = self.client.put(self.get_node_uri(node), {})
        self.assertEqual(httplib.FORBIDDEN, response.status_code)

    def test_PUT_zone_change_requires_admin(self):
        new_zone = factory.make_Zone()
        node = factory.make_Node(
            owner=self.logged_in_user,
            architecture=make_usable_architecture(self))
        old_zone = node.zone

        response = self.client.put(
            self.get_node_uri(node),
            {'zone': new_zone.name})

        self.assertEqual(httplib.FORBIDDEN, response.status_code)
        # Confirm the node's physical zone has not been updated.
        node = reload_object(node)
        self.assertEqual(old_zone, node.zone)

    def test_PUT_sets_disable_ipv4(self):
        self.become_admin()
        original_setting = factory.pick_bool()
        node = factory.make_Node(
            owner=self.logged_in_user,
            architecture=make_usable_architecture(self),
            disable_ipv4=original_setting)
        new_setting = not original_setting

        response = self.client.put(
            self.get_node_uri(node), {'disable_ipv4': new_setting})
        self.assertEqual(httplib.OK, response.status_code)

        node = reload_object(node)
        self.assertEqual(new_setting, node.disable_ipv4)

    def test_PUT_leaves_disable_ipv4_unchanged_by_default(self):
        self.become_admin()
        original_setting = factory.pick_bool()
        node = factory.make_Node(
            owner=self.logged_in_user,
            architecture=make_usable_architecture(self),
            disable_ipv4=original_setting)
        self.assertEqual(original_setting, node.disable_ipv4)

        response = self.client.put(
            self.get_node_uri(node), {'zone': factory.make_Zone()})
        self.assertEqual(httplib.OK, response.status_code)

        node = reload_object(node)
        self.assertEqual(original_setting, node.disable_ipv4)

    def test_PUT_updates_boot_type(self):
        self.become_admin()
        node = factory.make_Node(
            owner=self.logged_in_user,
            architecture=make_usable_architecture(self),
            boot_type=NODE_BOOT.FASTPATH,
            )
        response = self.client.put(
            reverse('node_handler', args=[node.system_id]),
            {'boot_type': NODE_BOOT.DEBIAN})
        parsed_result = json.loads(response.content)
        self.assertEqual(httplib.OK, response.status_code)
        node = reload_object(node)
        self.assertEqual(node.boot_type, parsed_result['boot_type'])
        self.assertEqual(node.boot_type, NODE_BOOT.DEBIAN)

    def test_PUT_updates_swap_size(self):
        self.become_admin()
        node = factory.make_Node(owner=self.logged_in_user,
                                 architecture=make_usable_architecture(self))
        response = self.client.put(
            reverse('node_handler', args=[node.system_id]),
            {'swap_size': 5 * 1000 ** 3})  # Making sure we overflow 32 bits
        parsed_result = json.loads(response.content)
        node = reload_object(node)
        self.assertEqual(httplib.OK, response.status_code)
        self.assertEqual(node.swap_size, parsed_result['swap_size'])

    def test_PUT_updates_swap_size_suffixes(self):
        self.become_admin()
        node = factory.make_Node(owner=self.logged_in_user,
                                 architecture=make_usable_architecture(self))

        response = self.client.put(
            reverse('node_handler', args=[node.system_id]),
            {'swap_size': '5K'})
        parsed_result = json.loads(response.content)
        self.assertEqual(httplib.OK, response.status_code)
        self.assertEqual(5000, parsed_result['swap_size'])

        response = self.client.put(
            reverse('node_handler', args=[node.system_id]),
            {'swap_size': '5M'})
        parsed_result = json.loads(response.content)
        self.assertEqual(httplib.OK, response.status_code)
        self.assertEqual(5000000, parsed_result['swap_size'])

        response = self.client.put(
            reverse('node_handler', args=[node.system_id]),
            {'swap_size': '5G'})
        parsed_result = json.loads(response.content)
        self.assertEqual(httplib.OK, response.status_code)
        self.assertEqual(5000000000, parsed_result['swap_size'])

        response = self.client.put(
            reverse('node_handler', args=[node.system_id]),
            {'swap_size': '5T'})
        parsed_result = json.loads(response.content)
        self.assertEqual(httplib.OK, response.status_code)
        self.assertEqual(5000000000000, parsed_result['swap_size'])

    def test_PUT_updates_swap_size_invalid_suffix(self):
        self.become_admin()
        node = factory.make_Node(owner=self.logged_in_user,
                                 architecture=make_usable_architecture(self))
        response = self.client.put(
            reverse('node_handler', args=[node.system_id]),
            {'swap_size': '5E'})  # We won't support exabytes yet
        parsed_result = json.loads(response.content)
        self.assertEqual(httplib.BAD_REQUEST, response.status_code)
        self.assertEqual('Invalid size for swap: 5E',
                         parsed_result['swap_size'][0])

    def test_DELETE_deletes_node(self):
        # The api allows to delete a Node.
        self.become_admin()
        node = factory.make_Node(owner=self.logged_in_user)
        system_id = node.system_id
        response = self.client.delete(self.get_node_uri(node))

        self.assertEqual(204, response.status_code)
        self.assertItemsEqual([], Node.objects.filter(system_id=system_id))

    def test_DELETE_rejects_device(self):
        node = factory.make_Node(
            installable=False, owner=self.logged_in_user)
        response = self.client.delete(self.get_node_uri(node))
        self.assertEqual(
            httplib.NOT_FOUND, response.status_code, response.content)

    def test_DELETE_deletes_node_fails_if_not_admin(self):
        # Only superusers can delete nodes.
        node = factory.make_Node(owner=self.logged_in_user)
        response = self.client.delete(self.get_node_uri(node))

        self.assertEqual(httplib.FORBIDDEN, response.status_code)

    def test_DELETE_forbidden_without_edit_permission(self):
        # A user without the edit permission cannot delete a Node.
        node = factory.make_Node()
        response = self.client.delete(self.get_node_uri(node))

        self.assertEqual(httplib.FORBIDDEN, response.status_code)

    def test_DELETE_refuses_to_delete_invisible_node(self):
        # The request to delete a single node is denied if the node isn't
        # visible by the user.
        other_node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=factory.make_User())

        response = self.client.delete(self.get_node_uri(other_node))

        self.assertEqual(httplib.FORBIDDEN, response.status_code)

    def test_DELETE_refuses_to_delete_nonexistent_node(self):
        # When deleting a Node, the api returns a 'Not Found' (404) error
        # if no node is found.
        url = reverse('node_handler', args=['invalid-uuid'])
        response = self.client.delete(url)

        self.assertEqual(httplib.NOT_FOUND, response.status_code)


class TestClaimStickyIpAddressAPI(APITestCase):
    """Tests for /api/1.0/nodes/<node>/?op=claim_sticky_ip_address"""

    def get_node_uri(self, node):
        """Get the API URI for `node`."""
        return reverse('node_handler', args=[node.system_id])

    def test_claim_sticky_ip_address_disallows_when_allocated(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED)
        response = self.client.post(
            self.get_node_uri(node), {'op': 'claim_sticky_ip_address'})
        self.assertEqual(
            httplib.CONFLICT, response.status_code, response.content)
        self.assertEqual(
            "Sticky IP cannot be assigned to a node that is allocated",
            response.content)

    def test_claim_sticky_ip_address_validates_ip_address(self):
        self.become_admin()
        node = factory.make_Node()
        response = self.client.post(
            self.get_node_uri(node), {'op': 'claim_sticky_ip_address',
                                      'requested_address': '192.168.1000.1'})
        self.assertEqual(httplib.BAD_REQUEST, response.status_code)
        self.assertEqual(
            dict(requested_address=["Enter a valid IPv4 or IPv6 address."]),
            json.loads(response.content))

    def test_claim_sticky_ip_address_returns_existing_if_already_exists(self):
        self.become_admin()
        node = factory.make_Node_with_Interface_on_Subnet(disable_ipv4=False)
        # Silence 'update_host_maps'.
        self.patch_autospec(interface_module, "update_host_maps")
        [existing_ip] = node.get_boot_interface().claim_static_ips()
        response = self.client.post(
            self.get_node_uri(node), {'op': 'claim_sticky_ip_address'})
        self.assertEqual(httplib.OK, response.status_code, response.content)
        parsed_node = json.loads(response.content)
        [returned_ip] = parsed_node["ip_addresses"]
        self.assertEqual(
            (existing_ip.ip, IPADDRESS_TYPE.STICKY),
            (returned_ip, existing_ip.alloc_type)
        )

    def test_claim_sticky_ip_address_claims_sticky_ip_address_non_admin(self):
        node = factory.make_Node_with_Interface_on_Subnet(
            owner=self.logged_in_user, disable_ipv4=False)
        # Silence 'update_host_maps'.
        self.patch(interface_module, "update_host_maps")
        response = self.client.post(
            self.get_node_uri(node), {'op': 'claim_sticky_ip_address'})
        self.assertEqual(httplib.OK, response.status_code, response.content)
        parsed_node = json.loads(response.content)
        [returned_ip] = parsed_node["ip_addresses"]
        [given_ip] = StaticIPAddress.objects.filter(
            alloc_type=IPADDRESS_TYPE.STICKY, ip__isnull=False)
        self.assertEqual(
            (given_ip.ip, IPADDRESS_TYPE.STICKY),
            (returned_ip, given_ip.alloc_type),
        )

    def test_claim_sticky_ip_address_checks_edit_permission(self):
        other_user = factory.make_User()
        node = factory.make_Node_with_Interface_on_Subnet(
            owner=other_user, disable_ipv4=False)
        response = self.client.post(
            self.get_node_uri(node), {'op': 'claim_sticky_ip_address'})
        self.assertEqual(
            httplib.FORBIDDEN, response.status_code, response.content)

    def test_claim_sticky_ip_address_claims_sticky_ip_address(self):
        self.become_admin()
        node = factory.make_Node_with_Interface_on_Subnet(disable_ipv4=False)
        # Silence 'update_host_maps'.
        self.patch(interface_module, "update_host_maps")
        response = self.client.post(
            self.get_node_uri(node), {'op': 'claim_sticky_ip_address'})
        self.assertEqual(httplib.OK, response.status_code, response.content)
        parsed_node = json.loads(response.content)
        [returned_ip] = parsed_node["ip_addresses"]
        [given_ip] = StaticIPAddress.objects.filter(
            alloc_type=IPADDRESS_TYPE.STICKY, ip__isnull=False)
        self.assertEqual(
            (given_ip.ip, IPADDRESS_TYPE.STICKY),
            (returned_ip, given_ip.alloc_type),
        )

    def test_claim_sticky_ip_address_allows_macaddress_parameter(self):
        self.become_admin()
        node = factory.make_Node_with_Interface_on_Subnet(disable_ipv4=False)
        boot_interface = node.get_boot_interface()
        subnet = boot_interface.ip_addresses.first().subnet
        second_nic = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.DISCOVERED, ip="",
            interface=second_nic, subnet=subnet)
        # Silence 'update_host_maps'.
        self.patch(interface_module, "update_host_maps")
        response = self.client.post(
            self.get_node_uri(node),
            {
                'op': 'claim_sticky_ip_address',
                'mac_address': second_nic.mac_address.get_raw(),
            })
        self.assertEqual(httplib.OK, response.status_code, response.content)
        [observed_static_ip] = second_nic.ip_addresses.filter(
            alloc_type=IPADDRESS_TYPE.STICKY)
        self.assertEqual(IPADDRESS_TYPE.STICKY, observed_static_ip.alloc_type)

    def test_claim_sticky_ip_address_catches_bad_mac_address_parameter(self):
        self.become_admin()
        node = factory.make_Node_with_Interface_on_Subnet(disable_ipv4=False)
        random_mac = factory.make_mac_address()

        response = self.client.post(
            self.get_node_uri(node),
            {
                'op': 'claim_sticky_ip_address',
                'mac_address': random_mac,
            })
        self.assertEqual(
            httplib.BAD_REQUEST, response.status_code, response.content)
        self.assertEqual(
            "mac_address %s not found on the node" % random_mac,
            response.content)

    def test_claim_sticky_ip_allows_requested_ip(self):
        self.become_admin()
        node = factory.make_Node_with_Interface_on_Subnet(disable_ipv4=False)
        boot_interface = node.get_boot_interface()
        subnet = boot_interface.ip_addresses.first().subnet
        ngi = subnet.nodegroupinterface_set.first()
        requested_address = ngi.static_ip_range_low

        # Silence 'update_host_maps'.
        self.patch(interface_module, "update_host_maps")
        response = self.client.post(
            self.get_node_uri(node),
            {
                'op': 'claim_sticky_ip_address',
                'requested_address': requested_address,
            })
        self.assertEqual(httplib.OK, response.status_code, response.content)
        self.assertIsNotNone(
            StaticIPAddress.objects.filter(
                alloc_type=IPADDRESS_TYPE.STICKY, ip=requested_address,
                subnet=subnet).first())

    def test_claim_sticky_ip_address_detects_out_of_network_requested_ip(self):
        self.become_admin()
        node = factory.make_Node_with_Interface_on_Subnet(disable_ipv4=False)
        boot_interface = node.get_boot_interface()
        subnet = boot_interface.ip_addresses.first().subnet
        ngi = subnet.nodegroupinterface_set.first()
        other_network = factory.make_ipv4_network(but_not=ngi.network)
        requested_address = factory.pick_ip_in_network(other_network)

        response = self.client.post(
            self.get_node_uri(node),
            {
                'op': 'claim_sticky_ip_address',
                'requested_address': requested_address.format(),
            })
        self.assertEqual(
            httplib.FORBIDDEN, response.status_code, response.content)

    def test_claim_sticky_ip_address_detects_unavailable_requested_ip(self):
        self.become_admin()
        # Create 2 nodes on the same nodegroup and interface.
        node = factory.make_Node_with_Interface_on_Subnet(disable_ipv4=False)
        boot_interface = node.get_boot_interface()
        subnet = boot_interface.ip_addresses.first().subnet
        ngi = subnet.nodegroupinterface_set.first()
        other_node = factory.make_Node(
            interface=True, nodegroup=ngi.nodegroup, disable_ipv4=False)
        other_mac = other_node.get_boot_interface()
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.DISCOVERED, ip="",
            interface=other_mac, subnet=subnet)

        # Allocate an IP to one of the nodes.
        self.patch_autospec(interface_module, "update_host_maps")
        requested_address = IPAddress(ngi.static_ip_range_low) + 1
        requested_address = requested_address.format()
        other_node.get_boot_interface().claim_static_ips(
            requested_address=requested_address)

        # Use the API to try to duplicate the same IP on the other node.
        response = self.client.post(
            self.get_node_uri(node),
            {
                'op': 'claim_sticky_ip_address',
                'requested_address': requested_address,
            })
        self.assertEqual(
            httplib.NOT_FOUND, response.status_code, response.content)


class TestNodeAPITransactional(APITransactionTestCase):
    '''The following TestNodeAPI tests require APITransactionTestCase,
        and thus, have been separated from the TestNodeAPI above.
    '''

    def test_POST_start_returns_error_when_static_ips_exhausted(self):
        node = factory.make_Node_with_Interface_on_Subnet(
            owner=self.logged_in_user, status=NODE_STATUS.ALLOCATED,
            architecture=make_usable_architecture(self))
        boot_interface = node.get_boot_interface()
        subnet = boot_interface.ip_addresses.first().subnet
        ngi = subnet.nodegroupinterface_set.first()

        # Narrow the available IP range and pre-claim the only address.
        ngi.static_ip_range_high = ngi.static_ip_range_low
        ngi.save()
        with transaction.atomic():
            StaticIPAddress.objects.allocate_new(
                ngi.network, ngi.static_ip_range_low, ngi.static_ip_range_high,
                ngi.ip_range_low, ngi.ip_range_high)

        osystem = make_usable_osystem(self)
        distro_series = osystem['default_release']
        response = self.client.post(
            TestNodeAPI.get_node_uri(node),
            {
                'op': 'start',
                'distro_series': distro_series,
            })
        self.assertEqual(httplib.SERVICE_UNAVAILABLE, response.status_code)


class TestNodeReleaseStickyIpAddressAPI(APITestCase):
    """Tests for /api/1.0/nodes/?op=release_sticky_ip_address."""

    @staticmethod
    def get_node_uri(node):
        """Get the API URI for `node`."""
        return reverse('node_handler', args=[node.system_id])

    def test__releases_ip_address(self):
        self.become_admin()
        node = factory.make_Node_with_Interface_on_Subnet(
            disable_ipv4=False)
        # Silence 'update_host_maps' and 'remove_host_maps'
        self.patch(interface_module, "update_host_maps")
        self.patch(interface_module, "remove_host_maps")
        response = self.client.post(
            self.get_node_uri(node), {'op': 'claim_sticky_ip_address'})
        self.assertEqual(httplib.OK, response.status_code, response.content)
        parsed_node = json.loads(response.content)
        self.expectThat(parsed_node["ip_addresses"], Not(HasLength(0)))

        response = self.client.post(
            self.get_node_uri(node), {'op': 'release_sticky_ip_address'})
        self.assertEqual(httplib.OK, response.status_code, response.content)
        parsed_node = json.loads(response.content)
        self.expectThat(parsed_node["ip_addresses"], HasLength(0))

    def test__validates_ip_address(self):
        self.become_admin()
        node = factory.make_Node_with_Interface_on_Subnet(
            disable_ipv4=False)
        # Silence 'update_host_maps' and 'remove_host_maps'
        response = self.client.post(
            self.get_node_uri(node), {'op': 'release_sticky_ip_address',
                                      'address': '192.168.1000.1'})
        self.assertEqual(httplib.BAD_REQUEST, response.status_code)
        self.assertEqual(
            dict(address=["Enter a valid IPv4 or IPv6 address."]),
            json.loads(response.content))


class TestNodeReleaseStickyIpAddressAPITransactional(APITransactionTestCase):
    """The following TestNodeReleaseStickyIpAddressAPI tests require
        APITransactionTestCase, and thus, have been separated
        from the TestNodeReleaseStickyIpAddressAPI above.
    """

    def test__releases_all_ip_addresses(self):
        network = factory._make_random_network(slash=24)
        subnet = factory.make_Subnet(cidr=unicode(network.cidr))
        node = factory.make_Node_with_Interface_on_Subnet(
            status=NODE_STATUS.ALLOCATED, installable=True, subnet=subnet,
            disable_ipv4=False, owner=self.logged_in_user)
        boot_interface = node.get_boot_interface()
        # Silence 'update_host_maps' and 'remove_host_maps'
        self.patch(interface_module, "update_host_maps")
        self.patch(interface_module, "remove_host_maps")
        for interface in node.interface_set.all():
            with transaction.atomic():
                allocated = boot_interface.claim_static_ips()
            self.expectThat(allocated, HasLength(1))
        response = self.client.post(
            TestNodeReleaseStickyIpAddressAPI.get_node_uri(node),
            {'op': 'release_sticky_ip_address'})
        self.assertEqual(httplib.OK, response.status_code, response.content)
        parsed_node = json.loads(response.content)
        self.expectThat(parsed_node["ip_addresses"], HasLength(0))

    def test__releases_specific_address(self):
        network = factory._make_random_network(slash=24)
        subnet = factory.make_Subnet(cidr=unicode(network.cidr))
        node = factory.make_Node_with_Interface_on_Subnet(
            status=NODE_STATUS.ALLOCATED, installable=True, subnet=subnet,
            disable_ipv4=False, owner=self.logged_in_user)
        boot_interface = node.get_boot_interface()
        # Silence 'update_host_maps' and 'remove_host_maps'
        self.patch(interface_module, "update_host_maps")
        self.patch(interface_module, "remove_host_maps")
        ips = []
        for interface in node.interface_set.all():
            with transaction.atomic():
                allocated = boot_interface.claim_static_ips()
            self.expectThat(allocated, HasLength(1))
            # Note: 'allocated' is a list of (ip,mac) tuples
            ips.append(allocated[0])
        response = self.client.post(
            TestNodeReleaseStickyIpAddressAPI.get_node_uri(node),
            {
                'op': 'release_sticky_ip_address',
                'address': ips[0].ip
            })
        self.assertEqual(httplib.OK, response.status_code, response.content)
        parsed_node = json.loads(response.content)
        self.expectThat(parsed_node["ip_addresses"], HasLength(0))

    def test__rejected_if_not_permitted(self):
        node = factory.make_Node_with_Interface_on_Subnet(
            status=NODE_STATUS.ALLOCATED, disable_ipv4=False,
            owner=factory.make_User())
        boot_interface = node.get_boot_interface()
        # Silence 'update_host_maps' and 'remove_host_maps'
        self.patch(interface_module, "update_host_maps")
        self.patch(interface_module, "remove_host_maps")
        with transaction.atomic():
            boot_interface.claim_static_ips()
        response = self.client.post(
            TestNodeReleaseStickyIpAddressAPI.get_node_uri(node),
            {'op': 'release_sticky_ip_address'})
        self.assertEqual(
            httplib.FORBIDDEN, response.status_code, response.content)


class TestGetDetails(APITestCase):
    """Tests for /api/1.0/nodes/<node>/?op=details."""

    def make_lshw_result(self, node, script_result=0):
        return factory.make_NodeResult_for_commissioning(
            node=node, name=commissioningscript.LSHW_OUTPUT_NAME,
            script_result=script_result)

    def make_lldp_result(self, node, script_result=0):
        return factory.make_NodeResult_for_commissioning(
            node=node, name=commissioningscript.LLDP_OUTPUT_NAME,
            script_result=script_result)

    def get_details(self, node):
        url = reverse('node_handler', args=[node.system_id])
        response = self.client.get(url, {'op': 'details'})
        self.assertEqual(httplib.OK, response.status_code)
        self.assertEqual('application/bson', response['content-type'])
        return bson.BSON(response.content).decode()

    def test_GET_returns_empty_details_when_there_are_none(self):
        node = factory.make_Node()
        self.assertDictEqual(
            {"lshw": None, "lldp": None},
            self.get_details(node))

    def test_GET_returns_all_details(self):
        node = factory.make_Node()
        lshw_result = self.make_lshw_result(node)
        lldp_result = self.make_lldp_result(node)
        self.assertDictEqual(
            {"lshw": bson.Binary(lshw_result.data),
             "lldp": bson.Binary(lldp_result.data)},
            self.get_details(node))

    def test_GET_returns_only_those_details_that_exist(self):
        node = factory.make_Node()
        lshw_result = self.make_lshw_result(node)
        self.assertDictEqual(
            {"lshw": bson.Binary(lshw_result.data),
             "lldp": None},
            self.get_details(node))

    def test_GET_returns_not_found_when_node_does_not_exist(self):
        url = reverse('node_handler', args=['does-not-exist'])
        response = self.client.get(url, {'op': 'details'})
        self.assertEqual(httplib.NOT_FOUND, response.status_code)


class TestMarkBroken(APITestCase):
    """Tests for /api/1.0/nodes/<node>/?op=mark_broken"""

    def get_node_uri(self, node):
        """Get the API URI for `node`."""
        return reverse('node_handler', args=[node.system_id])

    def test_mark_broken_changes_status(self):
        node = factory.make_Node(
            status=NODE_STATUS.COMMISSIONING, owner=self.logged_in_user)
        response = self.client.post(
            self.get_node_uri(node), {'op': 'mark_broken'})
        self.assertEqual(httplib.OK, response.status_code)
        self.assertEqual(NODE_STATUS.BROKEN, reload_object(node).status)

    def test_mark_broken_updates_error_description(self):
        # 'error_description' parameter was renamed 'comment' for consistency
        # make sure this comment updates the node's error_description
        node = factory.make_Node(
            status=NODE_STATUS.COMMISSIONING, owner=self.logged_in_user)
        comment = factory.make_name('comment')
        response = self.client.post(
            self.get_node_uri(node),
            {'op': 'mark_broken', 'comment': comment})
        self.assertEqual(httplib.OK, response.status_code)
        node = reload_object(node)
        self.assertEqual(
            (NODE_STATUS.BROKEN, comment),
            (node.status, node.error_description)
        )

    def test_mark_broken_updates_error_description_compatibility(self):
        # test old 'error_description' parameter is honored for compatibility
        node = factory.make_Node(
            status=NODE_STATUS.COMMISSIONING, owner=self.logged_in_user)
        error_description = factory.make_name('error_description')
        response = self.client.post(
            self.get_node_uri(node),
            {'op': 'mark_broken', 'error_description': error_description})
        self.assertEqual(httplib.OK, response.status_code)
        node = reload_object(node)
        self.assertEqual(
            (NODE_STATUS.BROKEN, error_description),
            (node.status, node.error_description)
        )

    def test_mark_broken_passes_comment(self):
        node = factory.make_Node(
            status=NODE_STATUS.COMMISSIONING, owner=self.logged_in_user)
        node_mark_broken = self.patch(node_module.Node, 'mark_broken')
        comment = factory.make_name('comment')
        self.client.post(
            self.get_node_uri(node),
            {'op': 'mark_broken', 'comment': comment})
        self.assertThat(
            node_mark_broken,
            MockCalledOnceWith(self.logged_in_user, comment))

    def test_mark_broken_handles_missing_comment(self):
        node = factory.make_Node(
            status=NODE_STATUS.COMMISSIONING, owner=self.logged_in_user)
        node_mark_broken = self.patch(node_module.Node, 'mark_broken')
        self.client.post(
            self.get_node_uri(node), {'op': 'mark_broken'})
        self.assertThat(
            node_mark_broken,
            MockCalledOnceWith(self.logged_in_user, None))

    def test_mark_broken_requires_ownership(self):
        node = factory.make_Node(status=NODE_STATUS.COMMISSIONING)
        response = self.client.post(
            self.get_node_uri(node), {'op': 'mark_broken'})
        self.assertEqual(httplib.FORBIDDEN, response.status_code)

    def test_mark_broken_allowed_from_any_other_state(self):
        for status, _ in NODE_STATUS_CHOICES:
            if status == NODE_STATUS.BROKEN:
                continue

            node = factory.make_Node(status=status, owner=self.logged_in_user)
            response = self.client.post(
                self.get_node_uri(node), {'op': 'mark_broken'})
            self.expectThat(response.status_code, Equals(httplib.OK), response)
            node = reload_object(node)
            self.expectThat(node.status, Equals(NODE_STATUS.BROKEN))


class TestMarkFixed(APITestCase):
    """Tests for /api/1.0/nodes/<node>/?op=mark_fixed"""

    def get_node_uri(self, node):
        """Get the API URI for `node`."""
        return reverse('node_handler', args=[node.system_id])

    def test_mark_fixed_changes_status(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.BROKEN)
        response = self.client.post(
            self.get_node_uri(node), {'op': 'mark_fixed'})
        self.assertEqual(httplib.OK, response.status_code)
        self.assertEqual(NODE_STATUS.READY, reload_object(node).status)

    def test_mark_fixed_requires_admin(self):
        node = factory.make_Node(status=NODE_STATUS.BROKEN)
        response = self.client.post(
            self.get_node_uri(node), {'op': 'mark_fixed'})
        self.assertEqual(httplib.FORBIDDEN, response.status_code)

    def test_mark_fixed_passes_comment(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.BROKEN)
        node_mark_fixed = self.patch(node_module.Node, 'mark_fixed')
        comment = factory.make_name('comment')
        self.client.post(
            self.get_node_uri(node),
            {'op': 'mark_fixed', 'comment': comment})
        self.assertThat(
            node_mark_fixed,
            MockCalledOnceWith(self.logged_in_user, comment))

    def test_mark_fixed_handles_missing_comment(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.BROKEN)
        node_mark_fixed = self.patch(node_module.Node, 'mark_fixed')
        self.client.post(
            self.get_node_uri(node), {'op': 'mark_fixed'})
        self.assertThat(
            node_mark_fixed,
            MockCalledOnceWith(self.logged_in_user, None))


class TestPowerParameters(APITestCase):
    def get_node_uri(self, node):
        """Get the API URI for `node`."""
        return reverse('node_handler', args=[node.system_id])

    def test_get_power_parameters(self):
        self.become_admin()
        node = factory.make_Node(
            power_parameters=factory.make_name("power_parameters"))
        response = self.client.get(
            self.get_node_uri(node), {'op': 'power_parameters'})
        self.assertEqual(httplib.OK, response.status_code, response.content)
        parsed_params = json.loads(response.content)
        self.assertEqual(node.power_parameters, parsed_params)

    def test_get_power_parameters_empty(self):
        self.become_admin()
        node = factory.make_Node()
        response = self.client.get(
            self.get_node_uri(node), {'op': 'power_parameters'})
        self.assertEqual(httplib.OK, response.status_code, response.content)
        parsed_params = json.loads(response.content)
        self.assertEqual("", parsed_params)

    def test_power_parameters_requires_admin(self):
        node = factory.make_Node()
        response = self.client.get(
            self.get_node_uri(node), {'op': 'power_parameters'})
        self.assertEqual(
            httplib.FORBIDDEN, response.status_code, response.content)


class TestAbortOperation(APITransactionTestCase):
    """Tests for /api/1.0/nodes/<node>/?op=abort_operation"""

    def get_node_uri(self, node):
        """Get the API URI for `node`."""
        return reverse('node_handler', args=[node.system_id])

    def test_abort_operation_changes_state(self):
        node = factory.make_Node(
            status=NODE_STATUS.DISK_ERASING, owner=self.logged_in_user)
        node_stop = self.patch(node, "stop")
        node_stop.side_effect = lambda user: post_commit()

        response = self.client.post(
            self.get_node_uri(node), {'op': 'abort_operation'})

        self.assertEqual(httplib.OK, response.status_code)
        self.assertEqual(
            NODE_STATUS.FAILED_DISK_ERASING, reload_object(node).status)

    def test_abort_operation_fails_for_unsupported_operation(self):
        node = factory.make_Node(status=NODE_STATUS.COMMISSIONING)
        response = self.client.post(
            self.get_node_uri(node), {'op': 'abort_operation'})
        self.assertEqual(httplib.FORBIDDEN, response.status_code)

    def test_abort_operation_passes_comment(self):
        self.become_admin()
        node = factory.make_Node(
            status=NODE_STATUS.DISK_ERASING, owner=self.logged_in_user)
        node_method = self.patch(node_module.Node, 'abort_operation')
        comment = factory.make_name('comment')
        self.client.post(
            self.get_node_uri(node),
            {'op': 'abort_operation', 'comment': comment})
        self.assertThat(
            node_method,
            MockCalledOnceWith(self.logged_in_user, comment))

    def test_abort_operation_handles_missing_comment(self):
        self.become_admin()
        node = factory.make_Node(
            status=NODE_STATUS.DISK_ERASING, owner=self.logged_in_user)
        node_method = self.patch(node_module.Node, 'abort_operation')
        self.client.post(
            self.get_node_uri(node), {'op': 'abort_operation'})
        self.assertThat(
            node_method,
            MockCalledOnceWith(self.logged_in_user, None))


class TestSetStorageLayout(APITestCase):

    def get_node_uri(self, node):
        """Get the API URI for `node`."""
        return reverse('node_handler', args=[node.system_id])

    def test__403_when_not_admin(self):
        node = factory.make_Node(status=NODE_STATUS.READY)
        response = self.client.post(
            self.get_node_uri(node), {'op': 'set_storage_layout'})
        self.assertEquals(
            httplib.FORBIDDEN, response.status_code, response.content)

    def test__409_when_node_not_ready(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED)
        response = self.client.post(
            self.get_node_uri(node), {'op': 'set_storage_layout'})
        self.assertEquals(
            httplib.CONFLICT, response.status_code, response.content)

    def test__400_when_storage_layout_missing(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        response = self.client.post(
            self.get_node_uri(node), {'op': 'set_storage_layout'})
        self.assertEquals(
            httplib.BAD_REQUEST, response.status_code, response.content)
        self.assertEquals({
            "storage_layout": [
                "This field is required."],
            }, json.loads(response.content))

    def test__400_when_invalid_optional_param(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        factory.make_PhysicalBlockDevice(node=node)
        response = self.client.post(
            self.get_node_uri(node), {
                'op': 'set_storage_layout',
                'storage_layout': 'flat',
                'boot_size': MIN_BOOT_PARTITION_SIZE - 1,
                })
        self.assertEquals(
            httplib.BAD_REQUEST, response.status_code, response.content)
        self.assertEquals({
            "boot_size": [
                "Size is too small. Minimum size is %s." % (
                    MIN_BOOT_PARTITION_SIZE)],
            }, json.loads(response.content))

    def test__400_when_no_boot_disk(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        response = self.client.post(
            self.get_node_uri(node), {
                'op': 'set_storage_layout',
                'storage_layout': 'flat',
                })
        self.assertEquals(
            httplib.BAD_REQUEST, response.status_code, response.content)
        self.assertEquals(
            "Node is missing a boot disk; no storage layout can be applied.",
            response.content)

    def test__400_when_layout_error(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        mock_set_storage_layout = self.patch(Node, "set_storage_layout")
        error_msg = factory.make_name("error")
        mock_set_storage_layout.side_effect = StorageLayoutError(error_msg)
        response = self.client.post(
            self.get_node_uri(node), {
                'op': 'set_storage_layout',
                'storage_layout': 'flat',
                })
        self.assertEquals(
            httplib.BAD_REQUEST, response.status_code, response.content)
        self.assertEquals(
            "Failed to configure storage layout 'flat': %s" % error_msg,
            response.content)

    def test__400_when_layout_not_supported(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        factory.make_PhysicalBlockDevice(node=node)
        response = self.client.post(
            self.get_node_uri(node), {
                'op': 'set_storage_layout',
                'storage_layout': 'bcache',
                })
        self.assertEquals(
            httplib.BAD_REQUEST, response.status_code, response.content)
        self.assertEquals(
            "Failed to configure storage layout 'bcache': Node doesn't "
            "have an available cache device to setup bcache.",
            response.content)

    def test__calls_set_storage_layout_on_node(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        mock_set_storage_layout = self.patch(Node, "set_storage_layout")
        response = self.client.post(
            self.get_node_uri(node), {
                'op': 'set_storage_layout',
                'storage_layout': 'flat',
                })
        self.assertEquals(
            httplib.OK, response.status_code, response.content)
        self.assertThat(
            mock_set_storage_layout,
            MockCalledOnceWith('flat', params=ANY, allow_fallback=False))


class TestClearDefaultGateways(APITestCase):

    def get_node_uri(self, node):
        """Get the API URI for `node`."""
        return reverse('node_handler', args=[node.system_id])

    def test__403_when_not_admin(self):
        node = factory.make_Node(
            owner=self.logged_in_user, status=NODE_STATUS.ALLOCATED)
        response = self.client.post(
            self.get_node_uri(node), {'op': 'clear_default_gateways'})
        self.assertEquals(
            httplib.FORBIDDEN, response.status_code, response.content)

    def test__clears_default_gateways(self):
        self.become_admin()
        node = factory.make_Node(
            owner=self.logged_in_user, status=NODE_STATUS.ALLOCATED)
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        network_v4 = factory.make_ipv4_network()
        subnet_v4 = factory.make_Subnet(
            cidr=unicode(network_v4.cidr), vlan=interface.vlan)
        link_v4 = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO, ip="",
            subnet=subnet_v4, interface=interface)
        node.gateway_link_ipv4 = link_v4
        network_v6 = factory.make_ipv6_network()
        subnet_v6 = factory.make_Subnet(
            cidr=unicode(network_v6.cidr), vlan=interface.vlan)
        link_v6 = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO, ip="",
            subnet=subnet_v6, interface=interface)
        node.gateway_link_ipv6 = link_v6
        node.save()
        response = self.client.post(
            self.get_node_uri(node), {'op': 'clear_default_gateways'})
        self.assertEquals(
            httplib.OK, response.status_code, response.content)
        node = reload_object(node)
        self.assertIsNone(node.gateway_link_ipv4)
        self.assertIsNone(node.gateway_link_ipv6)
