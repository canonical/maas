# Copyright 2012, 2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test maasserver API."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from base64 import b64encode
from cStringIO import StringIO
from functools import partial
import httplib
from itertools import izip
import json
import random
import sys

from apiclient.maas_client import MAASClient
from django.conf import settings
from django.core.urlresolvers import reverse
from fixtures import EnvironmentVariableFixture
from maasserver import api
from maasserver.api import (
    DISPLAYED_NODEGROUPINTERFACE_FIELDS,
    store_node_power_parameters,
    )
from maasserver.enum import (
    ARCHITECTURE,
    ARCHITECTURE_CHOICES,
    COMPONENT,
    DISTRO_SERIES,
    NODE_AFTER_COMMISSIONING_ACTION,
    NODE_STATUS,
    NODE_STATUS_CHOICES_DICT,
    NODEGROUP_STATUS,
    NODEGROUPINTERFACE_MANAGEMENT,
    )
from maasserver.exceptions import MAASAPIBadRequest
from maasserver.fields import (
    MAC,
    mac_error_msg,
    )
from maasserver.forms_settings import INVALID_SETTING_MSG_TEMPLATE
from maasserver.models import (
    BootImage,
    Config,
    Node,
    NodeGroup,
    NodeGroupInterface,
    SSHKey,
    )
from maasserver.models.user import (
    create_auth_token,
    get_auth_tokens,
    )
from maasserver.refresh_worker import refresh_worker
from maasserver.testing import (
    get_data,
    reload_object,
    reload_objects,
    )
from maasserver.testing.api import (
    APITestCase,
    APIv10TestMixin,
    log_in_as_normal_user,
    make_worker_client,
    MultipleUsersScenarios,
    )
from maasserver.testing.factory import factory
from maasserver.testing.oauthclient import OAuthAuthenticatedClient
from maasserver.testing.testcase import (
    LoggedInTestCase,
    MAASServerTestCase,
    )
from maasserver.tests.test_forms import make_interface_settings
from maasserver.utils import map_enum
from maasserver.utils.orm import get_one
from maastesting.celery import CeleryFixture
from maastesting.djangotestcase import TransactionTestCase
from metadataserver.models import (
    NodeKey,
    NodeUserData,
    )
from metadataserver.nodeinituser import get_node_init_user
from mock import (
    ANY,
    Mock,
    )
from provisioningserver import (
    boot_images,
    tasks,
    )
from provisioningserver.enum import (
    POWER_TYPE,
    POWER_TYPE_CHOICES,
    )
from provisioningserver.pxe import tftppath
from provisioningserver.testing.boot_images import make_boot_image_params
from testresources import FixtureResource
from testtools.matchers import (
    Contains,
    Equals,
    MatchesListwise,
    MatchesStructure,
    )


class TestAuthentication(APIv10TestMixin, MAASServerTestCase):
    """Tests for `maasserver.api_auth`."""

    def test_invalid_oauth_request(self):
        # An OAuth-signed request that does not validate is an error.
        user = factory.make_user()
        client = OAuthAuthenticatedClient(user)
        get_auth_tokens(user).delete()  # Delete the user's API keys.
        response = client.post(self.get_uri('nodes/'), {'op': 'start'})
        observed = response.status_code, response.content
        expected = (
            Equals(httplib.UNAUTHORIZED),
            Contains("Invalid access token:"),
            )
        self.assertThat(observed, MatchesListwise(expected))


class TestStoreNodeParameters(MAASServerTestCase):
    """Tests for `store_node_power_parameters`."""

    def setUp(self):
        super(TestStoreNodeParameters, self).setUp()
        self.node = factory.make_node()
        self.save = self.patch(self.node, "save")
        self.request = Mock()

    def test_power_type_not_given(self):
        # When power_type is not specified, nothing happens.
        self.request.POST = {}
        store_node_power_parameters(self.node, self.request)
        self.assertEqual(POWER_TYPE.DEFAULT, self.node.power_type)
        self.assertEqual("", self.node.power_parameters)
        self.save.assert_has_calls([])

    def test_power_type_set_but_no_parameters(self):
        # When power_type is valid, it is set. However, if power_parameters is
        # not specified, the node's power_parameters is left alone, and the
        # node is saved.
        power_type = factory.getRandomChoice(POWER_TYPE_CHOICES)
        self.request.POST = {"power_type": power_type}
        store_node_power_parameters(self.node, self.request)
        self.assertEqual(power_type, self.node.power_type)
        self.assertEqual("", self.node.power_parameters)
        self.save.assert_called_once_with()

    def test_power_type_set_with_parameters(self):
        # When power_type is valid, and power_parameters is valid JSON, both
        # fields are set on the node, and the node is saved.
        power_type = factory.getRandomChoice(POWER_TYPE_CHOICES)
        power_parameters = {"foo": [1, 2, 3]}
        self.request.POST = {
            "power_type": power_type,
            "power_parameters": json.dumps(power_parameters),
            }
        store_node_power_parameters(self.node, self.request)
        self.assertEqual(power_type, self.node.power_type)
        self.assertEqual(power_parameters, self.node.power_parameters)
        self.save.assert_called_once_with()

    def test_power_type_set_with_invalid_parameters(self):
        # When power_type is valid, but power_parameters is invalid JSON, the
        # node is not saved, and an exception is raised.
        power_type = factory.getRandomChoice(POWER_TYPE_CHOICES)
        self.request.POST = {
            "power_type": power_type,
            "power_parameters": "Not JSON.",
            }
        self.assertRaises(
            MAASAPIBadRequest, store_node_power_parameters,
            self.node, self.request)
        self.save.assert_has_calls([])

    def test_invalid_power_type(self):
        # When power_type is invalid, the node is not saved, and an exception
        # is raised.
        self.request.POST = {"power_type": factory.make_name("bogus")}
        self.assertRaises(
            MAASAPIBadRequest, store_node_power_parameters,
            self.node, self.request)
        self.save.assert_has_calls([])


class NodeHostnameTest(APIv10TestMixin, MultipleUsersScenarios,
                       MAASServerTestCase):

    scenarios = [
        ('user', dict(userfactory=factory.make_user)),
        ('admin', dict(userfactory=factory.make_admin)),
        ]

    def test_GET_list_returns_fqdn_with_domain_name_from_cluster(self):
        # If DNS management is enabled, the domain part of a hostname
        # is replaced by the domain name defined on the cluster.
        hostname_without_domain = factory.make_name('hostname')
        hostname_with_domain = '%s.%s' % (
            hostname_without_domain, factory.getRandomString())
        domain = factory.make_name('domain')
        nodegroup = factory.make_node_group(
            status=NODEGROUP_STATUS.ACCEPTED,
            name=domain,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS)
        node = factory.make_node(
            hostname=hostname_with_domain, nodegroup=nodegroup)
        expected_hostname = '%s.%s' % (hostname_without_domain, domain)
        response = self.client.get(self.get_uri('nodes/'), {'op': 'list'})
        self.assertEqual(httplib.OK, response.status_code, response.content)
        parsed_result = json.loads(response.content)
        self.assertItemsEqual(
            [expected_hostname],
            [node.get('hostname') for node in parsed_result])


class AnonymousIsRegisteredAPITest(APIv10TestMixin, MAASServerTestCase):

    def test_is_registered_returns_True_if_node_registered(self):
        mac_address = factory.getRandomMACAddress()
        factory.make_mac_address(mac_address)
        response = self.client.get(
            self.get_uri('nodes/'),
            {'op': 'is_registered', 'mac_address': mac_address})
        self.assertEqual(
            (httplib.OK, "true"),
            (response.status_code, response.content))

    def test_is_registered_returns_False_if_mac_registered_node_retired(self):
        mac_address = factory.getRandomMACAddress()
        mac = factory.make_mac_address(mac_address)
        mac.node.status = NODE_STATUS.RETIRED
        mac.node.save()
        response = self.client.get(
            self.get_uri('nodes/'),
            {'op': 'is_registered', 'mac_address': mac_address})
        self.assertEqual(
            (httplib.OK, "false"),
            (response.status_code, response.content))

    def test_is_registered_normalizes_mac_address(self):
        # These two non-normalized MAC addresses are the same.
        non_normalized_mac_address = 'AA-bb-cc-dd-ee-ff'
        non_normalized_mac_address2 = 'aabbccddeeff'
        factory.make_mac_address(non_normalized_mac_address)
        response = self.client.get(
            self.get_uri('nodes/'),
            {
                'op': 'is_registered',
                'mac_address': non_normalized_mac_address2
            })
        self.assertEqual(
            (httplib.OK, "true"),
            (response.status_code, response.content))

    def test_is_registered_returns_False_if_node_not_registered(self):
        mac_address = factory.getRandomMACAddress()
        response = self.client.get(
            self.get_uri('nodes/'),
            {'op': 'is_registered', 'mac_address': mac_address})
        self.assertEqual(
            (httplib.OK, "false"),
            (response.status_code, response.content))


class NodeAnonAPITest(APIv10TestMixin, MAASServerTestCase):

    def test_anon_nodes_GET(self):
        # Anonymous requests to the API without a specified operation
        # get a "Bad Request" response.
        response = self.client.get(self.get_uri('nodes/'))

        self.assertEqual(httplib.BAD_REQUEST, response.status_code)

    def test_anon_api_doc(self):
        # The documentation is accessible to anon users.
        self.patch(sys, "stderr", StringIO())
        response = self.client.get(self.get_uri('doc/'))
        self.assertEqual(httplib.OK, response.status_code)
        # No error or warning are emitted by docutils.
        self.assertEqual("", sys.stderr.getvalue())

    def test_node_init_user_cannot_access(self):
        token = NodeKey.objects.get_token_for_node(factory.make_node())
        client = OAuthAuthenticatedClient(get_node_init_user(), token)
        response = client.get(self.get_uri('nodes/'), {'op': 'list'})
        self.assertEqual(httplib.FORBIDDEN, response.status_code)


def extract_system_ids(parsed_result):
    """List the system_ids of the nodes in `parsed_result`."""
    return [node.get('system_id') for node in parsed_result]


class NodeAPILoggedInTest(APIv10TestMixin, LoggedInTestCase):

    def test_nodes_GET_logged_in(self):
        # A (Django) logged-in user can access the API.
        node = factory.make_node()
        response = self.client.get(self.get_uri('nodes/'), {'op': 'list'})
        parsed_result = json.loads(response.content)

        self.assertEqual(httplib.OK, response.status_code)
        self.assertEqual([node.system_id], extract_system_ids(parsed_result))


class TestNodeAPI(APITestCase):
    """Tests for /api/1.0/nodes/<node>/."""

    def get_node_uri(self, node):
        """Get the API URI for `node`."""
        return self.get_uri('nodes/%s/') % node.system_id

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
        response = self.client.get(self.get_uri('nodes/invalid-uuid/'))

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
                {'distro_series': ["Value u'%s' is not a valid choice." %
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

    def test_POST_release_removes_token_and_user(self):
        node = factory.make_node(status=NODE_STATUS.READY)
        self.client.post(self.get_uri('nodes/'), {'op': 'acquire'})
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
                if status not in releasable_statuses]
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
            self.get_uri('nodes/'), {'op': 'acquire'})
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
            self.get_uri('nodes/%s/') % (parsed_result['system_id']),
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
        response = self.client_put(self.get_uri('nodes/no-node-here/'))

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
        response = self.client.delete(self.get_uri('nodes/no-node-here/'))

        self.assertEqual(httplib.NOT_FOUND, response.status_code)


class TestNodesAPI(APITestCase):
    """Tests for /api/1.0/nodes/."""

    def test_POST_new_creates_node(self):
        # The API allows a non-admin logged-in user to create a Node.
        architecture = factory.getRandomChoice(ARCHITECTURE_CHOICES)
        response = self.client.post(
            self.get_uri('nodes/'),
            {
                'op': 'new',
                'hostname': factory.getRandomString(),
                'architecture': architecture,
                'after_commissioning_action':
                    NODE_AFTER_COMMISSIONING_ACTION.DEFAULT,
                'mac_addresses': ['aa:bb:cc:dd:ee:ff', '22:bb:cc:dd:ee:ff'],
            })

        self.assertEqual(httplib.OK, response.status_code)

    def test_POST_new_when_logged_in_creates_node_in_declared_state(self):
        # When a user enlists a node, it goes into the Declared state.
        # This will change once we start doing proper commissioning.
        response = self.client.post(
            self.get_uri('nodes/'),
            {
                'op': 'new',
                'hostname': factory.getRandomString(),
                'architecture': factory.getRandomChoice(ARCHITECTURE_CHOICES),
                'after_commissioning_action':
                    NODE_AFTER_COMMISSIONING_ACTION.DEFAULT,
                'mac_addresses': ['aa:bb:cc:dd:ee:ff'],
            })
        self.assertEqual(httplib.OK, response.status_code)
        system_id = json.loads(response.content)['system_id']
        self.assertEqual(
            NODE_STATUS.DECLARED,
            Node.objects.get(system_id=system_id).status)

    def test_GET_list_lists_nodes(self):
        # The api allows for fetching the list of Nodes.
        node1 = factory.make_node()
        node2 = factory.make_node(
            status=NODE_STATUS.ALLOCATED, owner=self.logged_in_user)
        response = self.client.get(self.get_uri('nodes/'), {'op': 'list'})
        parsed_result = json.loads(response.content)

        self.assertEqual(httplib.OK, response.status_code)
        self.assertItemsEqual(
            [node1.system_id, node2.system_id],
            extract_system_ids(parsed_result))

    def create_nodes(self, nodegroup, nb):
        [factory.make_node(nodegroup=nodegroup, mac=True)
            for i in range(nb)]

    def test_GET_list_nodes_issues_constant_number_of_queries(self):
        nodegroup = factory.make_node_group()
        self.create_nodes(nodegroup, 10)
        num_queries1, response1 = self.getNumQueries(
            self.client.get, self.get_uri('nodes/'), {'op': 'list'})
        self.create_nodes(nodegroup, 10)
        num_queries2, response2 = self.getNumQueries(
            self.client.get, self.get_uri('nodes/'), {'op': 'list'})
        # Make sure the responses are ok as it's not useful to compare the
        # number of queries if they are not.
        self.assertEqual(
            [httplib.OK, httplib.OK, 10, 20],
            [
                response1.status_code,
                response2.status_code,
                len(extract_system_ids(json.loads(response1.content))),
                len(extract_system_ids(json.loads(response2.content))),
            ])
        self.assertEqual(num_queries1, num_queries2)

    def test_GET_list_without_nodes_returns_empty_list(self):
        # If there are no nodes to list, the "list" op still works but
        # returns an empty list.
        response = self.client.get(self.get_uri('nodes/'), {'op': 'list'})
        self.assertItemsEqual([], json.loads(response.content))

    def test_GET_list_orders_by_id(self):
        # Nodes are returned in id order.
        nodes = [factory.make_node() for counter in range(3)]
        response = self.client.get(self.get_uri('nodes/'), {'op': 'list'})
        parsed_result = json.loads(response.content)
        self.assertSequenceEqual(
            [node.system_id for node in nodes],
            extract_system_ids(parsed_result))

    def test_GET_list_with_id_returns_matching_nodes(self):
        # The "list" operation takes optional "id" parameters.  Only
        # nodes with matching ids will be returned.
        ids = [factory.make_node().system_id for counter in range(3)]
        matching_id = ids[0]
        response = self.client.get(self.get_uri('nodes/'), {
            'op': 'list',
            'id': [matching_id],
        })
        parsed_result = json.loads(response.content)
        self.assertItemsEqual(
            [matching_id], extract_system_ids(parsed_result))

    def test_GET_list_with_nonexistent_id_returns_empty_list(self):
        # Trying to list a nonexistent node id returns a list containing
        # no nodes -- even if other (non-matching) nodes exist.
        existing_id = factory.make_node().system_id
        nonexistent_id = existing_id + factory.getRandomString()
        response = self.client.get(self.get_uri('nodes/'), {
            'op': 'list',
            'id': [nonexistent_id],
        })
        self.assertItemsEqual([], json.loads(response.content))

    def test_GET_list_with_ids_orders_by_id(self):
        # Even when ids are passed to "list," nodes are returned in id
        # order, not necessarily in the order of the id arguments.
        ids = [factory.make_node().system_id for counter in range(3)]
        response = self.client.get(self.get_uri('nodes/'), {
            'op': 'list',
            'id': list(reversed(ids)),
        })
        parsed_result = json.loads(response.content)
        self.assertSequenceEqual(ids, extract_system_ids(parsed_result))

    def test_GET_list_with_some_matching_ids_returns_matching_nodes(self):
        # If some nodes match the requested ids and some don't, only the
        # matching ones are returned.
        existing_id = factory.make_node().system_id
        nonexistent_id = existing_id + factory.getRandomString()
        response = self.client.get(self.get_uri('nodes/'), {
            'op': 'list',
            'id': [existing_id, nonexistent_id],
        })
        parsed_result = json.loads(response.content)
        self.assertItemsEqual(
            [existing_id], extract_system_ids(parsed_result))

    def test_GET_list_with_macs_returns_matching_nodes(self):
        # The "list" operation takes optional "mac_address" parameters.  Only
        # nodes with matching MAC addresses will be returned.
        macs = [factory.make_mac_address() for counter in range(3)]
        matching_mac = macs[0].mac_address
        matching_system_id = macs[0].node.system_id
        response = self.client.get(self.get_uri('nodes/'), {
            'op': 'list',
            'mac_address': [matching_mac],
        })
        parsed_result = json.loads(response.content)
        self.assertItemsEqual(
            [matching_system_id], extract_system_ids(parsed_result))

    def test_GET_list_with_invalid_macs_returns_sensible_error(self):
        # If specifying an invalid MAC, make sure the error that's
        # returned is not a crazy stack trace, but something nice to
        # humans.
        bad_mac1 = '00:E0:81:DD:D1:ZZ'  # ZZ is bad.
        bad_mac2 = '00:E0:81:DD:D1:XX'  # XX is bad.
        ok_mac = factory.make_mac_address()
        response = self.client.get(self.get_uri('nodes/'), {
            'op': 'list',
            'mac_address': [bad_mac1, bad_mac2, ok_mac],
            })
        observed = response.status_code, response.content
        expected = (
            Equals(httplib.BAD_REQUEST),
            Contains(
                "Invalid MAC address(es): 00:E0:81:DD:D1:ZZ, "
                "00:E0:81:DD:D1:XX"),
            )
        self.assertThat(observed, MatchesListwise(expected))

    def test_GET_list_allocated_returns_only_allocated_with_user_token(self):
        # If the user's allocated nodes have different session tokens,
        # list_allocated should only return the nodes that have the
        # current request's token on them.
        node_1 = factory.make_node(
            status=NODE_STATUS.ALLOCATED, owner=self.logged_in_user,
            token=get_auth_tokens(self.logged_in_user)[0])
        second_token = create_auth_token(self.logged_in_user)
        factory.make_node(
            owner=self.logged_in_user, status=NODE_STATUS.ALLOCATED,
            token=second_token)

        user_2 = factory.make_user()
        create_auth_token(user_2)
        factory.make_node(
            owner=self.logged_in_user, status=NODE_STATUS.ALLOCATED,
            token=second_token)

        # At this point we have two nodes owned by the same user but
        # allocated with different tokens, and a third node allocated to
        # someone else entirely.  We expect list_allocated to
        # return the node with the same token as the one used in
        # self.client, which is the one we set on node_1 above.

        response = self.client.get(self.get_uri('nodes/'), {
            'op': 'list_allocated'})
        self.assertEqual(httplib.OK, response.status_code)
        parsed_result = json.loads(response.content)
        self.assertItemsEqual(
            [node_1.system_id], extract_system_ids(parsed_result))

    def test_GET_list_allocated_filters_by_id(self):
        # list_allocated takes an optional list of 'id' parameters to
        # filter returned results.
        current_token = get_auth_tokens(self.logged_in_user)[0]
        nodes = []
        for i in range(3):
            nodes.append(factory.make_node(
                status=NODE_STATUS.ALLOCATED,
                owner=self.logged_in_user, token=current_token))

        required_node_ids = [nodes[0].system_id, nodes[1].system_id]
        response = self.client.get(self.get_uri('nodes/'), {
            'op': 'list_allocated',
            'id': required_node_ids,
        })
        self.assertEqual(httplib.OK, response.status_code)
        parsed_result = json.loads(response.content)
        self.assertItemsEqual(
            required_node_ids, extract_system_ids(parsed_result))

    def test_POST_acquire_returns_available_node(self):
        # The "acquire" operation returns an available node.
        available_status = NODE_STATUS.READY
        node = factory.make_node(status=available_status, owner=None)
        response = self.client.post(self.get_uri('nodes/'), {'op': 'acquire'})
        self.assertEqual(httplib.OK, response.status_code)
        parsed_result = json.loads(response.content)
        self.assertEqual(node.system_id, parsed_result['system_id'])

    def test_POST_acquire_allocates_node(self):
        # The "acquire" operation allocates the node it returns.
        available_status = NODE_STATUS.READY
        node = factory.make_node(status=available_status, owner=None)
        self.client.post(self.get_uri('nodes/'), {'op': 'acquire'})
        node = Node.objects.get(system_id=node.system_id)
        self.assertEqual(self.logged_in_user, node.owner)

    def test_POST_acquire_fails_if_no_node_present(self):
        # The "acquire" operation returns a Conflict error if no nodes
        # are available.
        response = self.client.post(self.get_uri('nodes/'), {'op': 'acquire'})
        # Fails with Conflict error: resource can't satisfy request.
        self.assertEqual(httplib.CONFLICT, response.status_code)

    def test_POST_ignores_already_allocated_node(self):
        factory.make_node(
            status=NODE_STATUS.ALLOCATED, owner=factory.make_user())
        response = self.client.post(self.get_uri('nodes/'), {'op': 'acquire'})
        self.assertEqual(httplib.CONFLICT, response.status_code)

    def test_POST_acquire_chooses_candidate_matching_constraint(self):
        # If "acquire" is passed a constraint, it will go for a node
        # matching that constraint even if there's tons of other nodes
        # available.
        # (Creating lots of nodes here to minimize the chances of this
        # passing by accident).
        available_nodes = [
            factory.make_node(status=NODE_STATUS.READY, owner=None)
            for counter in range(20)]
        desired_node = random.choice(available_nodes)
        response = self.client.post(self.get_uri('nodes/'), {
            'op': 'acquire',
            'name': desired_node.hostname,
        })
        self.assertEqual(httplib.OK, response.status_code)
        parsed_result = json.loads(response.content)
        self.assertEqual(desired_node.hostname, parsed_result['hostname'])

    def test_POST_acquire_would_rather_fail_than_disobey_constraint(self):
        # If "acquire" is passed a constraint, it won't return a node
        # that does not meet that constraint.  Even if it means that it
        # can't meet the request.
        factory.make_node(status=NODE_STATUS.READY, owner=None)
        desired_node = factory.make_node(
            status=NODE_STATUS.ALLOCATED, owner=factory.make_user())
        response = self.client.post(self.get_uri('nodes/'), {
            'op': 'acquire',
            'name': desired_node.system_id,
        })
        self.assertEqual(httplib.CONFLICT, response.status_code)

    def test_POST_acquire_ignores_unknown_constraint(self):
        node = factory.make_node(status=NODE_STATUS.READY, owner=None)
        response = self.client.post(self.get_uri('nodes/'), {
            'op': 'acquire',
            factory.getRandomString(): factory.getRandomString(),
        })
        self.assertEqual(httplib.OK, response.status_code)
        parsed_result = json.loads(response.content)
        self.assertEqual(node.system_id, parsed_result['system_id'])

    def test_POST_acquire_allocates_node_by_name(self):
        # Positive test for name constraint.
        # If a name constraint is given, "acquire" attempts to allocate
        # a node of that name.
        node = factory.make_node(status=NODE_STATUS.READY, owner=None)
        response = self.client.post(self.get_uri('nodes/'), {
            'op': 'acquire',
            'name': node.hostname,
        })
        self.assertEqual(httplib.OK, response.status_code)
        self.assertEqual(
            node.hostname, json.loads(response.content)['hostname'])

    def test_POST_acquire_treats_unknown_name_as_resource_conflict(self):
        # A name constraint naming an unknown node produces a resource
        # conflict: most likely the node existed but has changed or
        # disappeared.
        # Certainly it's not a 404, since the resource named in the URL
        # is "nodes/," which does exist.
        factory.make_node(status=NODE_STATUS.READY, owner=None)
        response = self.client.post(self.get_uri('nodes/'), {
            'op': 'acquire',
            'name': factory.getRandomString(),
        })
        self.assertEqual(httplib.CONFLICT, response.status_code)

    def test_POST_acquire_allocates_node_by_arch(self):
        # Asking for a particular arch acquires a node with that arch.
        node = factory.make_node(
            status=NODE_STATUS.READY, architecture=ARCHITECTURE.i386)
        response = self.client.post(self.get_uri('nodes/'), {
            'op': 'acquire',
            'arch': 'i386/generic',
        })
        self.assertEqual(httplib.OK, response.status_code)
        response_json = json.loads(response.content)
        self.assertEqual(node.architecture, response_json['architecture'])

    def test_POST_acquire_treats_unknown_arch_as_bad_request(self):
        # Asking for an unknown arch returns an HTTP "400 Bad Request"
        factory.make_node(status=NODE_STATUS.READY)
        response = self.client.post(self.get_uri('nodes/'), {
            'op': 'acquire',
            'arch': 'sparc',
        })
        self.assertEqual(httplib.BAD_REQUEST, response.status_code)

    def test_POST_acquire_allocates_node_by_cpu(self):
        # Asking for enough cpu acquires a node with at least that.
        node = factory.make_node(status=NODE_STATUS.READY, cpu_count=3)
        response = self.client.post(self.get_uri('nodes/'), {
            'op': 'acquire',
            'cpu_count': 2,
        })
        self.assertResponseCode(httplib.OK, response)
        response_json = json.loads(response.content)
        self.assertEqual(node.system_id, response_json['system_id'])

    def test_POST_acquire_allocates_node_by_float_cpu(self):
        # Asking for a needlessly precise number of cpus works.
        node = factory.make_node(status=NODE_STATUS.READY, cpu_count=1)
        response = self.client.post(self.get_uri('nodes/'), {
            'op': 'acquire',
            'cpu_count': '1.0',
        })
        self.assertResponseCode(httplib.OK, response)
        response_json = json.loads(response.content)
        self.assertEqual(node.system_id, response_json['system_id'])

    def test_POST_acquire_fails_with_invalid_cpu(self):
        # Asking for an invalid amount of cpu returns a bad request.
        factory.make_node(status=NODE_STATUS.READY)
        response = self.client.post(self.get_uri('nodes/'), {
            'op': 'acquire',
            'cpu_count': 'plenty',
        })
        self.assertResponseCode(httplib.BAD_REQUEST, response)

    def test_POST_acquire_allocates_node_by_mem(self):
        # Asking for enough memory acquires a node with at least that.
        node = factory.make_node(status=NODE_STATUS.READY, memory=1024)
        response = self.client.post(self.get_uri('nodes/'), {
            'op': 'acquire',
            'mem': 1024,
        })
        self.assertResponseCode(httplib.OK, response)
        response_json = json.loads(response.content)
        self.assertEqual(node.system_id, response_json['system_id'])

    def test_POST_acquire_fails_with_invalid_mem(self):
        # Asking for an invalid amount of memory returns a bad request.
        factory.make_node(status=NODE_STATUS.READY)
        response = self.client.post(self.get_uri('nodes/'), {
            'op': 'acquire',
            'mem': 'bags',
        })
        self.assertResponseCode(httplib.BAD_REQUEST, response)

    def test_POST_acquire_allocates_node_by_tags(self):
        node = factory.make_node(status=NODE_STATUS.READY)
        node_tag_names = ["fast", "stable", "cute"]
        node.tags = [factory.make_tag(t) for t in node_tag_names]
        # Legacy call using comma-separated tags.
        response = self.client.post(self.get_uri('nodes/'), {
            'op': 'acquire',
            'tags': ['fast', 'stable'],
        })
        self.assertResponseCode(httplib.OK, response)
        response_json = json.loads(response.content)
        self.assertEqual(node_tag_names, response_json['tag_names'])

    def test_POST_acquire_allocates_node_by_tags_comma_separated(self):
        node = factory.make_node(status=NODE_STATUS.READY)
        node_tag_names = ["fast", "stable", "cute"]
        node.tags = [factory.make_tag(t) for t in node_tag_names]
        # Legacy call using comma-separated tags.
        response = self.client.post(self.get_uri('nodes/'), {
            'op': 'acquire',
            'tags': 'fast, stable',
        })
        self.assertResponseCode(httplib.OK, response)
        response_json = json.loads(response.content)
        self.assertEqual(node_tag_names, response_json['tag_names'])

    def test_POST_acquire_allocates_node_by_tags_space_separated(self):
        node = factory.make_node(status=NODE_STATUS.READY)
        node_tag_names = ["fast", "stable", "cute"]
        node.tags = [factory.make_tag(t) for t in node_tag_names]
        # Legacy call using space-separated tags.
        response = self.client.post(self.get_uri('nodes/'), {
            'op': 'acquire',
            'tags': 'fast stable',
        })
        self.assertResponseCode(httplib.OK, response)
        response_json = json.loads(response.content)
        self.assertEqual(node_tag_names, response_json['tag_names'])

    def test_POST_acquire_allocates_node_by_tags_comma_space_separated(self):
        node = factory.make_node(status=NODE_STATUS.READY)
        node_tag_names = ["fast", "stable", "cute"]
        node.tags = [factory.make_tag(t) for t in node_tag_names]
        # Legacy call using comma-and-space-separated tags.
        response = self.client.post(self.get_uri('nodes/'), {
            'op': 'acquire',
            'tags': 'fast, stable cute',
        })
        self.assertResponseCode(httplib.OK, response)
        response_json = json.loads(response.content)
        self.assertEqual(node_tag_names, response_json['tag_names'])

    def test_POST_acquire_allocates_node_by_tags_mixed_input(self):
        node = factory.make_node(status=NODE_STATUS.READY)
        node_tag_names = ["fast", "stable", "cute"]
        node.tags = [factory.make_tag(t) for t in node_tag_names]
        # Mixed call using comma-separated tags in a list.
        response = self.client.post(self.get_uri('nodes/'), {
            'op': 'acquire',
            'tags': ['fast, stable', 'cute'],
        })
        self.assertResponseCode(httplib.OK, response)
        response_json = json.loads(response.content)
        self.assertEqual(node_tag_names, response_json['tag_names'])

    def test_POST_acquire_fails_without_all_tags(self):
        # Asking for particular tags does not acquire if no node has all tags.
        node1 = factory.make_node(status=NODE_STATUS.READY)
        node1.tags = [factory.make_tag(t) for t in ("fast", "stable", "cute")]
        node2 = factory.make_node(status=NODE_STATUS.READY)
        node2.tags = [factory.make_tag("cheap")]
        response = self.client.post(self.get_uri('nodes/'), {
            'op': 'acquire',
            'tags': 'fast, cheap',
        })
        self.assertResponseCode(httplib.CONFLICT, response)

    def test_POST_acquire_fails_with_unknown_tags(self):
        # Asking for a tag that does not exist gives a specific error.
        node = factory.make_node(status=NODE_STATUS.READY)
        node.tags = [factory.make_tag("fast")]
        response = self.client.post(self.get_uri('nodes/'), {
            'op': 'acquire',
            'tags': 'fast, hairy, boo',
        })
        self.assertEqual(httplib.BAD_REQUEST, response.status_code)
        self.assertEqual(
            dict(tags=["No such tag(s): 'hairy', 'boo'."]),
            json.loads(response.content))

    def test_POST_acquire_allocates_node_connected_to_routers(self):
        macs = [factory.make_MAC() for counter in range(3)]
        node = factory.make_node(routers=macs, status=NODE_STATUS.READY)
        factory.make_node(routers=[])

        response = self.client.post(self.get_uri('nodes/'), {
            'op': 'acquire',
            'connected_to': [macs[2].get_raw(), macs[0].get_raw()],
        })

        self.assertResponseCode(httplib.OK, response)
        response_json = json.loads(response.content)
        self.assertEqual(node.system_id, response_json['system_id'])

    def test_POST_acquire_allocates_node_not_connected_to_routers(self):
        macs = [MAC('aa:bb:cc:dd:ee:ff'), MAC('00:11:22:33:44:55')]
        factory.make_node(routers=macs, status=NODE_STATUS.READY)
        factory.make_node(
            routers=[MAC('11:11:11:11:11:11')], status=NODE_STATUS.READY)
        node = factory.make_node(status=NODE_STATUS.READY)

        response = self.client.post(self.get_uri('nodes/'), {
            'op': 'acquire',
            'not_connected_to': ['aa:bb:cc:dd:ee:ff', '11:11:11:11:11:11'],
        })

        self.assertResponseCode(httplib.OK, response)
        response_json = json.loads(response.content)
        self.assertEqual(node.system_id, response_json['system_id'])

    def test_POST_acquire_sets_a_token(self):
        # "acquire" should set the Token being used in the request on
        # the Node that is allocated.
        available_status = NODE_STATUS.READY
        node = factory.make_node(status=available_status, owner=None)
        self.client.post(self.get_uri('nodes/'), {'op': 'acquire'})
        node = Node.objects.get(system_id=node.system_id)
        oauth_key = self.client.token.key
        self.assertEqual(oauth_key, node.token.key)

    def test_POST_accept_gets_node_out_of_declared_state(self):
        # This will change when we add provisioning.  Until then,
        # acceptance gets a node straight to Ready state.
        self.become_admin()
        target_state = NODE_STATUS.COMMISSIONING

        node = factory.make_node(status=NODE_STATUS.DECLARED)
        response = self.client.post(
            self.get_uri('nodes/'),
            {'op': 'accept', 'nodes': [node.system_id]})
        accepted_ids = [
            accepted_node['system_id']
            for accepted_node in json.loads(response.content)]
        self.assertEqual(
            (httplib.OK, [node.system_id]),
            (response.status_code, accepted_ids))
        self.assertEqual(target_state, reload_object(node).status)

    def test_POST_quietly_accepts_empty_set(self):
        response = self.client.post(self.get_uri('nodes/'), {'op': 'accept'})
        self.assertEqual(
            (httplib.OK, "[]"), (response.status_code, response.content))

    def test_POST_accept_rejects_impossible_state_changes(self):
        self.become_admin()
        acceptable_states = set([
            NODE_STATUS.DECLARED,
            NODE_STATUS.COMMISSIONING,
            NODE_STATUS.READY,
            ])
        unacceptable_states = (
            set(map_enum(NODE_STATUS).values()) - acceptable_states)
        nodes = {
            status: factory.make_node(status=status)
            for status in unacceptable_states}
        responses = {
            status: self.client.post(
                self.get_uri('nodes/'), {
                    'op': 'accept',
                    'nodes': [node.system_id],
                    })
            for status, node in nodes.items()}
        # All of these attempts are rejected with Conflict errors.
        self.assertEqual(
            {status: httplib.CONFLICT for status in unacceptable_states},
            {
                status: responses[status].status_code
                for status in unacceptable_states})

        for status, response in responses.items():
            # Each error describes the problem.
            self.assertIn("Cannot accept node enlistment", response.content)
            # Each error names the node it encountered a problem with.
            self.assertIn(nodes[status].system_id, response.content)
            # Each error names the node state that the request conflicted
            # with.
            self.assertIn(NODE_STATUS_CHOICES_DICT[status], response.content)

    def test_POST_accept_fails_if_node_does_not_exist(self):
        self.become_admin()
        # Make sure there is a node, it just isn't the one being accepted
        factory.make_node()
        node_id = factory.getRandomString()
        response = self.client.post(
            self.get_uri('nodes/'), {'op': 'accept', 'nodes': [node_id]})
        self.assertEqual(
            (httplib.BAD_REQUEST, "Unknown node(s): %s." % node_id),
            (response.status_code, response.content))

    def test_POST_accept_accepts_multiple_nodes(self):
        # This will change when we add provisioning.  Until then,
        # acceptance gets a node straight to Ready state.
        self.become_admin()
        target_state = NODE_STATUS.COMMISSIONING

        nodes = [
            factory.make_node(status=NODE_STATUS.DECLARED)
            for counter in range(2)]
        node_ids = [node.system_id for node in nodes]
        response = self.client.post(self.get_uri('nodes/'), {
            'op': 'accept',
            'nodes': node_ids,
            })
        self.assertEqual(httplib.OK, response.status_code)
        self.assertEqual(
            [target_state] * len(nodes),
            [reload_object(node).status for node in nodes])

    def test_POST_accept_returns_actually_accepted_nodes(self):
        self.become_admin()
        acceptable_nodes = [
            factory.make_node(status=NODE_STATUS.DECLARED)
            for counter in range(2)
            ]
        accepted_node = factory.make_node(status=NODE_STATUS.READY)
        nodes = acceptable_nodes + [accepted_node]
        response = self.client.post(self.get_uri('nodes/'), {
            'op': 'accept',
            'nodes': [node.system_id for node in nodes],
            })
        self.assertEqual(httplib.OK, response.status_code)
        accepted_ids = [
            node['system_id'] for node in json.loads(response.content)]
        self.assertItemsEqual(
            [node.system_id for node in acceptable_nodes], accepted_ids)
        self.assertNotIn(accepted_node.system_id, accepted_ids)

    def test_POST_quietly_releases_empty_set(self):
        response = self.client.post(self.get_uri('nodes/'), {'op': 'release'})
        self.assertEqual(
            (httplib.OK, "[]"), (response.status_code, response.content))

    def test_POST_release_rejects_request_from_unauthorized_user(self):
        node = factory.make_node(
            status=NODE_STATUS.ALLOCATED, owner=factory.make_user())
        response = self.client.post(
            self.get_uri('nodes/'), {
                'op': 'release',
                'nodes': [node.system_id],
                })
        self.assertEqual(httplib.FORBIDDEN, response.status_code)
        self.assertEqual(NODE_STATUS.ALLOCATED, reload_object(node).status)

    def test_POST_release_fails_if_nodes_do_not_exist(self):
         # Make sure there is a node, it just isn't among the ones to release
        factory.make_node()
        node_ids = {factory.getRandomString() for i in xrange(5)}
        response = self.client.post(
            self.get_uri('nodes/'), {
                'op': 'release',
                'nodes': node_ids
                })
        # Awkward parsing, but the order may vary and it's not JSON
        s = response.content
        returned_ids = s[s.find(':') + 2:s.rfind('.')].split(', ')
        self.assertEqual(httplib.BAD_REQUEST, response.status_code)
        self.assertIn("Unknown node(s): ", response.content)
        self.assertItemsEqual(node_ids, returned_ids)

    def test_POST_release_forbidden_if_user_cannot_edit_node(self):
        # Create a bunch of nodes, owned by the logged in user
        node_ids = {
            factory.make_node(
                status=NODE_STATUS.ALLOCATED,
                owner=self.logged_in_user).system_id
            for i in xrange(3)
            }
        # And one with no owner
        another_node = factory.make_node(status=NODE_STATUS.RESERVED)
        node_ids.add(another_node.system_id)
        response = self.client.post(
            self.get_uri('nodes/'), {
                'op': 'release',
                'nodes': node_ids
                })
        self.assertEqual(
            (httplib.FORBIDDEN,
                "You don't have the required permission to release the "
                "following node(s): %s." % another_node.system_id),
            (response.status_code, response.content))

    def test_POST_release_rejects_impossible_state_changes(self):
        acceptable_states = {
            NODE_STATUS.ALLOCATED,
            NODE_STATUS.RESERVED,
            NODE_STATUS.READY,
            }
        unacceptable_states = (
            set(map_enum(NODE_STATUS).values()) - acceptable_states)
        owner = self.logged_in_user
        nodes = [
            factory.make_node(status=status, owner=owner)
            for status in unacceptable_states]
        response = self.client.post(
            self.get_uri('nodes/'), {
                'op': 'release',
                'nodes': [node.system_id for node in nodes],
                })
        # Awkward parsing again, because a string is returned, not JSON
        expected = [
            "%s ('%s')" % (node.system_id, node.display_status())
            for node in nodes
            if node.status not in acceptable_states]
        s = response.content
        returned = s[s.rfind(':') + 2:s.rfind('.')].split(', ')
        self.assertEqual(httplib.CONFLICT, response.status_code)
        self.assertIn(
            "Node(s) cannot be released in their current state:",
            response.content)
        self.assertItemsEqual(expected, returned)

    def test_POST_release_returns_modified_nodes(self):
        owner = self.logged_in_user
        acceptable_states = {
            NODE_STATUS.READY,
            NODE_STATUS.ALLOCATED,
            NODE_STATUS.RESERVED,
            }
        nodes = [
            factory.make_node(status=status, owner=owner)
            for status in acceptable_states
            ]
        response = self.client.post(
            self.get_uri('nodes/'), {
                'op': 'release',
                'nodes': [node.system_id for node in nodes],
                })
        parsed_result = json.loads(response.content)
        self.assertEqual(httplib.OK, response.status_code)
        # The first node is READY, so shouldn't be touched
        self.assertItemsEqual(
            [nodes[1].system_id, nodes[2].system_id],
            parsed_result)

    def test_handle_when_URL_is_repeated(self):
        # bin/maas-enlist (in the maas-enlist package) has a bug where the
        # path it uses is doubled up. This was not discovered previously
        # because the API URL patterns were not anchored (see bug 1131323).
        # For compatibility, MAAS will handle requests to obviously incorrect
        # paths. It does *not* redirect because (a) it's not clear that curl
        # (used by maas-enlist) supports HTTP 307 redirects, which are needed
        # to support redirecting POSTs, and (b) curl does not follow redirects
        # by default anyway.
        architecture = factory.getRandomChoice(ARCHITECTURE_CHOICES)
        response = self.client.post(
            self.get_uri('nodes/MAAS/api/1.0/nodes/'),
            {
                'op': 'new',
                'hostname': factory.getRandomString(),
                'architecture': architecture,
                'mac_addresses': ['aa:bb:cc:dd:ee:ff'],
            })
        self.assertEqual(httplib.OK, response.status_code)
        system_id = json.loads(response.content)['system_id']
        nodes = Node.objects.filter(system_id=system_id)
        self.assertIsNotNone(get_one(nodes))


class AccountAPITest(APITestCase):

    def test_create_authorisation_token(self):
        # The api operation create_authorisation_token returns a json dict
        # with the consumer_key, the token_key and the token_secret in it.
        response = self.client.post(
            self.get_uri('account/'), {'op': 'create_authorisation_token'})
        parsed_result = json.loads(response.content)

        self.assertEqual(
            ['consumer_key', 'token_key', 'token_secret'],
            sorted(parsed_result))
        self.assertIsInstance(parsed_result['consumer_key'], basestring)
        self.assertIsInstance(parsed_result['token_key'], basestring)
        self.assertIsInstance(parsed_result['token_secret'], basestring)

    def test_delete_authorisation_token_not_found(self):
        # If the provided token_key does not exist (for the currently
        # logged-in user), the api returns a 'Not Found' (404) error.
        response = self.client.post(
            self.get_uri('account/'),
            {'op': 'delete_authorisation_token', 'token_key': 'no-such-token'})

        self.assertEqual(httplib.NOT_FOUND, response.status_code)

    def test_delete_authorisation_token_bad_request_no_token(self):
        # token_key is a mandatory parameter when calling
        # delete_authorisation_token. It it is not present in the request's
        # parameters, the api returns a 'Bad Request' (400) error.
        response = self.client.post(
            self.get_uri('account/'), {'op': 'delete_authorisation_token'})

        self.assertEqual(httplib.BAD_REQUEST, response.status_code)


class TestSSHKeyHandlers(APITestCase):

    def test_list_works(self):
        _, keys = factory.make_user_with_keys(user=self.logged_in_user)
        params = dict(op="list")
        response = self.client.get(
            self.get_uri('account/prefs/sshkeys/'), params)
        self.assertEqual(httplib.OK, response.status_code, response)
        parsed_result = json.loads(response.content)
        expected_result = [
            dict(
                id=keys[0].id,
                key=keys[0].key,
                resource_uri=reverse('sshkey_handler', args=[keys[0].id]),
                ),
            dict(
                id=keys[1].id,
                key=keys[1].key,
                resource_uri=reverse('sshkey_handler', args=[keys[1].id]),
                ),
            ]
        self.assertEqual(expected_result, parsed_result)

    def test_get_by_id_works(self):
        _, keys = factory.make_user_with_keys(
            n_keys=1, user=self.logged_in_user)
        key = keys[0]
        response = self.client.get(
            self.get_uri('account/prefs/sshkeys/%s/' % key.id))
        self.assertEqual(httplib.OK, response.status_code, response)
        parsed_result = json.loads(response.content)
        expected = dict(
            id=key.id,
            key=key.key,
            resource_uri=reverse('sshkey_handler', args=[key.id]),
            )
        self.assertEqual(expected, parsed_result)

    def test_delete_by_id_works(self):
        _, keys = factory.make_user_with_keys(
            n_keys=2, user=self.logged_in_user)
        response = self.client.delete(
            self.get_uri('account/prefs/sshkeys/%s/' % keys[0].id))
        self.assertEqual(httplib.NO_CONTENT, response.status_code, response)
        keys_after = SSHKey.objects.filter(user=self.logged_in_user)
        self.assertEqual(1, len(keys_after))
        self.assertEqual(keys[1].id, keys_after[0].id)

    def test_delete_fails_if_not_your_key(self):
        user, keys = factory.make_user_with_keys(n_keys=1)
        response = self.client.delete(
            self.get_uri('account/prefs/sshkeys/%s/' % keys[0].id))
        self.assertEqual(httplib.FORBIDDEN, response.status_code, response)
        self.assertEqual(1, len(SSHKey.objects.filter(user=user)))

    def test_adding_works(self):
        key_string = get_data('data/test_rsa0.pub')
        response = self.client.post(
            self.get_uri('account/prefs/sshkeys/'),
            data=dict(op="new", key=key_string))
        self.assertEqual(httplib.CREATED, response.status_code)
        parsed_response = json.loads(response.content)
        self.assertEqual(key_string, parsed_response["key"])
        added_key = get_one(SSHKey.objects.filter(user=self.logged_in_user))
        self.assertEqual(key_string, added_key.key)

    def test_adding_catches_key_validation_errors(self):
        key_string = factory.getRandomString()
        response = self.client.post(
            self.get_uri('account/prefs/sshkeys/'),
            data=dict(op='new', key=key_string))
        self.assertEqual(httplib.BAD_REQUEST, response.status_code, response)
        self.assertIn("Invalid", response.content)

    def test_adding_returns_badrequest_when_key_not_in_form(self):
        response = self.client.post(
            self.get_uri('account/prefs/sshkeys/'),
            data=dict(op='new'))
        self.assertEqual(httplib.BAD_REQUEST, response.status_code, response)
        self.assertEqual(
            dict(key=["This field is required."]),
            json.loads(response.content))


class MAASAPIAnonTest(APIv10TestMixin, MAASServerTestCase):
    # The MAAS' handler is not accessible to anon users.

    def test_anon_get_config_forbidden(self):
        response = self.client.get(
            self.get_uri('maas/'),
            {'op': 'get_config'})

        self.assertEqual(httplib.FORBIDDEN, response.status_code)

    def test_anon_set_config_forbidden(self):
        response = self.client.post(
            self.get_uri('maas/'),
            {'op': 'set_config'})

        self.assertEqual(httplib.FORBIDDEN, response.status_code)


class MAASAPITest(APITestCase):

    def test_simple_user_get_config_forbidden(self):
        response = self.client.get(
            self.get_uri('maas/'),
            {'op': 'get_config'})

        self.assertEqual(httplib.FORBIDDEN, response.status_code)

    def test_simple_user_set_config_forbidden(self):
        response = self.client.post(
            self.get_uri('maas/'),
            {'op': 'set_config'})

        self.assertEqual(httplib.FORBIDDEN, response.status_code)

    def test_get_config_requires_name_param(self):
        self.become_admin()
        response = self.client.get(
            self.get_uri('maas/'),
            {
                'op': 'get_config',
            })

        self.assertEqual(httplib.BAD_REQUEST, response.status_code)
        self.assertEqual("No provided name!", response.content)

    def test_get_config_returns_config(self):
        self.become_admin()
        name = 'maas_name'
        value = factory.getRandomString()
        Config.objects.set_config(name, value)
        response = self.client.get(
            self.get_uri('maas/'),
            {
                'op': 'get_config',
                'name': name,
            })

        self.assertEqual(httplib.OK, response.status_code)
        parsed_result = json.loads(response.content)
        self.assertIn('application/json', response['Content-Type'])
        self.assertEqual(value, parsed_result)

    def test_get_config_rejects_unknown_config_item(self):
        self.become_admin()
        name = factory.getRandomString()
        value = factory.getRandomString()
        Config.objects.set_config(name, value)
        response = self.client.get(
            self.get_uri('maas/'),
            {
                'op': 'get_config',
                'name': name,
            })

        self.assertEqual(
            (
                httplib.BAD_REQUEST,
                {name: [INVALID_SETTING_MSG_TEMPLATE % name]},
            ),
            (response.status_code, json.loads(response.content)))

    def test_set_config_requires_name_param(self):
        self.become_admin()
        response = self.client.post(
            self.get_uri('maas/'),
            {
                'op': 'set_config',
                'value': factory.getRandomString(),
            })

        self.assertEqual(httplib.BAD_REQUEST, response.status_code)
        self.assertEqual("No provided name!", response.content)

    def test_set_config_requires_string_name_param(self):
        self.become_admin()
        value = factory.getRandomString()
        response = self.client.post(
            self.get_uri('maas/'),
            {
                'op': 'set_config',
                'name': '',  # Invalid empty name.
                'value': value,
            })

        self.assertEqual(httplib.BAD_REQUEST, response.status_code)
        self.assertEqual(
           "Invalid name: Please enter a value", response.content)

    def test_set_config_requires_value_param(self):
        self.become_admin()
        response = self.client.post(
            self.get_uri('maas/'),
            {
                'op': 'set_config',
                'name': factory.getRandomString(),
            })

        self.assertEqual(httplib.BAD_REQUEST, response.status_code)
        self.assertEqual("No provided value!", response.content)

    def test_admin_set_config(self):
        self.become_admin()
        name = 'maas_name'
        value = factory.getRandomString()
        response = self.client.post(
            self.get_uri('maas/'),
            {
                'op': 'set_config',
                'name': name,
                'value': value,
            })

        self.assertEqual(
            httplib.OK, response.status_code, response.content)
        stored_value = Config.objects.get_config(name)
        self.assertEqual(stored_value, value)

    def test_admin_set_config_rejects_unknown_config_item(self):
        self.become_admin()
        name = factory.getRandomString()
        value = factory.getRandomString()
        response = self.client.post(
            self.get_uri('maas/'),
            {
                'op': 'set_config',
                'name': name,
                'value': value,
            })

        self.assertEqual(
            (
                httplib.BAD_REQUEST,
                {name: [INVALID_SETTING_MSG_TEMPLATE % name]},
            ),
            (response.status_code, json.loads(response.content)))


class APIErrorsTest(APIv10TestMixin, TransactionTestCase):

    def test_internal_error_generates_proper_api_response(self):
        error_message = factory.getRandomString()

        # Monkey patch api.create_node to have it raise a RuntimeError.
        def raise_exception(*args, **kwargs):
            raise RuntimeError(error_message)
        self.patch(api, 'create_node', raise_exception)
        response = self.client.post(self.get_uri('nodes/'), {'op': 'new'})

        self.assertEqual(
            (httplib.INTERNAL_SERVER_ERROR, error_message),
            (response.status_code, response.content))


def dict_subset(obj, fields):
    """Return a dict of a subset of the fields/values of an object."""
    undefined = object()
    values = (getattr(obj, field, undefined) for field in fields)
    return {
        field: value for field, value in izip(fields, values)
        if value is not undefined
     }


class TestNodeGroupInterfacesAPI(APITestCase):

    def test_list_lists_interfaces(self):
        self.become_admin()
        nodegroup = factory.make_node_group()
        response = self.client.get(
            reverse('nodegroupinterfaces_handler', args=[nodegroup.uuid]),
            {'op': 'list'})
        self.assertEqual(httplib.OK, response.status_code)
        self.assertEqual(
            [
                dict_subset(
                    interface, DISPLAYED_NODEGROUPINTERFACE_FIELDS)
                for interface in nodegroup.nodegroupinterface_set.all()
            ],
            json.loads(response.content))

    def test_list_only_available_to_admin(self):
        nodegroup = factory.make_node_group()
        response = self.client.get(
            reverse('nodegroupinterfaces_handler', args=[nodegroup.uuid]),
            {'op': 'list'})
        self.assertEqual(httplib.FORBIDDEN, response.status_code)

    def test_new_creates_interface(self):
        self.become_admin()
        nodegroup = factory.make_node_group(
            management=NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED)

        interface_settings = make_interface_settings()
        query_data = dict(interface_settings, op="new")
        response = self.client.post(
            reverse('nodegroupinterfaces_handler', args=[nodegroup.uuid]),
            query_data)
        self.assertEqual(httplib.OK, response.status_code, response.content)
        expected_result = interface_settings
        new_interface = NodeGroupInterface.objects.get(
            nodegroup=nodegroup, interface=interface_settings['interface'])
        self.assertThat(
            new_interface,
            MatchesStructure.byEquality(**expected_result))

    def test_new_validates_data(self):
        self.become_admin()
        nodegroup = factory.make_node_group()
        response = self.client.post(
            reverse('nodegroupinterfaces_handler', args=[nodegroup.uuid]),
            {'op': 'new', 'ip': 'invalid ip'})
        self.assertEqual(
            (
                httplib.BAD_REQUEST,
                {'ip': ["Enter a valid IPv4 or IPv6 address."]},
            ),
            (response.status_code, json.loads(response.content)))

    def test_new_only_available_to_admin(self):
        nodegroup = factory.make_node_group()
        response = self.client.get(
            reverse('nodegroupinterfaces_handler', args=[nodegroup.uuid]),
            {'op': 'new'})
        self.assertEqual(httplib.FORBIDDEN, response.status_code)


class TestNodeGroupInterfaceAPI(APITestCase):

    def test_read_interface(self):
        self.become_admin()
        nodegroup = factory.make_node_group()
        interface = nodegroup.get_managed_interface()
        response = self.client.get(
            reverse(
                'nodegroupinterface_handler',
                args=[nodegroup.uuid, interface.interface]))
        self.assertEqual(httplib.OK, response.status_code)
        self.assertEqual(
            dict_subset(
                interface, DISPLAYED_NODEGROUPINTERFACE_FIELDS),
            json.loads(response.content))

    def test_update_interface(self):
        self.become_admin()
        nodegroup = factory.make_node_group()
        interface = nodegroup.get_managed_interface()
        get_ip_in_network = partial(
            factory.getRandomIPInNetwork, interface.network)
        new_ip_range_high = next(
            ip for ip in iter(get_ip_in_network, None)
            if ip != interface.ip_range_high)
        response = self.client_put(
            reverse(
                'nodegroupinterface_handler',
                args=[nodegroup.uuid, interface.interface]),
            {'ip_range_high': new_ip_range_high})
        self.assertEqual(
            (httplib.OK, new_ip_range_high),
            (response.status_code, reload_object(interface).ip_range_high))

    def test_delete_interface(self):
        self.become_admin()
        nodegroup = factory.make_node_group()
        interface = nodegroup.get_managed_interface()
        response = self.client.delete(
            reverse(
                'nodegroupinterface_handler',
                args=[nodegroup.uuid, interface.interface]))
        self.assertEqual(httplib.NO_CONTENT, response.status_code)
        self.assertFalse(
            NodeGroupInterface.objects.filter(
                interface=interface.interface, nodegroup=nodegroup).exists())


class TestBootImagesAPI(APITestCase):

    resources = (
        ('celery', FixtureResource(CeleryFixture())),
        )

    def report_images(self, nodegroup, images, client=None):
        if client is None:
            client = self.client
        return client.post(
            reverse('boot_images_handler'), {
                'images': json.dumps(images),
                'nodegroup': nodegroup.uuid,
                'op': 'report_boot_images',
                })

    def test_report_boot_images_does_not_work_for_normal_user(self):
        nodegroup = NodeGroup.objects.ensure_master()
        log_in_as_normal_user(self.client)
        response = self.report_images(nodegroup, [])
        self.assertEqual(
            httplib.FORBIDDEN, response.status_code, response.content)

    def test_report_boot_images_works_for_master_worker(self):
        nodegroup = NodeGroup.objects.ensure_master()
        client = make_worker_client(nodegroup)
        response = self.report_images(nodegroup, [], client=client)
        self.assertEqual(httplib.OK, response.status_code)

    def test_report_boot_images_stores_images(self):
        nodegroup = NodeGroup.objects.ensure_master()
        image = make_boot_image_params()
        client = make_worker_client(nodegroup)
        response = self.report_images(nodegroup, [image], client=client)
        self.assertEqual(
            (httplib.OK, "OK"),
            (response.status_code, response.content))
        self.assertTrue(
            BootImage.objects.have_image(nodegroup=nodegroup, **image))

    def test_report_boot_images_ignores_unknown_image_properties(self):
        nodegroup = NodeGroup.objects.ensure_master()
        image = make_boot_image_params()
        image['nonesuch'] = factory.make_name('nonesuch'),
        client = make_worker_client(nodegroup)
        response = self.report_images(nodegroup, [image], client=client)
        self.assertEqual(
            (httplib.OK, "OK"),
            (response.status_code, response.content))

    def test_report_boot_images_warns_if_no_images_found(self):
        nodegroup = NodeGroup.objects.ensure_master()
        factory.make_node_group()  # Second nodegroup with no images.
        recorder = self.patch(api, 'register_persistent_error')
        client = make_worker_client(nodegroup)
        response = self.report_images(nodegroup, [], client=client)
        self.assertEqual(
            (httplib.OK, "OK"),
            (response.status_code, response.content))

        self.assertIn(
            COMPONENT.IMPORT_PXE_FILES,
            [args[0][0] for args in recorder.call_args_list])
        # Check that the persistent error message contains a link to the
        # clusters listing.
        self.assertIn(
            "/settings/#accepted-clusters", recorder.call_args_list[0][0][1])

    def test_report_boot_images_warns_if_any_nodegroup_has_no_images(self):
        nodegroup = NodeGroup.objects.ensure_master()
        # Second nodegroup with no images.
        factory.make_node_group(status=NODEGROUP_STATUS.ACCEPTED)
        recorder = self.patch(api, 'register_persistent_error')
        client = make_worker_client(nodegroup)
        image = make_boot_image_params()
        response = self.report_images(nodegroup, [image], client=client)
        self.assertEqual(
            (httplib.OK, "OK"),
            (response.status_code, response.content))

        self.assertIn(
            COMPONENT.IMPORT_PXE_FILES,
            [args[0][0] for args in recorder.call_args_list])

    def test_report_boot_images_ignores_non_accepted_groups(self):
        nodegroup = factory.make_node_group(status=NODEGROUP_STATUS.ACCEPTED)
        factory.make_node_group(status=NODEGROUP_STATUS.PENDING)
        factory.make_node_group(status=NODEGROUP_STATUS.REJECTED)
        recorder = self.patch(api, 'register_persistent_error')
        client = make_worker_client(nodegroup)
        image = make_boot_image_params()
        response = self.report_images(nodegroup, [image], client=client)
        self.assertEqual(httplib.OK, response.status_code)
        self.assertEqual(0, recorder.call_count)

    def test_report_boot_images_removes_warning_if_images_found(self):
        self.patch(api, 'register_persistent_error')
        self.patch(api, 'discard_persistent_error')
        nodegroup = factory.make_node_group()
        image = make_boot_image_params()
        client = make_worker_client(nodegroup)

        response = self.report_images(nodegroup, [image], client=client)
        self.assertEqual(
            (httplib.OK, "OK"),
            (response.status_code, response.content))

        self.assertItemsEqual(
            [],
            api.register_persistent_error.call_args_list)
        api.discard_persistent_error.assert_called_once_with(
            COMPONENT.IMPORT_PXE_FILES)

    def test_worker_calls_report_boot_images(self):
        # report_boot_images() uses the report_boot_images op on the nodes
        # handlers to send image information.
        self.useFixture(
            EnvironmentVariableFixture("MAAS_URL", settings.DEFAULT_MAAS_URL))
        refresh_worker(NodeGroup.objects.ensure_master())
        self.patch(MAASClient, 'post')
        self.patch(tftppath, 'list_boot_images', Mock(return_value=[]))
        self.patch(boot_images, "get_cluster_uuid")

        tasks.report_boot_images.delay()

        # We're not concerned about the payloads (images and nodegroup) here;
        # those are tested in provisioningserver.tests.test_boot_images.
        MAASClient.post.assert_called_once_with(
            reverse('boot_images_handler').lstrip('/'), 'report_boot_images',
            images=ANY, nodegroup=ANY)
