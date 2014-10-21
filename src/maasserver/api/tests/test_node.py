# Copyright 2013-2014 Canonical Ltd.  This software is licensed under the
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
from maasserver import forms
from maasserver.enum import (
    IPADDRESS_TYPE,
    NODE_STATUS,
    NODE_STATUS_CHOICES_DICT,
    )
from maasserver.fields import (
    MAC,
    MAC_ERROR_MSG,
    )
from maasserver.models import (
    Node,
    node as node_module,
    StaticIPAddress,
    )
from maasserver.models.node import RELEASABLE_STATUSES
from maasserver.testing.api import APITestCase
from maasserver.testing.architecture import make_usable_architecture
from maasserver.testing.factory import factory
from maasserver.testing.oauthclient import OAuthAuthenticatedClient
from maasserver.testing.orm import (
    reload_object,
    reload_objects,
    )
from maasserver.testing.osystems import make_usable_osystem
from maasserver.testing.testcase import MAASServerTestCase
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
from provisioningserver.utils.enum import map_enum


class NodeAnonAPITest(MAASServerTestCase):

    def setUp(self):
        super(NodeAnonAPITest, self).setUp()
        self.patch(node_module, 'wait_for_power_commands')

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
        self.patch(node_module, 'wait_for_power_commands')

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
        self.patch(node_module, 'wait_for_power_commands')

    def test_handler_path(self):
        self.assertEqual(
            '/api/1.0/nodes/node-name/',
            reverse('node_handler', args=['node-name']))

    def get_node_uri(self, node):
        """Get the API URI for `node`."""
        return reverse('node_handler', args=[node.system_id])

    def test_GET_returns_node(self):
        # The api allows for fetching a single Node (using system_id).
        node = factory.make_Node()
        response = self.client.get(self.get_node_uri(node))

        self.assertEqual(httplib.OK, response.status_code)
        parsed_result = json.loads(response.content)
        self.assertEqual(node.hostname, parsed_result['hostname'])
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
        mac = factory.make_MACAddress(node=node)
        lease = factory.make_DHCPLease(
            nodegroup=node.nodegroup, mac=mac.mac_address)
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

    def test_GET_refuses_to_access_nonexistent_node(self):
        # When fetching a Node, the api returns a 'Not Found' (404) error
        # if no node is found.
        url = reverse('node_handler', args=['invalid-uuid'])

        response = self.client.get(url)

        self.assertEqual(httplib.NOT_FOUND, response.status_code)

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

    def test_POST_stop_checks_permission(self):
        node = factory.make_Node()
        node_stop = self.patch(node, 'stop')
        response = self.client.post(self.get_node_uri(node), {'op': 'stop'})
        self.assertEqual(httplib.FORBIDDEN, response.status_code)
        self.assertThat(node_stop, MockNotCalled())

    def test_POST_stop_returns_nothing_if_node_was_not_stopped(self):
        # The node may not be stopped by stop_nodes because, for example, its
        # power type does not support it. In this case the node is not
        # returned to the caller.
        node = factory.make_Node(owner=self.logged_in_user)
        node_stop = self.patch(node_module.Node, 'stop')
        node_stop.return_value = False
        response = self.client.post(self.get_node_uri(node), {'op': 'stop'})
        self.assertEqual(httplib.OK, response.status_code)
        self.assertIsNone(json.loads(response.content))
        self.assertThat(node_stop, MockCalledOnceWith(
            ANY, stop_mode=ANY))

    def test_POST_stop_returns_node(self):
        node = factory.make_Node(owner=self.logged_in_user)
        self.patch(node_module.Node, 'stop').return_value = True
        response = self.client.post(self.get_node_uri(node), {'op': 'stop'})
        self.assertEqual(httplib.OK, response.status_code)
        self.assertEqual(
            node.system_id, json.loads(response.content)['system_id'])

    def test_POST_stop_may_be_repeated(self):
        node = factory.make_Node(
            owner=self.logged_in_user, mac=True,
            power_type='ether_wake')
        self.patch(node, 'stop')
        self.client.post(self.get_node_uri(node), {'op': 'stop'})
        response = self.client.post(self.get_node_uri(node), {'op': 'stop'})
        self.assertEqual(httplib.OK, response.status_code)

    def test_POST_stop_stops_nodes(self):
        node = factory.make_Node(owner=self.logged_in_user)
        node_stop = self.patch(node_module.Node, 'stop')
        stop_mode = factory.make_name('stop_mode')
        self.client.post(
            self.get_node_uri(node), {'op': 'stop', 'stop_mode': stop_mode})
        self.assertThat(
            node_stop,
            MockCalledOnceWith(self.logged_in_user, stop_mode=stop_mode))

    def test_POST_start_checks_permission(self):
        node = factory.make_Node()
        response = self.client.post(self.get_node_uri(node), {'op': 'start'})
        self.assertEqual(httplib.FORBIDDEN, response.status_code)

    def test_POST_start_returns_node(self):
        node = factory.make_Node(
            owner=self.logged_in_user, mac=True,
            power_type='ether_wake')
        response = self.client.post(self.get_node_uri(node), {'op': 'start'})
        self.assertEqual(httplib.OK, response.status_code)
        self.assertEqual(
            node.system_id, json.loads(response.content)['system_id'])

    def test_POST_start_sets_osystem_and_distro_series(self):
        self.patch(node_module, 'wait_for_power_commands')
        node = factory.make_Node(
            owner=self.logged_in_user, mac=True,
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
            owner=self.logged_in_user, mac=True,
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
        self.patch(node_module, 'wait_for_power_commands')
        node = factory.make_Node(
            owner=self.logged_in_user, mac=True,
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
            owner=self.logged_in_user, mac=True,
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

    def test_POST_start_may_be_repeated(self):
        node = factory.make_Node(
            owner=self.logged_in_user, mac=True,
            power_type='ether_wake')
        self.client.post(self.get_node_uri(node), {'op': 'start'})
        response = self.client.post(self.get_node_uri(node), {'op': 'start'})
        self.assertEqual(httplib.OK, response.status_code)

    def test_POST_start_stores_user_data(self):
        node = factory.make_Node(
            owner=self.logged_in_user, mac=True,
            power_type='ether_wake')
        user_data = (
            b'\xff\x00\xff\xfe\xff\xff\xfe' +
            factory.make_string().encode('ascii'))
        response = self.client.post(
            self.get_node_uri(node), {
                'op': 'start',
                'user_data': b64encode(user_data),
                })
        self.assertEqual(httplib.OK, response.status_code)
        self.assertEqual(user_data, NodeUserData.objects.get_user_data(node))

    def test_POST_start_returns_error_when_static_ips_exhausted(self):
        node = factory.make_node_with_mac_attached_to_nodegroupinterface(
            owner=self.logged_in_user, status=NODE_STATUS.ALLOCATED)
        ngi = node.get_primary_mac().cluster_interface

        # Narrow the available IP range and pre-claim the only address.
        ngi.static_ip_range_high = ngi.static_ip_range_low
        ngi.save()
        StaticIPAddress.objects.allocate_new(
            ngi.static_ip_range_high, ngi.static_ip_range_low)

        response = self.client.post(self.get_node_uri(node), {'op': 'start'})
        self.assertEqual(httplib.SERVICE_UNAVAILABLE, response.status_code)

    def test_POST_release_releases_owned_node(self):
        owned_statuses = [
            NODE_STATUS.RESERVED,
            NODE_STATUS.ALLOCATED,
            ]
        owned_nodes = [
            factory.make_Node(
                owner=self.logged_in_user, status=status, power_type='ipmi')
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
        owned_node = factory.make_Node(
            owner=self.logged_in_user,
            status=NODE_STATUS.FAILED_DEPLOYMENT,
            power_type='ipmi')
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

    def test_POST_release_forbidden_if_user_cannot_edit_node(self):
        node = factory.make_Node(status=NODE_STATUS.READY)
        response = self.client.post(
            self.get_node_uri(node), {'op': 'release'})
        self.assertEqual(httplib.FORBIDDEN, response.status_code)

    def test_POST_release_fails_for_other_node_states(self):
        releasable_statuses = (
            RELEASABLE_STATUSES + [NODE_STATUS.READY])
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
        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=factory.make_User(),
            power_type='ipmi')
        self.become_admin()
        response = self.client.post(
            self.get_node_uri(node), {'op': 'release'})
        self.assertEqual(httplib.OK, response.status_code, response.content)
        self.assertEqual(NODE_STATUS.RELEASING, reload_object(node).status)

    def test_POST_release_combines_with_acquire(self):
        node = factory.make_Node(status=NODE_STATUS.READY, power_type='ipmi')
        response = self.client.post(
            reverse('nodes_handler'), {'op': 'acquire'})
        self.assertEqual(NODE_STATUS.ALLOCATED, reload_object(node).status)
        node_uri = json.loads(response.content)['resource_uri']
        response = self.client.post(node_uri, {'op': 'release'})
        self.assertEqual(httplib.OK, response.status_code, response.content)
        self.assertEqual(NODE_STATUS.RELEASING, reload_object(node).status)

    def test_POST_commission_commissions_node(self):
        node = factory.make_Node(
            status=NODE_STATUS.READY, owner=factory.make_User())
        self.become_admin()
        response = self.client.post(
            self.get_node_uri(node), {'op': 'commission'})
        self.assertEqual(httplib.OK, response.status_code)
        self.assertEqual(NODE_STATUS.COMMISSIONING, reload_object(node).status)

    def test_PUT_updates_node(self):
        # The api allows the updating of a Node.
        node = factory.make_Node(
            hostname='diane', owner=self.logged_in_user,
            architecture=make_usable_architecture(self))
        response = self.client_put(
            self.get_node_uri(node), {'hostname': 'francis'})
        parsed_result = json.loads(response.content)

        self.assertEqual(httplib.OK, response.status_code)
        self.assertEqual('francis', parsed_result['hostname'])
        self.assertEqual(0, Node.objects.filter(hostname='diane').count())
        self.assertEqual(1, Node.objects.filter(hostname='francis').count())

    def test_PUT_omitted_hostname(self):
        hostname = factory.make_name('hostname')
        arch = make_usable_architecture(self)
        node = factory.make_Node(
            hostname=hostname, owner=self.logged_in_user, architecture=arch)
        response = self.client_put(
            self.get_node_uri(node),
            {'architecture': arch})
        self.assertEqual(httplib.OK, response.status_code, response.content)
        self.assertTrue(Node.objects.filter(hostname=hostname).exists())

    def test_PUT_ignores_unknown_fields(self):
        node = factory.make_Node(
            owner=self.logged_in_user,
            architecture=make_usable_architecture(self))
        field = factory.make_string()
        response = self.client_put(
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
        self.client_put(
            self.get_node_uri(node),
            {'power_type': new_power_type}
            )

        self.assertEqual(
            new_power_type, reload_object(node).power_type)

    def test_PUT_non_admin_cannot_change_power_type(self):
        original_power_type = factory.pick_power_type()
        new_power_type = factory.pick_power_type(but_not=original_power_type)
        node = factory.make_Node(
            owner=self.logged_in_user, power_type=original_power_type)
        self.client_put(
            self.get_node_uri(node),
            {'power_type': new_power_type}
            )

        self.assertEqual(
            original_power_type, reload_object(node).power_type)

    def test_resource_uri_points_back_at_node(self):
        # When a Node is returned by the API, the field 'resource_uri'
        # provides the URI for this Node.
        node = factory.make_Node(
            hostname='diane', owner=self.logged_in_user,
            architecture=make_usable_architecture(self))
        response = self.client_put(
            self.get_node_uri(node), {'hostname': 'francis'})
        parsed_result = json.loads(response.content)

        self.assertEqual(
            reverse('node_handler', args=[parsed_result['system_id']]),
            parsed_result['resource_uri'])

    def test_PUT_rejects_invalid_data(self):
        # If the data provided to update a node is invalid, a 'Bad request'
        # response is returned.
        node = factory.make_Node(
            hostname='diane', owner=self.logged_in_user,
            architecture=make_usable_architecture(self))
        response = self.client_put(
            self.get_node_uri(node), {'hostname': '.'})
        parsed_result = json.loads(response.content)

        self.assertEqual(httplib.BAD_REQUEST, response.status_code)
        self.assertEqual(
            {'hostname': ["Hostname contains empty name."]},
            parsed_result)

    def test_PUT_refuses_to_update_invisible_node(self):
        # The request to update a single node is denied if the node isn't
        # visible by the user.
        other_node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=factory.make_User())

        response = self.client_put(self.get_node_uri(other_node))

        self.assertEqual(httplib.FORBIDDEN, response.status_code)

    def test_PUT_refuses_to_update_nonexistent_node(self):
        # When updating a Node, the api returns a 'Not Found' (404) error
        # if no node is found.
        url = reverse('node_handler', args=['invalid-uuid'])
        response = self.client_put(url)

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
        response = self.client_put(
            self.get_node_uri(node),
            {'power_parameters_mac_address': new_power_address})

        self.assertEqual(httplib.OK, response.status_code)
        self.assertEqual(
            {'mac_address': new_power_address},
            reload_object(node).power_parameters)

    def test_PUT_updates_cpu_memory_storage(self):
        self.become_admin()
        node = factory.make_Node(
            owner=self.logged_in_user,
            power_type=factory.pick_power_type(),
            architecture=make_usable_architecture(self))
        response = self.client_put(
            self.get_node_uri(node),
            {'cpu_count': 1, 'memory': 1024, 'storage': 2048})
        self.assertEqual(httplib.OK, response.status_code)
        node = reload_object(node)
        self.assertEqual(1, node.cpu_count)
        self.assertEqual(1024, node.memory)
        self.assertEqual(2048, node.storage)

    def test_PUT_updates_power_parameters_accepts_only_mac_for_wol(self):
        self.become_admin()
        node = factory.make_Node(
            owner=self.logged_in_user,
            power_type='ether_wake',
            architecture=make_usable_architecture(self))
        # Create an invalid power_parameter for WoL (not a valid
        # MAC address).
        new_power_address = factory.make_string()
        response = self.client_put(
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
        response = self.client_put(
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
        response = self.client_put(
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
        response = self.client_put(
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
        response = self.client_put(
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
        response = self.client_put(
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
        response = self.client_put(
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

        response = self.client_put(
            self.get_node_uri(node), {'zone': new_zone.name})

        self.assertEqual(httplib.OK, response.status_code)
        node = reload_object(node)
        self.assertEqual(new_zone, node.zone)

    def test_PUT_does_not_set_zone_if_not_present(self):
        self.become_admin()
        new_name = factory.make_name()
        node = factory.make_Node(architecture=make_usable_architecture(self))
        old_zone = node.zone

        response = self.client_put(
            self.get_node_uri(node), {'hostname': new_name})

        self.assertEqual(httplib.OK, response.status_code)
        node = reload_object(node)
        self.assertEqual((old_zone, new_name), (node.zone, node.hostname))

    #@skip(
    #    "XXX: JeroenVermeulen 2013-12-11 bug=1259872: Clearing the zone "
    #    "field does not work..")
    def test_PUT_clears_zone(self):
        # The @skip above breaks some 150 tests, with a strange error.
        # Figuring this out is taking too long; I'm disabling the test in a
        # simpler way.
        return
        self.become_admin()
        node = factory.make_Node(zone=factory.make_Zone())

        response = self.client_put(self.get_node_uri(node), {'zone': ''})

        self.assertEqual(httplib.OK, response.status_code)
        node = reload_object(node)
        self.assertEqual(None, node.zone)

    def test_PUT_without_zone_leaves_zone_unchanged(self):
        self.become_admin()
        zone = factory.make_Zone()
        node = factory.make_Node(
            zone=zone, architecture=make_usable_architecture(self))

        response = self.client_put(self.get_node_uri(node), {})

        self.assertEqual(httplib.OK, response.status_code)
        node = reload_object(node)
        self.assertEqual(zone, node.zone)

    def test_PUT_zone_change_requires_admin(self):
        new_zone = factory.make_Zone()
        node = factory.make_Node(
            owner=self.logged_in_user,
            architecture=make_usable_architecture(self))
        old_zone = node.zone

        response = self.client_put(
            self.get_node_uri(node),
            {'zone': new_zone.name})

        # Awkwardly, the request succeeds because for non-admins, "zone" is
        # an unknown parameter.  Unknown parameters are ignored.
        self.assertEqual(httplib.OK, response.status_code)
        # The node's physical zone, however, has not been updated.
        node = reload_object(node)
        self.assertEqual(old_zone, node.zone)

    def test_PUT_sets_disable_ipv4(self):
        original_setting = factory.pick_bool()
        node = factory.make_Node(
            owner=self.logged_in_user,
            architecture=make_usable_architecture(self),
            disable_ipv4=original_setting)
        new_setting = not original_setting

        response = self.client_put(
            self.get_node_uri(node), {'disable_ipv4': new_setting})
        self.assertEqual(httplib.OK, response.status_code)

        node = reload_object(node)
        self.assertEqual(new_setting, node.disable_ipv4)

    def test_PUT_leaves_disable_ipv4_unchanged_by_default(self):
        original_setting = factory.pick_bool()
        node = factory.make_Node(
            owner=self.logged_in_user,
            architecture=make_usable_architecture(self),
            disable_ipv4=original_setting)
        self.assertEqual(original_setting, node.disable_ipv4)

        response = self.client_put(
            self.get_node_uri(node), {'zone': factory.make_Zone()})
        self.assertEqual(httplib.OK, response.status_code)

        node = reload_object(node)
        self.assertEqual(original_setting, node.disable_ipv4)

    def test_DELETE_deletes_node(self):
        # The api allows to delete a Node.
        self.become_admin()
        node = factory.make_Node(owner=self.logged_in_user)
        system_id = node.system_id
        response = self.client.delete(self.get_node_uri(node))

        self.assertEqual(204, response.status_code)
        self.assertItemsEqual([], Node.objects.filter(system_id=system_id))

    def test_DELETE_cannot_delete_allocated_node(self):
        # The api allows to delete a Node.
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED)
        response = self.client.delete(self.get_node_uri(node))

        self.assertEqual(
            (httplib.CONFLICT,
                "Cannot delete node %s: node is in state %s." % (
                    node.system_id,
                    NODE_STATUS_CHOICES_DICT[NODE_STATUS.ALLOCATED])),
            (response.status_code, response.content))

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


class TestStickyIP(APITestCase):
    """Tests for /api/1.0/nodes/<node>/?op=claim_sticky_ip_address"""

    def get_node_uri(self, node):
        """Get the API URI for `node`."""
        return reverse('node_handler', args=[node.system_id])

    def test_claim_sticky_ip_address_disallows_non_admin(self):
        node = factory.make_Node()
        response = self.client.post(
            self.get_node_uri(node), {'op': 'claim_sticky_ip_address'})
        self.assertEqual(
            httplib.FORBIDDEN, response.status_code, response.content)

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

    def test_claim_sticky_ip_address_returns_existing_if_already_exists(self):
        self.become_admin()
        node = factory.make_node_with_mac_attached_to_nodegroupinterface()
        [existing_ip] = node.get_primary_mac().claim_static_ips(
            alloc_type=IPADDRESS_TYPE.STICKY)
        response = self.client.post(
            self.get_node_uri(node), {'op': 'claim_sticky_ip_address'})
        self.assertEqual(httplib.OK, response.status_code, response.content)
        parsed_node = json.loads(response.content)
        [returned_ip] = parsed_node["ip_addresses"]
        self.assertEqual(
            (existing_ip.ip, IPADDRESS_TYPE.STICKY),
            (returned_ip, existing_ip.alloc_type)
            )

    def test_claim_sticky_ip_address_rtns_error_if_clashing_type_exists(self):
        self.become_admin()
        node = factory.make_node_with_mac_attached_to_nodegroupinterface()
        random_alloc_type = factory.pick_enum(
            IPADDRESS_TYPE,
            but_not=[IPADDRESS_TYPE.STICKY, IPADDRESS_TYPE.USER_RESERVED])
        node.get_primary_mac().claim_static_ips(alloc_type=random_alloc_type)
        response = self.client.post(
            self.get_node_uri(node), {'op': 'claim_sticky_ip_address'})
        self.assertEqual(
            httplib.CONFLICT, response.status_code,
            response.content)

    def test_claim_sticky_ip_address_claims_sticky_ip_address(self):
        self.become_admin()
        node = factory.make_node_with_mac_attached_to_nodegroupinterface()
        response = self.client.post(
            self.get_node_uri(node), {'op': 'claim_sticky_ip_address'})
        self.assertEqual(httplib.OK, response.status_code, response.content)
        parsed_node = json.loads(response.content)
        [returned_ip] = parsed_node["ip_addresses"]
        [given_ip] = StaticIPAddress.objects.all()
        self.assertEqual(
            (given_ip.ip, IPADDRESS_TYPE.STICKY),
            (returned_ip, given_ip.alloc_type)
            )

    def test_claim_sticky_ip_address_allows_macaddress_parameter(self):
        self.become_admin()
        node = factory.make_node_with_mac_attached_to_nodegroupinterface()
        ngi = factory.make_NodeGroupInterface(nodegroup=node.nodegroup)
        second_mac = factory.make_MACAddress(node=node, cluster_interface=ngi)

        response = self.client.post(
            self.get_node_uri(node),
            {
                'op': 'claim_sticky_ip_address',
                'mac_address': second_mac.mac_address.get_raw(),
            })
        self.assertEqual(httplib.OK, response.status_code, response.content)
        [observed_static_ip] = StaticIPAddress.objects.all()
        [observed_mac] = observed_static_ip.macaddress_set.all()
        self.assertEqual(second_mac, observed_mac)

    def test_claim_sticky_ip_address_catches_bad_mac_address_parameter(self):
        self.become_admin()
        node = factory.make_node_with_mac_attached_to_nodegroupinterface()
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
        node = factory.make_node_with_mac_attached_to_nodegroupinterface()
        ngi = node.get_primary_mac().cluster_interface
        requested_address = ngi.static_ip_range_low

        response = self.client.post(
            self.get_node_uri(node),
            {
                'op': 'claim_sticky_ip_address',
                'requested_address': requested_address,
            })
        self.assertEqual(httplib.OK, response.status_code, response.content)
        [observed_static_ip] = StaticIPAddress.objects.all()
        self.assertEqual(observed_static_ip.ip, requested_address)

    def test_claim_sticky_ip_address_detects_out_of_range_requested_ip(self):
        self.become_admin()
        node = factory.make_node_with_mac_attached_to_nodegroupinterface()
        ngi = node.get_primary_mac().cluster_interface
        requested_address = IPAddress(ngi.static_ip_range_low) - 1

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
        node = factory.make_node_with_mac_attached_to_nodegroupinterface()
        ngi = node.get_primary_mac().cluster_interface
        other_node = factory.make_Node(mac=True, nodegroup=ngi.nodegroup)
        other_mac = other_node.get_primary_mac()
        other_mac.cluster_interface = ngi
        other_mac.save()

        # Allocate an IP to one of the nodes.
        requested_address = IPAddress(ngi.static_ip_range_low) + 1
        requested_address = requested_address.format()
        other_node.get_primary_mac().claim_static_ips(
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
        node = factory.make_Node(
            status=NODE_STATUS.COMMISSIONING, owner=self.logged_in_user)
        error_description = factory.make_name('error-description')
        response = self.client.post(
            self.get_node_uri(node),
            {'op': 'mark_broken', 'error_description': error_description})
        self.assertEqual(httplib.OK, response.status_code)
        node = reload_object(node)
        self.assertEqual(
            (NODE_STATUS.BROKEN, error_description),
            (node.status, node.error_description)
        )

    def test_mark_broken_requires_ownership(self):
        node = factory.make_Node(status=NODE_STATUS.COMMISSIONING)
        response = self.client.post(
            self.get_node_uri(node), {'op': 'mark_broken'})
        self.assertEqual(httplib.FORBIDDEN, response.status_code)


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


class TestAbortOperation(APITestCase):
    """Tests for /api/1.0/nodes/<node>/?op=abort_operation"""

    def get_node_uri(self, node):
        """Get the API URI for `node`."""
        return reverse('node_handler', args=[node.system_id])

    def test_abort_operation_changes_state(self):
        node = factory.make_Node(
            status=NODE_STATUS.DISK_ERASING, owner=self.logged_in_user)
        stop_nodes = self.patch_autospec(Node.objects, "stop_nodes")
        stop_nodes.return_value = [node]
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
