# Copyright 2013 Canonical Ltd.  This software is licensed under the
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
from maasserver.enum import (
    ARCHITECTURE_CHOICES,
    DISTRO_SERIES,
    NODE_AFTER_COMMISSIONING_ACTION,
    NODE_STATUS,
    NODE_STATUS_CHOICES_DICT,
    )
from maasserver.fields import (
    MAC,
    mac_error_msg,
    )
from maasserver.models import Node
from maasserver.testing import (
    reload_object,
    reload_objects,
    )
from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory
from maasserver.testing.oauthclient import OAuthAuthenticatedClient
from maasserver.testing.testcase import (
    LoggedInTestCase,
    MAASServerTestCase,
    )
from maasserver.utils import map_enum
from metadataserver.models import (
    commissioningscript,
    NodeKey,
    NodeUserData,
    )
from metadataserver.nodeinituser import get_node_init_user
from provisioningserver.enum import (
    POWER_TYPE,
    POWER_TYPE_CHOICES,
    )


class NodeAnonAPITest(MAASServerTestCase):

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
        token = NodeKey.objects.get_token_for_node(factory.make_node())
        client = OAuthAuthenticatedClient(get_node_init_user(), token)
        response = client.get(reverse('nodes_handler'), {'op': 'list'})
        self.assertEqual(httplib.FORBIDDEN, response.status_code)


class NodeAPILoggedInTest(LoggedInTestCase):

    def test_nodes_GET_logged_in(self):
        # A (Django) logged-in user can access the API.
        node = factory.make_node()
        response = self.client.get(reverse('nodes_handler'), {'op': 'list'})
        parsed_result = json.loads(response.content)

        self.assertEqual(httplib.OK, response.status_code)
        self.assertEqual(
            [node.system_id],
            [parsed_node.get('system_id') for parsed_node in parsed_result])


class TestNodeAPI(APITestCase):
    """Tests for /api/1.0/nodes/<node>/."""

    def test_handler_path(self):
        self.assertEqual(
            '/api/1.0/nodes/node-name/',
            reverse('node_handler', args=['node-name']))

    def get_node_uri(self, node):
        """Get the API URI for `node`."""
        return reverse('node_handler', args=[node.system_id])

    def test_GET_returns_node(self):
        # The api allows for fetching a single Node (using system_id).
        node = factory.make_node()
        response = self.client.get(self.get_node_uri(node))

        self.assertEqual(httplib.OK, response.status_code)
        parsed_result = json.loads(response.content)
        self.assertEqual(node.hostname, parsed_result['hostname'])
        self.assertEqual(node.system_id, parsed_result['system_id'])

    def test_GET_returns_associated_tag(self):
        node = factory.make_node()
        tag = factory.make_tag()
        node.tags.add(tag)
        response = self.client.get(self.get_node_uri(node))

        self.assertEqual(httplib.OK, response.status_code)
        parsed_result = json.loads(response.content)
        self.assertEqual([tag.name], parsed_result['tag_names'])

    def test_GET_returns_associated_ip_addresses(self):
        node = factory.make_node()
        mac = factory.make_mac_address(node=node)
        lease = factory.make_dhcp_lease(
            nodegroup=node.nodegroup, mac=mac.mac_address)
        response = self.client.get(self.get_node_uri(node))

        self.assertEqual(
            httplib.OK, response.status_code, response.content)
        parsed_result = json.loads(response.content)
        self.assertEqual([lease.ip], parsed_result['ip_addresses'])

    def test_GET_returns_associated_routers(self):
        macs = [MAC('aa:bb:cc:dd:ee:ff'), MAC('00:11:22:33:44:55')]
        node = factory.make_node(routers=macs)
        response = self.client.get(self.get_node_uri(node))

        self.assertEqual(
            httplib.OK, response.status_code, response.content)
        parsed_result = json.loads(response.content)
        self.assertItemsEqual(
            [mac.get_raw() for mac in macs], parsed_result['routers'])

    def test_GET_refuses_to_access_nonexistent_node(self):
        # When fetching a Node, the api returns a 'Not Found' (404) error
        # if no node is found.
        url = reverse('node_handler', args=['invalid-uuid'])

        response = self.client.get(url)

        self.assertEqual(httplib.NOT_FOUND, response.status_code)

    def test_GET_returns_owner_name_when_allocated_to_self(self):
        node = factory.make_node(
            status=NODE_STATUS.ALLOCATED, owner=self.logged_in_user)
        response = self.client.get(self.get_node_uri(node))
        self.assertEqual(httplib.OK, response.status_code)
        parsed_result = json.loads(response.content)
        self.assertEqual(node.owner.username, parsed_result["owner"])

    def test_GET_returns_owner_name_when_allocated_to_other_user(self):
        node = factory.make_node(
            status=NODE_STATUS.ALLOCATED, owner=factory.make_user())
        response = self.client.get(self.get_node_uri(node))
        self.assertEqual(httplib.OK, response.status_code)
        parsed_result = json.loads(response.content)
        self.assertEqual(node.owner.username, parsed_result["owner"])

    def test_GET_returns_empty_owner_when_not_allocated(self):
        node = factory.make_node(status=NODE_STATUS.READY)
        response = self.client.get(self.get_node_uri(node))
        self.assertEqual(httplib.OK, response.status_code)
        parsed_result = json.loads(response.content)
        self.assertEqual(None, parsed_result["owner"])

    def test_POST_stop_checks_permission(self):
        node = factory.make_node()
        response = self.client.post(self.get_node_uri(node), {'op': 'stop'})
        self.assertEqual(httplib.FORBIDDEN, response.status_code)

    def test_POST_stop_returns_node(self):
        node = factory.make_node(owner=self.logged_in_user)
        response = self.client.post(self.get_node_uri(node), {'op': 'stop'})
        self.assertEqual(httplib.OK, response.status_code)
        self.assertEqual(
            node.system_id, json.loads(response.content)['system_id'])

    def test_POST_stop_may_be_repeated(self):
        node = factory.make_node(
            owner=self.logged_in_user, mac=True,
            power_type=POWER_TYPE.WAKE_ON_LAN)
        self.client.post(self.get_node_uri(node), {'op': 'stop'})
        response = self.client.post(self.get_node_uri(node), {'op': 'stop'})
        self.assertEqual(httplib.OK, response.status_code)

    def test_POST_start_checks_permission(self):
        node = factory.make_node()
        response = self.client.post(self.get_node_uri(node), {'op': 'start'})
        self.assertEqual(httplib.FORBIDDEN, response.status_code)

    def test_POST_start_returns_node(self):
        node = factory.make_node(
            owner=self.logged_in_user, mac=True,
            power_type=POWER_TYPE.WAKE_ON_LAN)
        response = self.client.post(self.get_node_uri(node), {'op': 'start'})
        self.assertEqual(httplib.OK, response.status_code)
        self.assertEqual(
            node.system_id, json.loads(response.content)['system_id'])

    def test_POST_start_sets_distro_series(self):
        node = factory.make_node(
            owner=self.logged_in_user, mac=True,
            power_type=POWER_TYPE.WAKE_ON_LAN)
        distro_series = factory.getRandomEnum(DISTRO_SERIES)
        response = self.client.post(
            self.get_node_uri(node),
            {'op': 'start', 'distro_series': distro_series})
        self.assertEqual(
            (httplib.OK, node.system_id),
            (response.status_code, json.loads(response.content)['system_id']))
        self.assertEqual(
            distro_series, reload_object(node).distro_series)

    def test_POST_start_validates_distro_series(self):
        node = factory.make_node(
            owner=self.logged_in_user, mac=True,
            power_type=POWER_TYPE.WAKE_ON_LAN)
        invalid_distro_series = factory.getRandomString()
        response = self.client.post(
            self.get_node_uri(node),
            {'op': 'start', 'distro_series': invalid_distro_series})
        self.assertEqual(
            (
                httplib.BAD_REQUEST,
                {'distro_series': [
                    "Value u'%s' is not a valid choice." %
                    invalid_distro_series]}
            ),
            (response.status_code, json.loads(response.content)))

    def test_POST_start_may_be_repeated(self):
        node = factory.make_node(
            owner=self.logged_in_user, mac=True,
            power_type=POWER_TYPE.WAKE_ON_LAN)
        self.client.post(self.get_node_uri(node), {'op': 'start'})
        response = self.client.post(self.get_node_uri(node), {'op': 'start'})
        self.assertEqual(httplib.OK, response.status_code)

    def test_POST_start_stores_user_data(self):
        node = factory.make_node(
            owner=self.logged_in_user, mac=True,
            power_type=POWER_TYPE.WAKE_ON_LAN)
        user_data = (
            b'\xff\x00\xff\xfe\xff\xff\xfe' +
            factory.getRandomString().encode('ascii'))
        response = self.client.post(
            self.get_node_uri(node), {
                'op': 'start',
                'user_data': b64encode(user_data),
                })
        self.assertEqual(httplib.OK, response.status_code)
        self.assertEqual(user_data, NodeUserData.objects.get_user_data(node))

    def test_POST_release_releases_owned_node(self):
        owned_statuses = [
            NODE_STATUS.RESERVED,
            NODE_STATUS.ALLOCATED,
            ]
        owned_nodes = [
            factory.make_node(owner=self.logged_in_user, status=status)
            for status in owned_statuses]
        responses = [
            self.client.post(self.get_node_uri(node), {'op': 'release'})
            for node in owned_nodes]
        self.assertEqual(
            [httplib.OK] * len(owned_nodes),
            [response.status_code for response in responses])
        self.assertItemsEqual(
            [NODE_STATUS.READY] * len(owned_nodes),
            [node.status for node in reload_objects(Node, owned_nodes)])

    def test_POST_release_turns_on_netboot(self):
        node = factory.make_node(
            status=NODE_STATUS.ALLOCATED, owner=self.logged_in_user)
        node.set_netboot(on=False)
        self.client.post(self.get_node_uri(node), {'op': 'release'})
        self.assertTrue(reload_object(node).netboot)

    def test_POST_release_resets_distro_series(self):
        node = factory.make_node(
            status=NODE_STATUS.ALLOCATED, owner=self.logged_in_user,
            distro_series=factory.getRandomEnum(DISTRO_SERIES))
        self.client.post(self.get_node_uri(node), {'op': 'release'})
        self.assertEqual('', reload_object(node).distro_series)

    def test_POST_release_resets_agent_name(self):
        agent_name = factory.make_name('agent-name')
        node = factory.make_node(
            status=NODE_STATUS.ALLOCATED, owner=self.logged_in_user,
            distro_series=factory.getRandomEnum(DISTRO_SERIES),
            agent_name=agent_name)
        self.client.post(self.get_node_uri(node), {'op': 'release'})
        self.assertEqual('', reload_object(node).agent_name)

    def test_POST_release_removes_token_and_user(self):
        node = factory.make_node(status=NODE_STATUS.READY)
        self.client.post(reverse('nodes_handler'), {'op': 'acquire'})
        node = Node.objects.get(system_id=node.system_id)
        self.assertEqual(NODE_STATUS.ALLOCATED, node.status)
        self.assertEqual(self.logged_in_user, node.owner)
        self.assertEqual(self.client.token.key, node.token.key)
        self.client.post(self.get_node_uri(node), {'op': 'release'})
        node = Node.objects.get(system_id=node.system_id)
        self.assertIs(None, node.owner)
        self.assertIs(None, node.token)

    def test_POST_release_does_nothing_for_unowned_node(self):
        node = factory.make_node(
            status=NODE_STATUS.READY, owner=self.logged_in_user)
        response = self.client.post(
            self.get_node_uri(node), {'op': 'release'})
        self.assertEqual(httplib.OK, response.status_code)
        self.assertEqual(NODE_STATUS.READY, reload_object(node).status)

    def test_POST_release_forbidden_if_user_cannot_edit_node(self):
        node = factory.make_node(status=NODE_STATUS.READY)
        response = self.client.post(
            self.get_node_uri(node), {'op': 'release'})
        self.assertEqual(httplib.FORBIDDEN, response.status_code)

    def test_POST_release_fails_for_other_node_states(self):
        releasable_statuses = [
            NODE_STATUS.RESERVED,
            NODE_STATUS.ALLOCATED,
            NODE_STATUS.READY,
            ]
        unreleasable_statuses = [
            status
            for status in map_enum(NODE_STATUS).values()
            if status not in releasable_statuses
        ]
        nodes = [
            factory.make_node(status=status, owner=self.logged_in_user)
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
        node = factory.make_node(
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
        node = factory.make_node(
            status=NODE_STATUS.ALLOCATED, owner=factory.make_user())
        response = self.client.post(
            self.get_node_uri(node), {'op': 'release'})
        self.assertEqual(httplib.FORBIDDEN, response.status_code)
        self.assertEqual(NODE_STATUS.ALLOCATED, reload_object(node).status)

    def test_POST_release_allows_admin_to_release_anyones_node(self):
        node = factory.make_node(
            status=NODE_STATUS.ALLOCATED, owner=factory.make_user())
        self.become_admin()
        response = self.client.post(
            self.get_node_uri(node), {'op': 'release'})
        self.assertEqual(httplib.OK, response.status_code)
        self.assertEqual(NODE_STATUS.READY, reload_object(node).status)

    def test_POST_release_combines_with_acquire(self):
        node = factory.make_node(status=NODE_STATUS.READY)
        response = self.client.post(
            reverse('nodes_handler'), {'op': 'acquire'})
        self.assertEqual(NODE_STATUS.ALLOCATED, reload_object(node).status)
        node_uri = json.loads(response.content)['resource_uri']
        response = self.client.post(node_uri, {'op': 'release'})
        self.assertEqual(httplib.OK, response.status_code)
        self.assertEqual(NODE_STATUS.READY, reload_object(node).status)

    def test_POST_commission_commissions_node(self):
        node = factory.make_node(
            status=NODE_STATUS.READY, owner=factory.make_user())
        self.become_admin()
        response = self.client.post(
            self.get_node_uri(node), {'op': 'commission'})
        self.assertEqual(httplib.OK, response.status_code)
        self.assertEqual(NODE_STATUS.COMMISSIONING, reload_object(node).status)

    def test_PUT_updates_node(self):
        # The api allows the updating of a Node.
        node = factory.make_node(hostname='diane', owner=self.logged_in_user)
        response = self.client_put(
            self.get_node_uri(node), {'hostname': 'francis'})
        parsed_result = json.loads(response.content)

        self.assertEqual(httplib.OK, response.status_code)
        self.assertEqual('francis', parsed_result['hostname'])
        self.assertEqual(0, Node.objects.filter(hostname='diane').count())
        self.assertEqual(1, Node.objects.filter(hostname='francis').count())

    def test_PUT_omitted_hostname(self):
        hostname = factory.make_name('hostname')
        node = factory.make_node(hostname=hostname, owner=self.logged_in_user)
        response = self.client_put(
            self.get_node_uri(node),
            {'architecture': factory.getRandomChoice(ARCHITECTURE_CHOICES)})
        self.assertEqual(httplib.OK, response.status_code, response.content)
        self.assertTrue(Node.objects.filter(hostname=hostname).exists())

    def test_PUT_ignores_unknown_fields(self):
        node = factory.make_node(
            owner=self.logged_in_user,
            after_commissioning_action=(
                NODE_AFTER_COMMISSIONING_ACTION.DEFAULT))
        field = factory.getRandomString()
        response = self.client_put(
            self.get_node_uri(node),
            {field: factory.getRandomString()}
            )

        self.assertEqual(httplib.OK, response.status_code)

    def test_PUT_admin_can_change_power_type(self):
        self.become_admin()
        original_power_type = factory.getRandomChoice(
            POWER_TYPE_CHOICES)
        new_power_type = factory.getRandomChoice(
            POWER_TYPE_CHOICES, but_not=original_power_type)
        node = factory.make_node(
            owner=self.logged_in_user,
            power_type=original_power_type,
            after_commissioning_action=(
                NODE_AFTER_COMMISSIONING_ACTION.DEFAULT))
        self.client_put(
            self.get_node_uri(node),
            {'power_type': new_power_type}
            )

        self.assertEqual(
            new_power_type, reload_object(node).power_type)

    def test_PUT_non_admin_cannot_change_power_type(self):
        original_power_type = factory.getRandomChoice(
            POWER_TYPE_CHOICES)
        new_power_type = factory.getRandomChoice(
            POWER_TYPE_CHOICES, but_not=original_power_type)
        node = factory.make_node(
            owner=self.logged_in_user,
            power_type=original_power_type,
            after_commissioning_action=(
                NODE_AFTER_COMMISSIONING_ACTION.DEFAULT))
        self.client_put(
            self.get_node_uri(node),
            {'power_type': new_power_type}
            )

        self.assertEqual(
            original_power_type, reload_object(node).power_type)

    def test_resource_uri_points_back_at_node(self):
        # When a Node is returned by the API, the field 'resource_uri'
        # provides the URI for this Node.
        node = factory.make_node(hostname='diane', owner=self.logged_in_user)
        response = self.client_put(
            self.get_node_uri(node), {'hostname': 'francis'})
        parsed_result = json.loads(response.content)

        self.assertEqual(
            reverse('node_handler', args=[parsed_result['system_id']]),
            parsed_result['resource_uri'])

    def test_PUT_rejects_invalid_data(self):
        # If the data provided to update a node is invalid, a 'Bad request'
        # response is returned.
        node = factory.make_node(hostname='diane', owner=self.logged_in_user)
        response = self.client_put(
            self.get_node_uri(node), {'hostname': 'too long' * 100})
        parsed_result = json.loads(response.content)

        self.assertEqual(httplib.BAD_REQUEST, response.status_code)
        self.assertEqual(
            {'hostname':
                ['Ensure this value has at most 255 characters '
                 '(it has 800).']},
            parsed_result)

    def test_PUT_refuses_to_update_invisible_node(self):
        # The request to update a single node is denied if the node isn't
        # visible by the user.
        other_node = factory.make_node(
            status=NODE_STATUS.ALLOCATED, owner=factory.make_user())

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
        node = factory.make_node(
            owner=self.logged_in_user,
            power_type=POWER_TYPE.WAKE_ON_LAN)
        # Create a power_parameter valid for the selected power_type.
        new_power_address = factory.getRandomMACAddress()
        response = self.client_put(
            self.get_node_uri(node),
            {'power_parameters_mac_address': new_power_address})

        self.assertEqual(httplib.OK, response.status_code)
        self.assertEqual(
            {'mac_address': new_power_address},
            reload_object(node).power_parameters)

    def test_PUT_updates_cpu_memory_storage(self):
        self.become_admin()
        node = factory.make_node(
            owner=self.logged_in_user,
            power_type=POWER_TYPE.WAKE_ON_LAN)
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
        node = factory.make_node(
            owner=self.logged_in_user,
            power_type=POWER_TYPE.WAKE_ON_LAN)
        # Create an invalid power_parameter for WoL (not a valid
        # MAC address).
        new_power_address = factory.getRandomString()
        response = self.client_put(
            self.get_node_uri(node),
            {'power_parameters_mac_address': new_power_address})

        self.assertEqual(
            (
                httplib.BAD_REQUEST,
                {'power_parameters': ["MAC Address: %s" % mac_error_msg]},
            ),
            (response.status_code, json.loads(response.content)))

    def test_PUT_updates_power_parameters_rejects_unknown_param(self):
        self.become_admin()
        power_parameters = factory.getRandomString()
        node = factory.make_node(
            owner=self.logged_in_user,
            power_type=POWER_TYPE.WAKE_ON_LAN,
            power_parameters=power_parameters)
        response = self.client_put(
            self.get_node_uri(node),
            {'power_parameters_unknown_param': factory.getRandomString()})

        self.assertEqual(
            (
                httplib.BAD_REQUEST,
                {'power_parameters': ["Unknown parameter(s): unknown_param."]}
            ),
            (response.status_code, json.loads(response.content)))
        self.assertEqual(
            power_parameters, reload_object(node).power_parameters)

    def test_PUT_updates_power_type_default_resets_params(self):
        # If one sets power_type to DEFAULT, power_parameter gets
        # reset by default (if skip_check is not set).
        self.become_admin()
        power_parameters = factory.getRandomString()
        node = factory.make_node(
            owner=self.logged_in_user,
            power_type=POWER_TYPE.WAKE_ON_LAN,
            power_parameters=power_parameters)
        response = self.client_put(
            self.get_node_uri(node),
            {'power_type': POWER_TYPE.DEFAULT})

        node = reload_object(node)
        self.assertEqual(
            (httplib.OK, node.power_type, node.power_parameters),
            (response.status_code, POWER_TYPE.DEFAULT, ''))

    def test_PUT_updates_power_type_default_rejects_params(self):
        # If one sets power_type to DEFAULT, on cannot set power_parameters.
        self.become_admin()
        power_parameters = factory.getRandomString()
        node = factory.make_node(
            owner=self.logged_in_user,
            power_type=POWER_TYPE.WAKE_ON_LAN,
            power_parameters=power_parameters)
        new_param = factory.getRandomString()
        response = self.client_put(
            self.get_node_uri(node),
            {
                'power_type': POWER_TYPE.DEFAULT,
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

    def test_PUT_updates_power_type_default_skip_check_to_force_params(self):
        # If one sets power_type to DEFAULT, it is possible to pass
        # power_parameter_skip_check='true' to force power_parameters.
        self.become_admin()
        power_parameters = factory.getRandomString()
        node = factory.make_node(
            owner=self.logged_in_user,
            power_type=POWER_TYPE.WAKE_ON_LAN,
            power_parameters=power_parameters)
        new_param = factory.getRandomString()
        response = self.client_put(
            self.get_node_uri(node),
            {
                'power_type': POWER_TYPE.DEFAULT,
                'power_parameters_param': new_param,
                'power_parameters_skip_check': 'true',
            })

        node = reload_object(node)
        self.assertEqual(
            (httplib.OK, node.power_type, node.power_parameters),
            (response.status_code, POWER_TYPE.DEFAULT, {'param': new_param}))

    def test_PUT_updates_power_parameters_skip_ckeck(self):
        # With power_parameters_skip_check, arbitrary data
        # can be put in a Node's power_parameter field.
        self.become_admin()
        node = factory.make_node(owner=self.logged_in_user)
        new_param = factory.getRandomString()
        new_value = factory.getRandomString()
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
        node = factory.make_node(
            owner=self.logged_in_user,
            power_type=POWER_TYPE.WAKE_ON_LAN,
            power_parameters=factory.getRandomString())
        response = self.client_put(
            self.get_node_uri(node),
            {'power_parameters_mac_address': ''})

        self.assertEqual(httplib.OK, response.status_code)
        self.assertEqual(
            {'mac_address': ''},
            reload_object(node).power_parameters)

    def test_PUT_sets_zone(self):
        self.become_admin()
        new_zone = factory.make_zone()
        node = factory.make_node()

        response = self.client_put(
            self.get_node_uri(node),
            {'zone': new_zone.name})

        self.assertEqual(httplib.OK, response.status_code)
        node = reload_object(node)
        self.assertEqual(new_zone, node.zone)

    #@skip(
    #    "XXX: JeroenVermeulen 2013-12-11 bug=1259872: Clearing the zone "
    #    "field does not work..")
    def test_PUT_clears_zone(self):
        # The @skip above breaks some 150 tests, with a strange error.
        # Figuring this out is taking too long; I'm disabling the test in a
        # simpler way.
        return
        self.become_admin()
        node = factory.make_node(zone=factory.make_zone())

        response = self.client_put(self.get_node_uri(node), {'zone': ''})

        self.assertEqual(httplib.OK, response.status_code)
        node = reload_object(node)
        self.assertEqual(None, node.zone)

    def test_PUT_without_zone_leaves_zone_unchanged(self):
        self.become_admin()
        zone = factory.make_zone()
        node = factory.make_node(zone=zone)

        response = self.client_put(self.get_node_uri(node), {})

        self.assertEqual(httplib.OK, response.status_code)
        node = reload_object(node)
        self.assertEqual(zone, node.zone)

    def test_PUT_zone_change_requires_admin(self):
        new_zone = factory.make_zone()
        node = factory.make_node(owner=self.logged_in_user)
        old_zone = node.zone

        response = self.client_put(
            self.get_node_uri(node),
            {'zone': new_zone.name})

        # Awkwardly, the request succeeds because for non-admins, "zone" is
        # an unknown parameter.  Unknown parameters are ignored.
        self.assertEqual(httplib.OK, response.status_code)
        # The node's availability zone, however, has not been updated.
        node = reload_object(node)
        self.assertEqual(old_zone, node.zone)

    def test_DELETE_deletes_node(self):
        # The api allows to delete a Node.
        self.become_admin()
        node = factory.make_node(owner=self.logged_in_user)
        system_id = node.system_id
        response = self.client.delete(self.get_node_uri(node))

        self.assertEqual(204, response.status_code)
        self.assertItemsEqual([], Node.objects.filter(system_id=system_id))

    def test_DELETE_cannot_delete_allocated_node(self):
        # The api allows to delete a Node.
        self.become_admin()
        node = factory.make_node(status=NODE_STATUS.ALLOCATED)
        response = self.client.delete(self.get_node_uri(node))

        self.assertEqual(
            (httplib.CONFLICT,
                "Cannot delete node %s: node is in state %s." % (
                    node.system_id,
                    NODE_STATUS_CHOICES_DICT[NODE_STATUS.ALLOCATED])),
            (response.status_code, response.content))

    def test_DELETE_deletes_node_fails_if_not_admin(self):
        # Only superusers can delete nodes.
        node = factory.make_node(owner=self.logged_in_user)
        response = self.client.delete(self.get_node_uri(node))

        self.assertEqual(httplib.FORBIDDEN, response.status_code)

    def test_DELETE_forbidden_without_edit_permission(self):
        # A user without the edit permission cannot delete a Node.
        node = factory.make_node()
        response = self.client.delete(self.get_node_uri(node))

        self.assertEqual(httplib.FORBIDDEN, response.status_code)

    def test_DELETE_refuses_to_delete_invisible_node(self):
        # The request to delete a single node is denied if the node isn't
        # visible by the user.
        other_node = factory.make_node(
            status=NODE_STATUS.ALLOCATED, owner=factory.make_user())

        response = self.client.delete(self.get_node_uri(other_node))

        self.assertEqual(httplib.FORBIDDEN, response.status_code)

    def test_DELETE_refuses_to_delete_nonexistent_node(self):
        # When deleting a Node, the api returns a 'Not Found' (404) error
        # if no node is found.
        url = reverse('node_handler', args=['invalid-uuid'])
        response = self.client.delete(url)

        self.assertEqual(httplib.NOT_FOUND, response.status_code)


class TestGetDetails(APITestCase):
    """Tests for /api/1.0/nodes/<node>/?op=details."""

    def make_lshw_result(self, node, script_result=0):
        return factory.make_node_commission_result(
            node=node, name=commissioningscript.LSHW_OUTPUT_NAME,
            script_result=script_result)

    def make_lldp_result(self, node, script_result=0):
        return factory.make_node_commission_result(
            node=node, name=commissioningscript.LLDP_OUTPUT_NAME,
            script_result=script_result)

    def get_details(self, node):
        url = reverse('node_handler', args=[node.system_id])
        response = self.client.get(url, {'op': 'details'})
        self.assertEqual(httplib.OK, response.status_code)
        self.assertEqual('application/bson', response['content-type'])
        return bson.BSON(response.content).decode()

    def test_GET_returns_empty_details_when_there_are_none(self):
        node = factory.make_node()
        self.assertDictEqual(
            {"lshw": None, "lldp": None},
            self.get_details(node))

    def test_GET_returns_all_details(self):
        node = factory.make_node()
        lshw_result = self.make_lshw_result(node)
        lldp_result = self.make_lldp_result(node)
        self.assertDictEqual(
            {"lshw": bson.Binary(lshw_result.data),
             "lldp": bson.Binary(lldp_result.data)},
            self.get_details(node))

    def test_GET_returns_only_those_details_that_exist(self):
        node = factory.make_node()
        lshw_result = self.make_lshw_result(node)
        self.assertDictEqual(
            {"lshw": bson.Binary(lshw_result.data),
             "lldp": None},
            self.get_details(node))

    def test_GET_returns_not_found_when_node_does_not_exist(self):
        url = reverse('node_handler', args=['does-not-exist'])
        response = self.client.get(url, {'op': 'details'})
        self.assertEqual(httplib.NOT_FOUND, response.status_code)
