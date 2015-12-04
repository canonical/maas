# Copyright 2013-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the nodes API."""

__all__ = []

import http.client
import json
import random

import crochet
from django.conf import settings
from django.core.urlresolvers import reverse
from django.http import QueryDict
from django.test import RequestFactory
from maasserver import (
    eventloop,
    forms,
)
from maasserver.api import nodes as nodes_module
from maasserver.api.utils import get_overridden_query_dict
from maasserver.enum import (
    INTERFACE_TYPE,
    NODE_STATUS,
    NODE_STATUS_CHOICES_DICT,
    NODEGROUP_STATUS,
    NODEGROUPINTERFACE_MANAGEMENT,
    POWER_STATE,
)
from maasserver.exceptions import (
    ClusterUnavailable,
    MAASAPIValidationError,
)
from maasserver.fields import MAC
from maasserver.models import (
    Config,
    Node,
    NodeGroup,
)
from maasserver.models.node import RELEASABLE_STATUSES
from maasserver.models.user import (
    create_auth_token,
    get_auth_tokens,
)
from maasserver.rpc.testing.fixtures import MockLiveRegionToClusterRPCFixture
from maasserver.testing.api import (
    APITestCase,
    APITransactionTestCase,
    MultipleUsersScenarios,
)
from maasserver.testing.architecture import make_usable_architecture
from maasserver.testing.eventloop import (
    RegionEventLoopFixture,
    RunningEventLoopFixture,
)
from maasserver.testing.factory import factory
from maasserver.testing.orm import reload_object
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils import ignore_unused
from maasserver.utils.orm import get_one
from maastesting.djangotestcase import count_queries
from maastesting.matchers import MockCalledOnceWith
from maastesting.twisted import always_succeed_with
from mock import Mock
from provisioningserver.power.poweraction import PowerActionFail
from provisioningserver.rpc import cluster as cluster_module
from provisioningserver.rpc.exceptions import NoConnectionsAvailable
from provisioningserver.utils.enum import map_enum
from testtools.matchers import (
    Contains,
    Equals,
    HasLength,
    Not,
)


class TestGetStorageLayoutParams(MAASServerTestCase):

    def test_sets_request_data_to_mutable(self):
        data = {
            'op': 'acquire',
            'storage_layout': 'flat',
        }
        request = RequestFactory().post(reverse('nodes_handler'), data)
        request.data = request.POST.copy()
        request.data._mutable = False
        nodes_module.get_storage_layout_params(request)
        self.assertTrue(request.data._mutable)


class NodeHostnameTest(MultipleUsersScenarios,
                       MAASServerTestCase):

    scenarios = [
        ('user', dict(userfactory=factory.make_User)),
        ('admin', dict(userfactory=factory.make_admin)),
    ]

    def test_GET_list_returns_fqdn_with_domain_name_from_cluster(self):
        # If DNS management is enabled, the domain part of a hostname
        # is replaced by the domain name defined on the cluster.
        hostname_without_domain = factory.make_name('hostname')
        hostname_with_domain = '%s.%s' % (
            hostname_without_domain, factory.make_string())
        domain = factory.make_name('domain')
        nodegroup = factory.make_NodeGroup(
            status=NODEGROUP_STATUS.ENABLED,
            name=domain,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS)
        factory.make_Node(
            hostname=hostname_with_domain, nodegroup=nodegroup)
        expected_hostname = '%s.%s' % (hostname_without_domain, domain)
        response = self.client.get(reverse('nodes_handler'), {'op': 'list'})
        self.assertEqual(
            http.client.OK.value, response.status_code, response.content)
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))
        self.assertItemsEqual(
            [expected_hostname],
            [node.get('hostname') for node in parsed_result])


class AnonymousIsRegisteredAPITest(MAASServerTestCase):

    def test_is_registered_returns_True_if_node_registered(self):
        mac_address = factory.make_mac_address()
        factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, mac_address=mac_address)
        response = self.client.get(
            reverse('nodes_handler'),
            {'op': 'is_registered', 'mac_address': mac_address})
        self.assertEqual(
            (http.client.OK.value, "true"),
            (response.status_code,
             response.content.decode(settings.DEFAULT_CHARSET)))

    def test_is_registered_normalizes_mac_address(self):
        # These two non-normalized MAC addresses are the same.
        non_normalized_mac_address = 'AA-bb-cc-dd-ee-ff'
        non_normalized_mac_address2 = 'aabbccddeeff'
        factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, mac_address=non_normalized_mac_address)
        response = self.client.get(
            reverse('nodes_handler'),
            {
                'op': 'is_registered',
                'mac_address': non_normalized_mac_address2
            })
        self.assertEqual(
            (http.client.OK.value, "true"),
            (response.status_code,
             response.content.decode(settings.DEFAULT_CHARSET)))

    def test_is_registered_returns_False_if_node_not_registered(self):
        mac_address = factory.make_mac_address()
        response = self.client.get(
            reverse('nodes_handler'),
            {'op': 'is_registered', 'mac_address': mac_address})
        self.assertEqual(
            (http.client.OK.value, "false"),
            (response.status_code,
             response.content.decode(settings.DEFAULT_CHARSET)))


def extract_system_ids(parsed_result):
    """List the system_ids of the nodes in `parsed_result`."""
    return [node.get('system_id') for node in parsed_result]


def extract_system_ids_from_nodes(nodes):
    return [node.system_id for node in nodes]


class RequestFixture:
    def __init__(self, dict, fields):
        self.user = factory.make_User()
        self.GET = get_overridden_query_dict(dict, QueryDict(''), fields)


class TestFilteredNodesListFromRequest(APITestCase):

    def test_node_list_with_id_returns_matching_nodes(self):
        # The "list" operation takes optional "id" parameters.  Only
        # nodes with matching ids will be returned.
        ids = [factory.make_Node().system_id for _ in range(3)]
        matching_id = ids[0]
        query = RequestFixture({'id': [matching_id]}, 'id')
        node_list = nodes_module.filtered_nodes_list_from_request(query)

        self.assertItemsEqual(
            [matching_id],
            extract_system_ids_from_nodes(node_list))

    def test_node_list_with_nonexistent_id_returns_empty_list(self):
        # Trying to list a nonexistent node id returns a list containing
        # no nodes -- even if other (non-matching) nodes exist.
        existing_id = factory.make_Node().system_id
        nonexistent_id = existing_id + factory.make_string()
        query = RequestFixture({'id': [nonexistent_id]}, 'id')
        node_list = nodes_module.filtered_nodes_list_from_request(query)

        self.assertItemsEqual(
            [],
            extract_system_ids_from_nodes(node_list))

    def test_node_list_with_ids_orders_by_id(self):
        # Even when ids are passed to "list," nodes are returned in id
        # order, not necessarily in the order of the id arguments.
        all_nodes = [factory.make_Node() for _ in range(3)]
        system_ids = [node.system_id for node in all_nodes]
        random.shuffle(system_ids)

        query = RequestFixture({'id': list(system_ids)}, 'id')
        node_list = nodes_module.filtered_nodes_list_from_request(query)

        sorted_system_ids = [
            node.system_id
            for node in sorted(all_nodes, key=lambda node: node.id)
        ]
        self.assertSequenceEqual(
            sorted_system_ids,
            extract_system_ids_from_nodes(node_list))

    def test_node_list_with_some_matching_ids_returns_matching_nodes(self):
        # If some nodes match the requested ids and some don't, only the
        # matching ones are returned.
        existing_id = factory.make_Node().system_id
        nonexistent_id = existing_id + factory.make_string()

        query = RequestFixture({'id': [existing_id, nonexistent_id]}, 'id')
        node_list = nodes_module.filtered_nodes_list_from_request(query)

        self.assertItemsEqual(
            [existing_id],
            extract_system_ids_from_nodes(node_list))

    def test_node_list_with_hostname_returns_matching_nodes(self):
        # The list operation takes optional "hostname" parameters. Only nodes
        # with matching hostnames will be returned.
        nodes = [factory.make_Node() for _ in range(3)]
        matching_hostname = nodes[0].hostname
        matching_system_id = nodes[0].system_id

        query = RequestFixture({'hostname': [matching_hostname]}, 'hostname')
        node_list = nodes_module.filtered_nodes_list_from_request(query)

        self.assertItemsEqual(
            [matching_system_id],
            extract_system_ids_from_nodes(node_list))

    def test_node_list_with_macs_returns_matching_nodes(self):
        # The "list" operation takes optional "mac_address" parameters. Only
        # nodes with matching MAC addresses will be returned.
        interfaces = [
            factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
            for _ in range(3)
        ]
        matching_mac = str(interfaces[0].mac_address)
        matching_system_id = interfaces[0].node.system_id

        query = RequestFixture({'mac_address': [matching_mac]}, 'mac_address')
        node_list = nodes_module.filtered_nodes_list_from_request(query)

        self.assertItemsEqual(
            [matching_system_id],
            extract_system_ids_from_nodes(node_list))

    def test_node_list_with_invalid_macs_returns_sensible_error(self):
        # If specifying an invalid MAC, make sure the error that's
        # returned is not a crazy stack trace, but something nice to
        # humans.
        bad_mac1 = '00:E0:81:DD:D1:ZZ'  # ZZ is bad.
        bad_mac2 = '00:E0:81:DD:D1:XX'  # XX is bad.
        ok_mac = str(
            factory.make_Interface(INTERFACE_TYPE.PHYSICAL).mac_address)
        mac_list = [bad_mac1, bad_mac2, ok_mac]

        query = RequestFixture({'mac_address': mac_list}, 'mac_address')
        expected_msg = [
            "Invalid MAC address(es): 00:E0:81:DD:D1:ZZ, 00:E0:81:DD:D1:XX"
        ]
        ex = self.assertRaises(
            MAASAPIValidationError,
            nodes_module.filtered_nodes_list_from_request,
            query)
        self.assertEqual(expected_msg, ex.messages)

    def test_node_list_with_agent_name_filters_by_agent_name(self):
        non_listed_node = factory.make_Node(
            agent_name=factory.make_name('agent_name'))
        ignore_unused(non_listed_node)
        agent_name = factory.make_name('agent-name')
        node = factory.make_Node(agent_name=agent_name)

        query = RequestFixture({'agent_name': agent_name}, 'agent_name')
        node_list = nodes_module.filtered_nodes_list_from_request(query)

        self.assertSequenceEqual(
            [node.system_id],
            extract_system_ids_from_nodes(node_list))

    def test_node_list_with_agent_name_filters_with_empty_string(self):
        factory.make_Node(agent_name=factory.make_name('agent-name'))
        node = factory.make_Node(agent_name='')

        query = RequestFixture({'agent_name': ''}, 'agent_name')
        node_list = nodes_module.filtered_nodes_list_from_request(query)

        self.assertSequenceEqual(
            [node.system_id],
            extract_system_ids_from_nodes(node_list))

    def test_node_list_without_agent_name_does_not_filter(self):
        nodes = [
            factory.make_Node(agent_name=factory.make_name('agent-name'))
            for _ in range(3)]

        query = RequestFixture({}, '')
        node_list = nodes_module.filtered_nodes_list_from_request(query)

        self.assertSequenceEqual(
            [node.system_id for node in nodes],
            extract_system_ids_from_nodes(node_list))

    def test_node_list_doesnt_list_devices(self):
        nodes = [
            factory.make_Node(agent_name=factory.make_name('agent-name'))
            for _ in range(3)]
        # Create devices.
        nodes = [
            factory.make_Node(installable=False)
            for _ in range(3)]

        query = RequestFixture({}, '')
        node_list = nodes_module.filtered_nodes_list_from_request(query)

        system_ids = extract_system_ids_from_nodes(node_list)
        self.assertEqual(
            [],
            [node.system_id for node in nodes if node.system_id in system_ids],
            "Node listing contains devices.")

    def test_node_list_with_zone_filters_by_zone(self):
        non_listed_node = factory.make_Node(
            zone=factory.make_Zone(name='twilight'))
        ignore_unused(non_listed_node)
        zone = factory.make_Zone()
        node = factory.make_Node(zone=zone)

        query = RequestFixture({'zone': zone.name}, 'zone')
        node_list = nodes_module.filtered_nodes_list_from_request(query)

        self.assertSequenceEqual(
            [node.system_id], extract_system_ids_from_nodes(node_list))

    def test_node_list_without_zone_does_not_filter(self):
        nodes = [factory.make_Node(zone=factory.make_Zone())
                 for _ in range(3)]

        query = RequestFixture({}, '')
        node_list = nodes_module.filtered_nodes_list_from_request(query)

        self.assertSequenceEqual(
            [node.system_id for node in nodes],
            extract_system_ids_from_nodes(node_list))


class TestNodesAPI(APITestCase):
    """Tests for /api/1.0/nodes/."""

    def test_handler_path(self):
        self.assertEqual(
            '/api/1.0/nodes/', reverse('nodes_handler'))

    def test_POST_new_creates_node(self):
        # The API allows a non-admin logged-in user to create a Node.
        hostname = factory.make_name('host')
        architecture = make_usable_architecture(self)
        macs = {
            factory.make_mac_address()
            for _ in range(random.randint(1, 2))
        }
        response = self.client.post(
            reverse('nodes_handler'),
            {
                'op': 'new',
                'autodetect_nodegroup': '1',
                'hostname': hostname,
                'architecture': architecture,
                'mac_addresses': macs,
            })
        self.assertEqual(http.client.OK, response.status_code)
        system_id = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))['system_id']
        node = Node.objects.get(system_id=system_id)
        self.expectThat(node.hostname, Equals(hostname))
        self.expectThat(node.architecture, Equals(architecture))
        self.expectThat(
            {nic.mac_address for nic in node.interface_set.all()},
            Equals(macs))

    def test_POST_new_when_logged_in_creates_node_in_declared_state(self):
        # When a user enlists a node, it goes into the New state.
        # This will change once we start doing proper commissioning.
        response = self.client.post(
            reverse('nodes_handler'),
            {
                'op': 'new',
                'autodetect_nodegroup': '1',
                'hostname': factory.make_name('host'),
                'architecture': make_usable_architecture(self),
                'mac_addresses': [factory.make_mac_address()],
            })
        self.assertEqual(http.client.OK, response.status_code)
        system_id = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))['system_id']
        self.assertEqual(
            NODE_STATUS.NEW,
            Node.objects.get(system_id=system_id).status)

    def test_POST_new_takes_default_for_disable_ipv4_from_given_cluster(self):
        default_disable_ipv4 = factory.pick_bool()
        cluster = factory.make_NodeGroup(
            default_disable_ipv4=default_disable_ipv4)
        response = self.client.post(
            reverse('nodes_handler'),
            {
                'op': 'new',
                'nodegroup': cluster.id,
                'architecture': make_usable_architecture(self),
                'mac_addresses': [factory.make_mac_address()],
            })
        self.assertEqual(http.client.OK, response.status_code)
        system_id = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))['system_id']
        node = Node.objects.get(system_id=system_id)
        self.assertEqual(default_disable_ipv4, node.disable_ipv4)

    def test_POST_new_takes_default_disable_ipv4_from_guessed_cluster(self):
        default_disable_ipv4 = factory.pick_bool()
        master_cluster = NodeGroup.objects.ensure_master()
        master_cluster.default_disable_ipv4 = default_disable_ipv4
        master_cluster.save()
        response = self.client.post(
            reverse('nodes_handler'),
            {
                'op': 'new',
                'autodetect_nodegroup': '1',
                'architecture': make_usable_architecture(self),
                'mac_addresses': [factory.make_mac_address()],
            })
        self.assertEqual(http.client.OK, response.status_code)
        system_id = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))['system_id']
        node = Node.objects.get(system_id=system_id)
        self.assertEqual(default_disable_ipv4, node.disable_ipv4)

    def test_POST_new_when_no_RPC_to_cluster_defaults_empty_power(self):
        # Test for bug 1305061, if there is no cluster RPC connection
        # then make sure that power_type is defaulted to the empty
        # string rather than being entirely absent, which results in a
        # crash.
        cluster_error = factory.make_name("cluster error")
        self.patch(forms, 'get_power_types').side_effect = (
            ClusterUnavailable(cluster_error))
        self.become_admin()
        # The patching behind the scenes to avoid *real* RPC is
        # complex and the available power types is actually a
        # valid set, so use an invalid type to trigger the bug here.
        power_type = factory.make_name("power_type")
        response = self.client.post(
            reverse('nodes_handler'),
            {
                'op': 'new',
                'autodetect_nodegroup': '1',
                'architecture': make_usable_architecture(self),
                'mac_addresses': ['aa:bb:cc:dd:ee:ff'],
                'power_type': power_type,
            })
        self.assertEqual(http.client.BAD_REQUEST, response.status_code)
        validation_errors = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))['power_type']
        self.assertIn(cluster_error, validation_errors[1])

    def test_GET_list_lists_nodes(self):
        # The api allows for fetching the list of Nodes.
        node1 = factory.make_Node()
        node2 = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=self.logged_in_user)
        response = self.client.get(reverse('nodes_handler'), {'op': 'list'})
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))

        self.assertEqual(http.client.OK, response.status_code)
        self.assertItemsEqual(
            [node1.system_id, node2.system_id],
            extract_system_ids(parsed_result))

    def create_nodes(self, nodegroup, nb):
        for _ in range(nb):
            factory.make_Node(nodegroup=nodegroup, interface=True)

    def test_GET_list_nodes_issues_constant_number_of_queries(self):
        # XXX: GavinPanella 2014-10-03 bug=1377335
        self.skip("Unreliable; something is causing varying counts.")

        nodegroup = factory.make_NodeGroup()
        self.create_nodes(nodegroup, 10)
        num_queries1, response1 = count_queries(
            self.client.get, reverse('nodes_handler'), {'op': 'list'})
        self.create_nodes(nodegroup, 10)
        num_queries2, response2 = count_queries(
            self.client.get, reverse('nodes_handler'), {'op': 'list'})
        # Make sure the responses are ok as it's not useful to compare the
        # number of queries if they are not.
        self.assertEqual(
            [http.client.OK, http.client.OK, 10, 20],
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
        response = self.client.get(reverse('nodes_handler'), {'op': 'list'})
        self.assertItemsEqual(
            [], json.loads(response.content.decode(settings.DEFAULT_CHARSET)))

    def test_GET_list_orders_by_id(self):
        # Nodes are returned in id order.
        nodes = [factory.make_Node() for counter in range(3)]
        response = self.client.get(reverse('nodes_handler'), {'op': 'list'})
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))
        self.assertSequenceEqual(
            [node.system_id for node in nodes],
            extract_system_ids(parsed_result))

    def test_GET_list_with_id_returns_matching_nodes(self):
        # The "list" operation takes optional "id" parameters.  Only
        # nodes with matching ids will be returned.
        ids = [factory.make_Node().system_id for counter in range(3)]
        matching_id = ids[0]
        response = self.client.get(reverse('nodes_handler'), {
            'op': 'list',
            'id': [matching_id],
        })
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))
        self.assertItemsEqual(
            [matching_id], extract_system_ids(parsed_result))

    def test_GET_list_with_nonexistent_id_returns_empty_list(self):
        # Trying to list a nonexistent node id returns a list containing
        # no nodes -- even if other (non-matching) nodes exist.
        existing_id = factory.make_Node().system_id
        nonexistent_id = existing_id + factory.make_string()
        response = self.client.get(reverse('nodes_handler'), {
            'op': 'list',
            'id': [nonexistent_id],
        })
        self.assertItemsEqual([], json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)))

    def test_GET_list_with_ids_orders_by_id(self):
        # Even when ids are passed to "list," nodes are returned in id
        # order, not necessarily in the order of the id arguments.
        ids = [factory.make_Node().system_id for counter in range(3)]
        response = self.client.get(reverse('nodes_handler'), {
            'op': 'list',
            'id': list(reversed(ids)),
        })
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))
        self.assertSequenceEqual(ids, extract_system_ids(parsed_result))

    def test_GET_list_with_some_matching_ids_returns_matching_nodes(self):
        # If some nodes match the requested ids and some don't, only the
        # matching ones are returned.
        existing_id = factory.make_Node().system_id
        nonexistent_id = existing_id + factory.make_string()
        response = self.client.get(reverse('nodes_handler'), {
            'op': 'list',
            'id': [existing_id, nonexistent_id],
        })
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))
        self.assertItemsEqual(
            [existing_id], extract_system_ids(parsed_result))

    def test_GET_list_with_hostname_returns_matching_nodes(self):
        # The list operation takes optional "hostname" parameters. Only nodes
        # with matching hostnames will be returned.
        nodes = [factory.make_Node() for _ in range(3)]
        matching_hostname = nodes[0].hostname
        matching_system_id = nodes[0].system_id
        response = self.client.get(reverse('nodes_handler'), {
            'op': 'list',
            'hostname': [matching_hostname],
        })
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))
        self.assertItemsEqual(
            [matching_system_id], extract_system_ids(parsed_result))

    def test_GET_list_with_macs_returns_matching_nodes(self):
        # The "list" operation takes optional "mac_address" parameters. Only
        # nodes with matching MAC addresses will be returned.
        interfaces = [
            factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
            for _ in range(3)
        ]
        matching_mac = interfaces[0].mac_address
        matching_system_id = interfaces[0].node.system_id
        response = self.client.get(reverse('nodes_handler'), {
            'op': 'list',
            'mac_address': [matching_mac],
        })
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))
        self.assertItemsEqual(
            [matching_system_id], extract_system_ids(parsed_result))

    def test_GET_list_with_invalid_macs_returns_sensible_error(self):
        # If specifying an invalid MAC, make sure the error that's
        # returned is not a crazy stack trace, but something nice to
        # humans.
        bad_mac1 = '00:E0:81:DD:D1:ZZ'  # ZZ is bad.
        bad_mac2 = '00:E0:81:DD:D1:XX'  # XX is bad.
        ok_mac = str(
            factory.make_Interface(INTERFACE_TYPE.PHYSICAL).mac_address)
        response = self.client.get(reverse('nodes_handler'), {
            'op': 'list',
            'mac_address': [bad_mac1, bad_mac2, ok_mac],
        })
        self.assertEqual(http.client.BAD_REQUEST, response.status_code)
        self.assertIn(
            "Invalid MAC address(es): 00:E0:81:DD:D1:ZZ, 00:E0:81:DD:D1:XX",
            response.content.decode(settings.DEFAULT_CHARSET))

    def test_GET_list_with_agent_name_filters_by_agent_name(self):
        non_listed_node = factory.make_Node(
            agent_name=factory.make_name('agent_name'))
        ignore_unused(non_listed_node)
        agent_name = factory.make_name('agent-name')
        node = factory.make_Node(agent_name=agent_name)
        response = self.client.get(reverse('nodes_handler'), {
            'op': 'list',
            'agent_name': agent_name,
        })
        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))
        self.assertSequenceEqual(
            [node.system_id], extract_system_ids(parsed_result))

    def test_GET_list_with_agent_name_filters_with_empty_string(self):
        factory.make_Node(agent_name=factory.make_name('agent-name'))
        node = factory.make_Node(agent_name='')
        response = self.client.get(reverse('nodes_handler'), {
            'op': 'list',
            'agent_name': '',
        })
        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))
        self.assertSequenceEqual(
            [node.system_id], extract_system_ids(parsed_result))

    def test_GET_list_without_agent_name_does_not_filter(self):
        nodes = [
            factory.make_Node(agent_name=factory.make_name('agent-name'))
            for _ in range(3)]
        response = self.client.get(reverse('nodes_handler'), {'op': 'list'})
        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))
        self.assertSequenceEqual(
            [node.system_id for node in nodes],
            extract_system_ids(parsed_result))

    def test_GET_list_doesnt_list_devices(self):
        nodes = [
            factory.make_Node(agent_name=factory.make_name('agent-name'))
            for _ in range(3)]
        # Create devices.
        nodes = [
            factory.make_Node(installable=False)
            for _ in range(3)]
        response = self.client.get(reverse('nodes_handler'), {'op': 'list'})
        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))
        system_ids = extract_system_ids(parsed_result)
        self.assertEqual(
            [],
            [node.system_id for node in nodes if node.system_id in system_ids],
            "Node listing contains devices.")

    def test_GET_list_with_zone_filters_by_zone(self):
        non_listed_node = factory.make_Node(
            zone=factory.make_Zone(name='twilight'))
        ignore_unused(non_listed_node)
        zone = factory.make_Zone()
        node = factory.make_Node(zone=zone)
        response = self.client.get(reverse('nodes_handler'), {
            'op': 'list',
            'zone': zone.name,
        })
        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))
        self.assertSequenceEqual(
            [node.system_id], extract_system_ids(parsed_result))

    def test_GET_list_without_zone_does_not_filter(self):
        nodes = [
            factory.make_Node(zone=factory.make_Zone())
            for _ in range(3)]
        response = self.client.get(reverse('nodes_handler'), {'op': 'list'})
        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))
        self.assertSequenceEqual(
            [node.system_id for node in nodes],
            extract_system_ids(parsed_result))

    def test_GET_list_allocated_returns_only_allocated_with_user_token(self):
        # If the user's allocated nodes have different session tokens,
        # list_allocated should only return the nodes that have the
        # current request's token on them.
        node_1 = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=self.logged_in_user,
            token=get_auth_tokens(self.logged_in_user)[0])
        second_token = create_auth_token(self.logged_in_user)
        factory.make_Node(
            owner=self.logged_in_user, status=NODE_STATUS.ALLOCATED,
            token=second_token)

        user_2 = factory.make_User()
        create_auth_token(user_2)
        factory.make_Node(
            owner=self.logged_in_user, status=NODE_STATUS.ALLOCATED,
            token=second_token)

        # At this point we have two nodes owned by the same user but
        # allocated with different tokens, and a third node allocated to
        # someone else entirely.  We expect list_allocated to
        # return the node with the same token as the one used in
        # self.client, which is the one we set on node_1 above.

        response = self.client.get(reverse('nodes_handler'), {
            'op': 'list_allocated'})
        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))
        self.assertItemsEqual(
            [node_1.system_id], extract_system_ids(parsed_result))

    def test_GET_list_allocated_filters_by_id(self):
        # list_allocated takes an optional list of 'id' parameters to
        # filter returned results.
        current_token = get_auth_tokens(self.logged_in_user)[0]
        nodes = []
        for _ in range(3):
            nodes.append(factory.make_Node(
                status=NODE_STATUS.ALLOCATED,
                owner=self.logged_in_user, token=current_token))

        required_node_ids = [nodes[0].system_id, nodes[1].system_id]
        response = self.client.get(reverse('nodes_handler'), {
            'op': 'list_allocated',
            'id': required_node_ids,
        })
        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))
        self.assertItemsEqual(
            required_node_ids, extract_system_ids(parsed_result))

    def test_POST_acquire_returns_available_node(self):
        # The "acquire" operation returns an available node.
        available_status = NODE_STATUS.READY
        node = factory.make_Node(
            status=available_status, owner=None, with_boot_disk=True)
        response = self.client.post(
            reverse('nodes_handler'), {'op': 'acquire'})
        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))
        self.assertEqual(node.system_id, parsed_result['system_id'])

    def test_POST_acquire_allocates_node(self):
        # The "acquire" operation allocates the node it returns.
        available_status = NODE_STATUS.READY
        node = factory.make_Node(
            status=available_status, owner=None, with_boot_disk=True)
        self.client.post(reverse('nodes_handler'), {'op': 'acquire'})
        node = Node.objects.get(system_id=node.system_id)
        self.assertEqual(self.logged_in_user, node.owner)

    def test_POST_acquire_uses_node_acquire_lock(self):
        # The "acquire" operation allocates the node it returns.
        available_status = NODE_STATUS.READY
        factory.make_Node(
            status=available_status, owner=None, with_boot_disk=True)
        node_acquire = self.patch(nodes_module.locks, 'node_acquire')
        self.client.post(reverse('nodes_handler'), {'op': 'acquire'})
        self.assertThat(node_acquire.__enter__, MockCalledOnceWith())
        self.assertThat(
            node_acquire.__exit__, MockCalledOnceWith(None, None, None))

    def test_POST_acquire_sets_agent_name(self):
        available_status = NODE_STATUS.READY
        node = factory.make_Node(
            status=available_status, owner=None,
            agent_name=factory.make_name('agent-name'), with_boot_disk=True)
        agent_name = factory.make_name('agent-name')
        self.client.post(
            reverse('nodes_handler'),
            {'op': 'acquire', 'agent_name': agent_name})
        node = Node.objects.get(system_id=node.system_id)
        self.assertEqual(agent_name, node.agent_name)

    def test_POST_acquire_agent_name_defaults_to_empty_string(self):
        available_status = NODE_STATUS.READY
        agent_name = factory.make_name('agent-name')
        node = factory.make_Node(
            status=available_status, owner=None, agent_name=agent_name,
            with_boot_disk=True)
        self.client.post(reverse('nodes_handler'), {'op': 'acquire'})
        node = Node.objects.get(system_id=node.system_id)
        self.assertEqual('', node.agent_name)

    def test_POST_acquire_fails_if_no_node_present(self):
        # The "acquire" operation returns a Conflict error if no nodes
        # are available.
        response = self.client.post(
            reverse('nodes_handler'), {'op': 'acquire'})
        # Fails with Conflict error: resource can't satisfy request.
        self.assertEqual(http.client.CONFLICT, response.status_code)

    def test_POST_acquire_failure_shows_no_constraints_if_none_given(self):
        response = self.client.post(
            reverse('nodes_handler'), {'op': 'acquire'})
        self.assertEqual(http.client.CONFLICT, response.status_code)
        self.assertEqual(
            "No node available.",
            response.content.decode(settings.DEFAULT_CHARSET))

    def test_POST_acquire_failure_shows_constraints_if_given(self):
        hostname = factory.make_name('host')
        response = self.client.post(
            reverse('nodes_handler'), {
                'op': 'acquire',
                'name': hostname,
            })
        expected_response = (
            "No available node matches constraints: name=%s" % hostname
        ).encode(settings.DEFAULT_CHARSET)
        self.assertEqual(http.client.CONFLICT, response.status_code)
        self.assertEqual(expected_response, response.content)

    def test_POST_acquire_ignores_already_allocated_node(self):
        factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=factory.make_User(),
            with_boot_disk=True)
        response = self.client.post(
            reverse('nodes_handler'), {'op': 'acquire'})
        self.assertEqual(http.client.CONFLICT, response.status_code)

    def test_POST_acquire_chooses_candidate_matching_constraint(self):
        # If "acquire" is passed a constraint, it will go for a node
        # matching that constraint even if there's tons of other nodes
        # available.
        # (Creating lots of nodes here to minimize the chances of this
        # passing by accident).
        available_nodes = [
            factory.make_Node(
                status=NODE_STATUS.READY, owner=None, with_boot_disk=True)
            for counter in range(20)]
        desired_node = random.choice(available_nodes)
        response = self.client.post(reverse('nodes_handler'), {
            'op': 'acquire',
            'name': desired_node.hostname,
        })
        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))
        domain_name = desired_node.nodegroup.name
        self.assertEqual(
            "%s.%s" % (desired_node.hostname, domain_name),
            parsed_result['hostname'])

    def test_POST_acquire_would_rather_fail_than_disobey_constraint(self):
        # If "acquire" is passed a constraint, it won't return a node
        # that does not meet that constraint.  Even if it means that it
        # can't meet the request.
        factory.make_Node(
            status=NODE_STATUS.READY, owner=None, with_boot_disk=True)
        desired_node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=factory.make_User())
        response = self.client.post(reverse('nodes_handler'), {
            'op': 'acquire',
            'name': desired_node.system_id,
        })
        self.assertEqual(http.client.CONFLICT, response.status_code)

    def test_POST_acquire_ignores_unknown_constraint(self):
        node = factory.make_Node(
            status=NODE_STATUS.READY, owner=None, with_boot_disk=True)
        response = self.client.post(reverse('nodes_handler'), {
            'op': 'acquire',
            factory.make_string(): factory.make_string(),
        })
        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))
        self.assertEqual(node.system_id, parsed_result['system_id'])

    def test_POST_acquire_allocates_node_by_name(self):
        # Positive test for name constraint.
        # If a name constraint is given, "acquire" attempts to allocate
        # a node of that name.
        node = factory.make_Node(
            status=NODE_STATUS.READY, owner=None, with_boot_disk=True)
        response = self.client.post(reverse('nodes_handler'), {
            'op': 'acquire',
            'name': node.hostname,
        })
        self.assertEqual(http.client.OK, response.status_code)
        nodegroup = NodeGroup.objects.ensure_master()
        domain_name = nodegroup.name
        self.assertEqual(
            "%s.%s" % (node.hostname, domain_name),
            json.loads(
                response.content.decode(settings.DEFAULT_CHARSET))['hostname'])

    def test_POST_acquire_treats_unknown_name_as_resource_conflict(self):
        # A name constraint naming an unknown node produces a resource
        # conflict: most likely the node existed but has changed or
        # disappeared.
        # Certainly it's not a 404, since the resource named in the URL
        # is "nodes/," which does exist.
        factory.make_Node(
            status=NODE_STATUS.READY, owner=None, with_boot_disk=True)
        response = self.client.post(reverse('nodes_handler'), {
            'op': 'acquire',
            'name': factory.make_string(),
        })
        self.assertEqual(http.client.CONFLICT, response.status_code)

    def test_POST_acquire_allocates_node_by_arch(self):
        # Asking for a particular arch acquires a node with that arch.
        arch = make_usable_architecture(self)
        node = factory.make_Node(
            status=NODE_STATUS.READY, architecture=arch, with_boot_disk=True)
        response = self.client.post(reverse('nodes_handler'), {
            'op': 'acquire',
            'arch': arch,
        })
        self.assertEqual(http.client.OK, response.status_code)
        response_json = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))
        self.assertEqual(node.architecture, response_json['architecture'])

    def test_POST_acquire_treats_unknown_arch_as_bad_request(self):
        # Asking for an unknown arch returns an HTTP "400 Bad Request"
        factory.make_Node(
            status=NODE_STATUS.READY, with_boot_disk=True)
        response = self.client.post(reverse('nodes_handler'), {
            'op': 'acquire',
            'arch': 'sparc',
        })
        self.assertEqual(http.client.BAD_REQUEST, response.status_code)

    def test_POST_acquire_allocates_node_by_cpu(self):
        # Asking for enough cpu acquires a node with at least that.
        node = factory.make_Node(
            status=NODE_STATUS.READY, cpu_count=3, with_boot_disk=True)
        response = self.client.post(reverse('nodes_handler'), {
            'op': 'acquire',
            'cpu_count': 2,
        })
        self.assertResponseCode(http.client.OK, response)
        response_json = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))
        self.assertEqual(node.system_id, response_json['system_id'])

    def test_POST_acquire_allocates_node_by_float_cpu(self):
        # Asking for a needlessly precise number of cpus works.
        node = factory.make_Node(
            status=NODE_STATUS.READY, cpu_count=1, with_boot_disk=True)
        response = self.client.post(reverse('nodes_handler'), {
            'op': 'acquire',
            'cpu_count': '1.0',
        })
        self.assertResponseCode(http.client.OK, response)
        response_json = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))
        self.assertEqual(node.system_id, response_json['system_id'])

    def test_POST_acquire_fails_with_invalid_cpu(self):
        # Asking for an invalid amount of cpu returns a bad request.
        factory.make_Node(
            status=NODE_STATUS.READY, with_boot_disk=True)
        response = self.client.post(reverse('nodes_handler'), {
            'op': 'acquire',
            'cpu_count': 'plenty',
        })
        self.assertResponseCode(http.client.BAD_REQUEST, response)

    def test_POST_acquire_allocates_node_by_mem(self):
        # Asking for enough memory acquires a node with at least that.
        node = factory.make_Node(
            status=NODE_STATUS.READY, memory=1024, with_boot_disk=True)
        response = self.client.post(reverse('nodes_handler'), {
            'op': 'acquire',
            'mem': 1024,
        })
        self.assertResponseCode(http.client.OK, response)
        response_json = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))
        self.assertEqual(node.system_id, response_json['system_id'])

    def test_POST_acquire_fails_with_invalid_mem(self):
        # Asking for an invalid amount of memory returns a bad request.
        factory.make_Node(
            status=NODE_STATUS.READY, with_boot_disk=True)
        response = self.client.post(reverse('nodes_handler'), {
            'op': 'acquire',
            'mem': 'bags',
        })
        self.assertResponseCode(http.client.BAD_REQUEST, response)

    def test_POST_acquire_allocates_node_by_tags(self):
        node = factory.make_Node(
            status=NODE_STATUS.READY, with_boot_disk=True)
        node_tag_names = ["fast", "stable", "cute"]
        node.tags = [factory.make_Tag(t) for t in node_tag_names]
        # Legacy call using comma-separated tags.
        response = self.client.post(reverse('nodes_handler'), {
            'op': 'acquire',
            'tags': ['fast', 'stable'],
        })
        self.assertResponseCode(http.client.OK, response)
        response_json = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))
        self.assertItemsEqual(node_tag_names, response_json['tag_names'])

    def test_POST_acquire_allocates_node_by_negated_tags(self):
        tagged_node = factory.make_Node(
            status=NODE_STATUS.READY, with_boot_disk=True)
        partially_tagged_node = factory.make_Node(
            status=NODE_STATUS.READY, with_boot_disk=True)
        node_tag_names = ["fast", "stable", "cute"]
        tags = [factory.make_Tag(t) for t in node_tag_names]
        tagged_node.tags = tags
        partially_tagged_node.tags = tags[:-1]
        # Legacy call using comma-separated tags.
        response = self.client.post(reverse('nodes_handler'), {
            'op': 'acquire',
            'not_tags': ['cute']
        })
        self.assertResponseCode(http.client.OK, response)
        response_json = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))
        self.assertEqual(
            partially_tagged_node.system_id,
            response_json['system_id'])
        self.assertItemsEqual(
            node_tag_names[:-1], response_json['tag_names'])

    def test_POST_acquire_allocates_node_by_zone(self):
        factory.make_Node(
            status=NODE_STATUS.READY, with_boot_disk=True)
        zone = factory.make_Zone()
        node = factory.make_Node(
            status=NODE_STATUS.READY, zone=zone, with_boot_disk=True)
        response = self.client.post(reverse('nodes_handler'), {
            'op': 'acquire',
            'zone': zone.name,
        })
        self.assertResponseCode(http.client.OK, response)
        response_json = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))
        self.assertEqual(node.system_id, response_json['system_id'])

    def test_POST_acquire_allocates_node_by_zone_fails_if_no_node(self):
        factory.make_Node(
            status=NODE_STATUS.READY, with_boot_disk=True)
        zone = factory.make_Zone()
        response = self.client.post(reverse('nodes_handler'), {
            'op': 'acquire',
            'zone': zone.name,
        })
        self.assertResponseCode(http.client.CONFLICT, response)

    def test_POST_acquire_rejects_unknown_zone(self):
        response = self.client.post(reverse('nodes_handler'), {
            'op': 'acquire',
            'zone': factory.make_name('zone'),
        })
        self.assertEqual(http.client.BAD_REQUEST, response.status_code)

    def test_POST_acquire_allocates_node_by_tags_comma_separated(self):
        node = factory.make_Node(
            status=NODE_STATUS.READY, with_boot_disk=True)
        node_tag_names = ["fast", "stable", "cute"]
        node.tags = [factory.make_Tag(t) for t in node_tag_names]
        # Legacy call using comma-separated tags.
        response = self.client.post(reverse('nodes_handler'), {
            'op': 'acquire',
            'tags': 'fast, stable',
        })
        self.assertResponseCode(http.client.OK, response)
        response_json = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))
        self.assertItemsEqual(node_tag_names, response_json['tag_names'])

    def test_POST_acquire_allocates_node_by_tags_space_separated(self):
        node = factory.make_Node(
            status=NODE_STATUS.READY, with_boot_disk=True)
        node_tag_names = ["fast", "stable", "cute"]
        node.tags = [factory.make_Tag(t) for t in node_tag_names]
        # Legacy call using space-separated tags.
        response = self.client.post(reverse('nodes_handler'), {
            'op': 'acquire',
            'tags': 'fast stable',
        })
        self.assertResponseCode(http.client.OK, response)
        response_json = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))
        self.assertItemsEqual(node_tag_names, response_json['tag_names'])

    def test_POST_acquire_allocates_node_by_tags_comma_space_separated(self):
        node = factory.make_Node(
            status=NODE_STATUS.READY, with_boot_disk=True)
        node_tag_names = ["fast", "stable", "cute"]
        node.tags = [factory.make_Tag(t) for t in node_tag_names]
        # Legacy call using comma-and-space-separated tags.
        response = self.client.post(reverse('nodes_handler'), {
            'op': 'acquire',
            'tags': 'fast, stable cute',
        })
        self.assertResponseCode(http.client.OK, response)
        response_json = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))
        self.assertItemsEqual(node_tag_names, response_json['tag_names'])

    def test_POST_acquire_allocates_node_by_tags_mixed_input(self):
        node = factory.make_Node(
            status=NODE_STATUS.READY, with_boot_disk=True)
        node_tag_names = ["fast", "stable", "cute"]
        node.tags = [factory.make_Tag(t) for t in node_tag_names]
        # Mixed call using comma-separated tags in a list.
        response = self.client.post(reverse('nodes_handler'), {
            'op': 'acquire',
            'tags': ['fast, stable', 'cute'],
        })
        self.assertResponseCode(http.client.OK, response)
        response_json = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))
        self.assertItemsEqual(node_tag_names, response_json['tag_names'])

    def test_POST_acquire_allocates_node_by_storage(self):
        """Storage label is returned alongside node data"""
        node = factory.make_Node(
            status=NODE_STATUS.READY, with_boot_disk=False)
        # The ID may always be '1', which won't be interesting for testing.
        for _ in range(1, random.choice([1, 3, 5])):
            factory.make_PhysicalBlockDevice()
        factory.make_PhysicalBlockDevice(
            node=node, size=11 * (1000 ** 3), tags=['ssd'])
        response = self.client.post(reverse('nodes_handler'), {
            'op': 'acquire',
            'storage': 'needed:10(ssd)',
        })
        self.assertResponseCode(http.client.OK, response)
        response_json = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))
        device_id = response_json['physicalblockdevice_set'][0]['id']
        constraint_map = response_json.get('constraint_map')
        constraint_name = constraint_map[str(device_id)]
        self.assertItemsEqual(constraint_name, 'needed')
        constraints = response_json['constraints_by_type']
        self.expectThat(constraints, Contains('storage'))
        self.expectThat(constraints['storage'], Contains('needed'))
        self.expectThat(constraints['storage']['needed'], Contains(device_id))
        self.expectThat(constraints, Not(Contains('verbose_storage')))

    def test_POST_acquire_allocates_node_by_storage_with_verbose(self):
        """Storage label is returned alongside node data"""
        node = factory.make_Node(
            status=NODE_STATUS.READY, with_boot_disk=False)
        # The ID may always be '1', which won't be interesting for testing.
        for _ in range(1, random.choice([1, 3, 5])):
            factory.make_PhysicalBlockDevice()
        factory.make_PhysicalBlockDevice(
            node=node, size=11 * (1000 ** 3), tags=['ssd'])
        response = self.client.post(reverse('nodes_handler'), {
            'op': 'acquire',
            'storage': 'needed:10(ssd)',
            'verbose': 'true',
        })
        self.assertResponseCode(http.client.OK, response)
        response_json = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))
        device_id = response_json['physicalblockdevice_set'][0]['id']
        constraint_map = response_json.get('constraint_map')
        constraint_name = constraint_map[str(device_id)]
        self.assertItemsEqual(constraint_name, 'needed')
        constraints = response_json['constraints_by_type']
        self.expectThat(constraints, Contains('storage'))
        self.expectThat(constraints['storage'], Contains('needed'))
        self.expectThat(constraints['storage']['needed'], Contains(device_id))
        verbose_storage = constraints.get('verbose_storage')
        self.expectThat(verbose_storage, Contains(str(node.id)))
        self.expectThat(
            verbose_storage[str(node.id)], Equals(constraint_map))

    def test_POST_acquire_allocates_node_by_interfaces(self):
        """Interface label is returned alongside node data"""
        fabric = factory.make_Fabric('ubuntu')
        # The ID may always be '1', which won't be interesting for testing.
        for _ in range(1, random.choice([1, 3, 5])):
            factory.make_Interface()
        node = factory.make_Node_with_Interface_on_Subnet(
            status=NODE_STATUS.READY, fabric=fabric)
        iface = node.get_boot_interface()
        response = self.client.post(reverse('nodes_handler'), {
            'op': 'acquire',
            'interfaces': 'needed:fabric=ubuntu',
        })
        self.assertResponseCode(http.client.OK, response)
        response_json = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))
        self.expectThat(
            response_json['substatus'], Equals(NODE_STATUS.ALLOCATED))
        constraints = response_json['constraints_by_type']
        self.expectThat(constraints, Contains('interfaces'))
        interfaces = constraints.get('interfaces')
        self.expectThat(interfaces, Contains('needed'))
        self.expectThat(interfaces['needed'], Contains(iface.id))
        self.expectThat(constraints, Not(Contains('verbose_interfaces')))

    def test_POST_acquire_allocates_node_by_interfaces_dry_run_with_verbose(
            self):
        """Interface label is returned alongside node data"""
        fabric = factory.make_Fabric('ubuntu')
        # The ID may always be '1', which won't be interesting for testing.
        for _ in range(1, random.choice([1, 3, 5])):
            factory.make_Interface()
        node = factory.make_Node_with_Interface_on_Subnet(
            status=NODE_STATUS.READY, fabric=fabric)
        iface = node.get_boot_interface()
        response = self.client.post(reverse('nodes_handler'), {
            'op': 'acquire',
            'interfaces': 'needed:fabric=ubuntu',
            'verbose': 'true',
            'dry_run': 'true',
        })
        self.assertResponseCode(http.client.OK, response)
        response_json = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))
        self.expectThat(
            response_json['substatus'], Equals(NODE_STATUS.READY))
        # Check that we still got the verbose constraints output even if
        # it was a dry run.
        constraints = response_json['constraints_by_type']
        self.expectThat(constraints, Contains('interfaces'))
        interfaces = constraints.get('interfaces')
        self.expectThat(interfaces, Contains('needed'))
        self.expectThat(interfaces['needed'], Contains(iface.id))
        verbose_interfaces = constraints.get('verbose_interfaces')
        self.expectThat(
            verbose_interfaces['needed'], Contains(str(node.id)))
        self.expectThat(
            verbose_interfaces['needed'][str(node.id)],
            Contains(iface.id))

    def test_POST_acquire_allocates_node_by_interfaces_with_verbose(self):
        """Interface label is returned alongside node data"""
        fabric = factory.make_Fabric('ubuntu')
        # The ID may always be '1', which won't be interesting for testing.
        for _ in range(1, random.choice([1, 3, 5])):
            factory.make_Interface()
        factory.make_Node()
        node = factory.make_Node_with_Interface_on_Subnet(
            status=NODE_STATUS.READY, fabric=fabric)
        iface = node.get_boot_interface()
        response = self.client.post(reverse('nodes_handler'), {
            'op': 'acquire',
            'interfaces': 'needed:fabric=ubuntu',
            'verbose': 'true',
        })
        self.assertResponseCode(http.client.OK, response)
        response_json = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))
        constraints = response_json['constraints_by_type']
        self.expectThat(constraints, Contains('interfaces'))
        interfaces = constraints.get('interfaces')
        self.expectThat(interfaces, Contains('needed'))
        self.expectThat(interfaces['needed'], Equals([iface.id]))
        verbose_interfaces = constraints.get('verbose_interfaces')
        self.expectThat(
            verbose_interfaces['needed'], Contains(str(node.id)))
        self.expectThat(
            verbose_interfaces['needed'][str(node.id)],
            Contains(iface.id))

    def test_POST_acquire_fails_without_all_tags(self):
        # Asking for particular tags does not acquire if no node has all tags.
        node1 = factory.make_Node(
            status=NODE_STATUS.READY, with_boot_disk=True)
        node1.tags = [factory.make_Tag(t) for t in ("fast", "stable", "cute")]
        node2 = factory.make_Node(
            status=NODE_STATUS.READY, with_boot_disk=True)
        node2.tags = [factory.make_Tag("cheap")]
        response = self.client.post(reverse('nodes_handler'), {
            'op': 'acquire',
            'tags': 'fast, cheap',
        })
        self.assertResponseCode(http.client.CONFLICT, response)

    def test_POST_acquire_fails_with_unknown_tags(self):
        # Asking for a tag that does not exist gives a specific error.
        node = factory.make_Node(
            status=NODE_STATUS.READY, with_boot_disk=True)
        node.tags = [factory.make_Tag("fast")]
        response = self.client.post(reverse('nodes_handler'), {
            'op': 'acquire',
            'tags': 'fast, hairy, boo',
        })
        self.assertEqual(http.client.BAD_REQUEST, response.status_code)
        response_dict = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))
        # The order in which "foo" and "bar" appear is not guaranteed.
        self.assertIn("No such tag(s):", response_dict['tags'][0])
        self.assertIn("'hairy'", response_dict['tags'][0])
        self.assertIn("'boo'", response_dict['tags'][0])

    def test_POST_acquire_allocates_node_connected_to_routers(self):
        macs = [factory.make_MAC() for counter in range(3)]
        node = factory.make_Node(
            routers=macs, status=NODE_STATUS.READY, with_boot_disk=True)
        factory.make_Node(routers=[], with_boot_disk=True)

        response = self.client.post(reverse('nodes_handler'), {
            'op': 'acquire',
            'connected_to': [macs[2].get_raw(), macs[0].get_raw()],
        })

        self.assertResponseCode(http.client.OK, response)
        response_json = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))
        self.assertEqual(node.system_id, response_json['system_id'])

    def test_POST_acquire_allocates_node_not_connected_to_routers(self):
        macs = [MAC('aa:bb:cc:dd:ee:ff'), MAC('00:11:22:33:44:55')]
        factory.make_Node(
            routers=macs, status=NODE_STATUS.READY, with_boot_disk=True)
        factory.make_Node(
            routers=[MAC('11:11:11:11:11:11')], status=NODE_STATUS.READY,
            with_boot_disk=True)
        node = factory.make_Node(
            status=NODE_STATUS.READY, with_boot_disk=True)

        response = self.client.post(reverse('nodes_handler'), {
            'op': 'acquire',
            'not_connected_to': ['aa:bb:cc:dd:ee:ff', '11:11:11:11:11:11'],
        })

        self.assertResponseCode(http.client.OK, response)
        response_json = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))
        self.assertEqual(node.system_id, response_json['system_id'])

    def test_POST_acquire_allocates_node_by_network(self):
        subnets = [
            factory.make_Subnet()
            for _ in range(5)
        ]
        nodes = [
            factory.make_Node_with_Interface_on_Subnet(
                status=NODE_STATUS.READY, with_boot_disk=True, subnet=subnet)
            for subnet in subnets
        ]
        # We'll make it so that only the node and subnet at this index will
        # match the request.
        pick = 2

        response = self.client.post(reverse('nodes_handler'), {
            'op': 'acquire',
            'networks': [subnets[pick].name],
        })

        self.assertResponseCode(http.client.OK, response)
        response_json = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))
        self.assertEqual(
            nodes[pick].system_id, response_json['system_id'])

    def test_POST_acquire_allocates_node_by_not_network(self):
        subnets = [
            factory.make_Subnet()
            for _ in range(5)
        ]
        for subnet in subnets:
            factory.make_Node_with_Interface_on_Subnet(
                status=NODE_STATUS.READY, with_boot_disk=True, subnet=subnet)
        right_node = factory.make_Node_with_Interface_on_Subnet(
            status=NODE_STATUS.READY, with_boot_disk=True)

        response = self.client.post(reverse('nodes_handler'), {
            'op': 'acquire',
            'not_networks': [subnet.name for subnet in subnets],
        })

        self.assertResponseCode(http.client.OK, response)
        response_json = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))
        self.assertEqual(right_node.system_id, response_json['system_id'])

    def test_POST_acquire_obeys_not_in_zone(self):
        # Zone we don't want to acquire from.
        not_in_zone = factory.make_Zone()
        nodes = [
            factory.make_Node(
                status=NODE_STATUS.READY, zone=not_in_zone,
                with_boot_disk=True)
            for _ in range(5)
        ]
        # Pick a node in the middle to avoid false negatives if acquire()
        # always tries the oldest, or the newest, node first.
        eligible_node = nodes[2]
        eligible_node.zone = factory.make_Zone()
        eligible_node.save()

        response = self.client.post(
            reverse('nodes_handler'),
            {
                'op': 'acquire',
                'not_in_zone': [not_in_zone.name],
            })
        self.assertEqual(http.client.OK, response.status_code)
        system_id = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))['system_id']
        self.assertEqual(eligible_node.system_id, system_id)

    def test_POST_acquire_sets_a_token(self):
        # "acquire" should set the Token being used in the request on
        # the Node that is allocated.
        available_status = NODE_STATUS.READY
        node = factory.make_Node(
            status=available_status, owner=None, with_boot_disk=True)
        self.client.post(reverse('nodes_handler'), {'op': 'acquire'})
        node = Node.objects.get(system_id=node.system_id)
        oauth_key = self.client.token.key
        self.assertEqual(oauth_key, node.token.key)

    def test_POST_accept_gets_node_out_of_declared_state(self):
        # This will change when we add provisioning.  Until then,
        # acceptance gets a node straight to Ready state.
        self.patch_autospec(Node, 'start_transition_monitor')
        self.become_admin()
        target_state = NODE_STATUS.COMMISSIONING

        node = factory.make_Node(status=NODE_STATUS.NEW)
        response = self.client.post(
            reverse('nodes_handler'),
            {'op': 'accept', 'nodes': [node.system_id]})
        accepted_ids = [
            accepted_node['system_id']
            for accepted_node in json.loads(
                response.content.decode(settings.DEFAULT_CHARSET))]
        self.assertEqual(
            (http.client.OK, [node.system_id]),
            (response.status_code, accepted_ids))
        self.assertEqual(target_state, reload_object(node).status)

    def test_POST_quietly_accepts_empty_set(self):
        response = self.client.post(reverse('nodes_handler'), {'op': 'accept'})
        self.assertEqual(
            (http.client.OK.value, "[]"),
            (response.status_code,
             response.content.decode(settings.DEFAULT_CHARSET)))

    def test_POST_accept_rejects_impossible_state_changes(self):
        self.become_admin()
        acceptable_states = set([
            NODE_STATUS.NEW,
            NODE_STATUS.COMMISSIONING,
            NODE_STATUS.READY,
        ])
        unacceptable_states = (
            set(map_enum(NODE_STATUS).values()) - acceptable_states)
        nodes = {
            status: factory.make_Node(status=status)
            for status in unacceptable_states}
        responses = {
            status: self.client.post(
                reverse('nodes_handler'), {
                    'op': 'accept',
                    'nodes': [node.system_id],
                })
            for status, node in nodes.items()}
        # All of these attempts are rejected with Conflict errors.
        self.assertEqual(
            {status: http.client.CONFLICT for status in unacceptable_states},
            {
                status: responses[status].status_code
                for status in unacceptable_states})

        for status, response in responses.items():
            # Each error describes the problem.
            self.assertIn(
                "Cannot accept node enlistment",
                response.content.decode(settings.DEFAULT_CHARSET))
            # Each error names the node it encountered a problem with.
            self.assertIn(
                nodes[status].system_id.encode(
                    settings.DEFAULT_CHARSET), response.content)
            # Each error names the node state that the request conflicted
            # with.
            self.assertIn(
                NODE_STATUS_CHOICES_DICT[status].encode(
                    settings.DEFAULT_CHARSET),
                response.content)

    def test_POST_accept_fails_if_node_does_not_exist(self):
        self.become_admin()
        # Make sure there is a node, it just isn't the one being accepted
        factory.make_Node()
        node_id = factory.make_string()
        response = self.client.post(
            reverse('nodes_handler'), {'op': 'accept', 'nodes': [node_id]})
        self.assertEqual(
            (http.client.BAD_REQUEST,
             ("Unknown node(s): %s." % node_id).encode(
                 settings.DEFAULT_CHARSET)),
            (response.status_code, response.content))

    def test_POST_accept_fails_for_device(self):
        self.become_admin()
        factory.make_Node(installable=False)
        node_id = factory.make_string()
        response = self.client.post(
            reverse('nodes_handler'), {'op': 'accept', 'nodes': [node_id]})
        self.assertEqual(
            (http.client.BAD_REQUEST,
             ("Unknown node(s): %s." % node_id).encode(
                 settings.DEFAULT_CHARSET)),
            (response.status_code, response.content))

    def test_POST_accept_accepts_multiple_nodes(self):
        # This will change when we add provisioning.  Until then,
        # acceptance gets a node straight to Ready state.
        self.patch_autospec(Node, 'start_transition_monitor')
        self.become_admin()
        target_state = NODE_STATUS.COMMISSIONING

        nodes = [
            factory.make_Node(status=NODE_STATUS.NEW)
            for counter in range(2)]
        node_ids = [node.system_id for node in nodes]
        response = self.client.post(reverse('nodes_handler'), {
            'op': 'accept',
            'nodes': node_ids,
        })
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(
            [target_state] * len(nodes),
            [reload_object(node).status for node in nodes])

    def test_POST_accept_returns_actually_accepted_nodes(self):
        self.patch_autospec(Node, 'start_transition_monitor')
        self.become_admin()
        acceptable_nodes = [
            factory.make_Node(status=NODE_STATUS.NEW)
            for counter in range(2)
        ]
        accepted_node = factory.make_Node(status=NODE_STATUS.READY)
        nodes = acceptable_nodes + [accepted_node]
        response = self.client.post(reverse('nodes_handler'), {
            'op': 'accept',
            'nodes': [node.system_id for node in nodes],
        })
        self.assertEqual(http.client.OK, response.status_code)
        accepted_ids = [
            node['system_id']
            for node in json.loads(
                response.content.decode(settings.DEFAULT_CHARSET))]
        self.assertItemsEqual(
            [node.system_id for node in acceptable_nodes], accepted_ids)
        self.assertNotIn(accepted_node.system_id, accepted_ids)

    def test_POST_quietly_releases_empty_set(self):
        response = self.client.post(
            reverse('nodes_handler'), {'op': 'release'})
        self.assertEqual(
            (http.client.OK.value, "[]"),
            (response.status_code,
             response.content.decode(settings.DEFAULT_CHARSET)))

    def test_POST_release_ignores_devices(self):
        node_ids = {
            factory.make_Node(installable=False).system_id
            for _ in range(3)
        }
        response = self.client.post(
            reverse('nodes_handler'), {
                'op': 'release',
                'nodes': node_ids
            })
        self.assertEqual(http.client.BAD_REQUEST, response.status_code)

    def test_POST_release_rejects_request_from_unauthorized_user(self):
        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=factory.make_User())
        response = self.client.post(
            reverse('nodes_handler'), {
                'op': 'release',
                'nodes': [node.system_id],
            })
        self.assertEqual(http.client.FORBIDDEN, response.status_code)
        self.assertEqual(NODE_STATUS.ALLOCATED, reload_object(node).status)

    def test_POST_release_fails_if_nodes_do_not_exist(self):
        # Make sure there is a node, it just isn't among the ones to release
        factory.make_Node()
        node_ids = {factory.make_string() for _ in range(5)}
        response = self.client.post(
            reverse('nodes_handler'), {
                'op': 'release',
                'nodes': node_ids
            })
        # Awkward parsing, but the order may vary and it's not JSON
        s = response.content.decode(settings.DEFAULT_CHARSET)
        returned_ids = s[s.find(':') + 2:s.rfind('.')].split(', ')
        self.assertEqual(http.client.BAD_REQUEST, response.status_code)
        self.assertIn(
            "Unknown node(s): ",
            response.content.decode(settings.DEFAULT_CHARSET))
        self.assertItemsEqual(node_ids, returned_ids)

    def test_POST_release_forbidden_if_user_cannot_edit_node(self):
        # Create a bunch of nodes, owned by the logged in user
        node_ids = {
            factory.make_Node(
                status=NODE_STATUS.ALLOCATED,
                owner=self.logged_in_user).system_id
            for _ in range(3)
        }
        # And one with no owner
        another_node = factory.make_Node(status=NODE_STATUS.RESERVED)
        node_ids.add(another_node.system_id)
        response = self.client.post(
            reverse('nodes_handler'), {
                'op': 'release',
                'nodes': node_ids
            })
        expected_response = (
            "You don't have the required permission to release the following "
            "node(s): %s." % another_node.system_id).encode(
            settings.DEFAULT_CHARSET)
        self.assertEqual(
            (http.client.FORBIDDEN.value, expected_response),
            (response.status_code, response.content))

    def test_POST_release_rejects_impossible_state_changes(self):
        acceptable_states = set(
            RELEASABLE_STATUSES + [NODE_STATUS.READY])
        unacceptable_states = (
            set(map_enum(NODE_STATUS).values()) - acceptable_states)
        owner = self.logged_in_user
        nodes = [
            factory.make_Node(status=status, owner=owner)
            for status in unacceptable_states]
        response = self.client.post(
            reverse('nodes_handler'), {
                'op': 'release',
                'nodes': [node.system_id for node in nodes],
            })
        # Awkward parsing again, because a string is returned, not JSON
        expected = [
            "%s ('%s')" % (node.system_id, node.display_status())
            for node in nodes
            if node.status not in acceptable_states]
        s = response.content.decode(settings.DEFAULT_CHARSET)
        returned = s[s.rfind(':') + 2:s.rfind('.')].split(', ')
        self.assertEqual(http.client.CONFLICT, response.status_code)
        self.assertIn(
            "Node(s) cannot be released in their current state:",
            response.content.decode(settings.DEFAULT_CHARSET))
        self.assertItemsEqual(expected, returned)

    def test_POST_release_returns_modified_nodes(self):
        owner = self.logged_in_user
        acceptable_states = [NODE_STATUS.READY] + RELEASABLE_STATUSES
        nodes = [
            factory.make_Node(status=status, owner=owner)
            for status in acceptable_states
        ]
        response = self.client.post(
            reverse('nodes_handler'), {
                'op': 'release',
                'nodes': [node.system_id for node in nodes],
            })
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))
        self.assertEqual(http.client.OK, response.status_code)
        # The first node is READY, so shouldn't be touched.
        self.assertItemsEqual(
            [node.system_id for node in nodes[1:]],
            parsed_result)

    def test_POST_release_erases_disks_when_enabled(self):
        owner = self.logged_in_user
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED, owner=owner)
        Config.objects.set_config(
            'enable_disk_erasing_on_release', True)
        response = self.client.post(
            reverse('nodes_handler'), {
                'op': 'release',
                'nodes': [node.system_id],
            })
        self.assertEqual(http.client.OK.value, response.status_code, response)
        node = reload_object(node)
        self.assertEqual(NODE_STATUS.DISK_ERASING, node.status)

    def test_handle_when_URL_is_repeated(self):
        # bin/maas-enlist (in the maas-enlist package) has a bug where the
        # path it uses is doubled up. This was not discovered previously
        # because the API URL patterns were not anchored (see bug 1131323).
        # For compatibility, MAAS will handle requests to obviously incorrect
        # paths. It does *not* redirect because (a) it's not clear that curl
        # (used by maas-enlist) supports HTTP 307 redirects, which are needed
        # to support redirecting POSTs, and (b) curl does not follow redirects
        # by default anyway.
        architecture = make_usable_architecture(self)
        response = self.client.post(
            '/api/1.0/nodes/MAAS/api/1.0/nodes/',
            {
                'op': 'new',
                'autodetect_nodegroup': '1',
                'hostname': factory.make_string(),
                'architecture': architecture,
                'mac_addresses': ['aa:bb:cc:dd:ee:ff'],
            })
        self.assertEqual(http.client.OK.value, response.status_code)
        system_id = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))['system_id']
        nodes = Node.objects.filter(system_id=system_id)
        self.assertIsNotNone(get_one(nodes))

    def test_POST_set_zone_sets_zone_on_nodes(self):
        self.become_admin()
        node = factory.make_Node()
        zone = factory.make_Zone()
        response = self.client.post(
            reverse('nodes_handler'),
            {
                'op': 'set_zone',
                'nodes': [node.system_id],
                'zone': zone.name
            })
        self.assertEqual(http.client.OK, response.status_code)
        node = reload_object(node)
        self.assertEqual(zone, node.zone)

    def test_POST_set_zone_does_not_affect_other_nodes(self):
        self.become_admin()
        node = factory.make_Node()
        original_zone = node.zone
        response = self.client.post(
            reverse('nodes_handler'),
            {
                'op': 'set_zone',
                'nodes': [factory.make_Node().system_id],
                'zone': factory.make_Zone().name
            })
        self.assertEqual(http.client.OK, response.status_code)
        node = reload_object(node)
        self.assertEqual(original_zone, node.zone)

    def test_POST_set_zone_requires_admin(self):
        node = factory.make_Node(owner=self.logged_in_user)
        original_zone = node.zone
        response = self.client.post(
            reverse('nodes_handler'),
            {
                'op': 'set_zone',
                'nodes': [node.system_id],
                'zone': factory.make_Zone().name
            })
        self.assertEqual(http.client.FORBIDDEN, response.status_code)
        node = reload_object(node)
        self.assertEqual(original_zone, node.zone)

    def test_GET_power_parameters_requires_admin(self):
        response = self.client.get(
            reverse('nodes_handler'),
            {
                'op': 'power_parameters',
            })
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content)

    def test_GET_power_parameters_without_ids_does_not_filter(self):
        self.become_admin()
        nodes = [
            factory.make_Node(
                power_parameters=factory.make_name("power_parameters"))
            for _ in range(0, 3)
        ]
        response = self.client.get(
            reverse('nodes_handler'),
            {
                'op': 'power_parameters',
            })
        self.assertEqual(
            http.client.OK, response.status_code, response.content)
        parsed = json.loads(response.content.decode(settings.DEFAULT_CHARSET))
        expected = {
            node.system_id: node.power_parameters
            for node in nodes
        }
        self.assertEqual(expected, parsed)

    def test_GET_power_parameters_with_ids_filters(self):
        self.become_admin()
        nodes = [
            factory.make_Node(
                power_parameters=factory.make_name("power_parameters"))
            for _ in range(0, 6)
        ]
        expected_nodes = random.sample(nodes, 3)
        response = self.client.get(
            reverse('nodes_handler'),
            {
                'op': 'power_parameters',
                'id': [node.system_id for node in expected_nodes],
            })
        self.assertEqual(
            http.client.OK, response.status_code, response.content)
        parsed = json.loads(response.content.decode(settings.DEFAULT_CHARSET))
        expected = {
            node.system_id: node.power_parameters
            for node in expected_nodes
        }
        self.assertEqual(expected, parsed)


class TestDeploymentStatus(APITestCase):
    """Tests for /api/1.0/nodes/?op=deployment_status."""

    endpoint = reverse('nodes_handler')

    def test_GET_returns_single_matching_node(self):
        owned_node = factory.make_Node(
            owner=self.logged_in_user, status=NODE_STATUS.DEPLOYED)
        response = self.client.get(
            self.endpoint,
            {'op': 'deployment_status', 'nodes': [owned_node.system_id]})
        self.assertEqual(
            http.client.OK, response.status_code, response.content)
        expected = {owned_node.system_id: "Deployed"}
        self.assertEqual(
            expected, json.loads(
                response.content.decode(settings.DEFAULT_CHARSET)))

    def test_GET_returns_multiple_matching_nodes(self):
        nodes = []
        expected = dict()
        for _ in range(3):
            node = factory.make_Node(
                owner=self.logged_in_user, status=NODE_STATUS.DEPLOYED)
            nodes.append(node)
            expected[node.system_id] = "Deployed"
        ids = [n.system_id for n in nodes]
        response = self.client.get(
            self.endpoint, {'op': 'deployment_status', 'nodes': ids})
        self.assertEqual(
            http.client.OK, response.status_code, response.content)
        self.assertItemsEqual(
            expected, json.loads(
                response.content.decode(settings.DEFAULT_CHARSET)))

    def test_GET_rejects_unviewable_nodes(self):
        owned_node = factory.make_Node(owner=self.logged_in_user)
        unowned_node = factory.make_Node(owner=factory.make_User())
        node_ids = [owned_node.system_id, unowned_node.system_id]
        response = self.client.get(
            self.endpoint,
            {'op': 'deployment_status', 'nodes': node_ids})
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content)
        expected_response = (
            "You don't have the required permission to view the following "
            "node(s): %s." % unowned_node.system_id).encode(
            settings.DEFAULT_CHARSET)
        self.assertEqual(expected_response, response.content)

    def test_GET_rejects_invalid_node_ids(self):
        response = self.client.get(
            self.endpoint,
            {'op': 'deployment_status', 'nodes': ['foo', 'bar']})
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content)
        response_string = response.content.decode(settings.DEFAULT_CHARSET)
        # The order in which "foo" and "bar" appear is not guaranteed, but they
        # should be in the string, as well as the error message.
        self.assertIn("Unknown node(s):", response_string)
        self.assertIn("foo", response_string)
        self.assertIn("bar", response_string)

    def test_GET_rejects_devices(self):
        owned_node = factory.make_Node(
            installable=False, owner=self.logged_in_user)
        response = self.client.get(
            self.endpoint,
            {'op': 'deployment_status', 'nodes': [owned_node.system_id]})
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content)
        self.assertIn(
            "Unknown node(s)",
            response.content.decode(settings.DEFAULT_CHARSET))


class TestBackwardCompatiblityFixNodesAPI(APITestCase):
    """Tests for backward-compatibility fixes of the node and nodes API.

    Before adding the 'Deploying', 'Deployed' and 'Failed deployment' states
    all of this different states were folded into the state 'Allocated'.
    In the 1.0 API, we continue exposing these statuses as one status to
    be backward compatible.

    All the API methods returning a node or list of nodes should obey this
    rule but here we only test some chosen methods as proof that the fix
    is applied across the board.
    """

    scenarios = [
        ('allocated', dict(status=NODE_STATUS.ALLOCATED)),
        ('deploying', dict(status=NODE_STATUS.DEPLOYING)),
        ('deployed', dict(status=NODE_STATUS.DEPLOYED)),
        ('failed_deployment', dict(status=NODE_STATUS.FAILED_DEPLOYMENT)),
        ('releasing', dict(status=NODE_STATUS.RELEASING)),
        ('failed_releasing', dict(status=NODE_STATUS.FAILED_RELEASING)),
        ('disk_erasing', dict(status=NODE_STATUS.DISK_ERASING)),
        ('failed_disk_erasing', dict(status=NODE_STATUS.FAILED_DISK_ERASING)),
    ]

    old_allocated_status = 6

    def get_node_uri(self, node):
        """Get the API URI for a node."""
        return reverse('node_handler', args=[node.system_id])

    def get_nodes_uri(self):
        """Get the API URI for nodes."""
        return reverse('nodes_handler')

    def test_GET_list_allocated_folds_status(self):
        node = factory.make_Node(
            status=self.status, owner=self.logged_in_user,
            token=get_auth_tokens(self.logged_in_user)[0])

        response = self.client.get(self.get_nodes_uri(), {
            'op': 'list_allocated'})

        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))
        self.assertThat(parsed_result, HasLength(1))
        result_node = parsed_result[0]
        self.assertEqual(node.system_id, result_node.get('system_id'))
        self.assertEqual(self.old_allocated_status, result_node.get('status'))

    def test_GET_node_folds_status(self):
        node = factory.make_Node(status=self.status)
        response = self.client.get(self.get_node_uri(node))

        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))
        self.assertEqual(node.system_id, parsed_result['system_id'])
        self.assertEqual(self.old_allocated_status, parsed_result['status'])

    def test_PUT_updates_node_folds_status(self):
        self.become_admin()
        node = factory.make_Node(
            owner=self.logged_in_user, status=self.status,
            architecture=make_usable_architecture(self))
        response = self.client.put(
            self.get_node_uri(node), {'hostname': factory.make_name('host')})
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))

        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(self.old_allocated_status, parsed_result['status'])

    def test_PUT_update_forbidden_if_not_admin(self):
        node = factory.make_Node(
            owner=self.logged_in_user, status=self.status,
            architecture=make_usable_architecture(self))

        # should get FORBIDDEN because user isn't admin
        response = self.client.put(
            self.get_node_uri(node), {'hostname': factory.make_name('host')})
        self.assertEqual(http.client.FORBIDDEN, response.status_code)

        # confirm operation succeeds as admin
        self.become_admin()
        response = self.client.put(
            self.get_node_uri(node), {'hostname': factory.make_name('host')})
        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))
        self.assertEqual(self.old_allocated_status, parsed_result['status'])

    def test_GET_list_allocated_exposes_substatus(self):
        node = factory.make_Node(
            status=self.status, owner=self.logged_in_user,
            token=get_auth_tokens(self.logged_in_user)[0])

        response = self.client.get(self.get_nodes_uri(), {
            'op': 'list_allocated'})

        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))
        self.assertThat(parsed_result, HasLength(1))
        result_node = parsed_result[0]
        self.assertEqual(node.system_id, result_node.get('system_id'))
        self.assertEqual(node.status, result_node.get('substatus'))

    def test_GET_node_exposes_substatus(self):
        node = factory.make_Node(status=self.status)
        response = self.client.get(self.get_node_uri(node))

        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))
        self.assertEqual(node.system_id, parsed_result['system_id'])
        self.assertEqual(self.status, parsed_result['substatus'])

    def test_PUT_updates_exposes_substatus(self):
        self.become_admin()
        node = factory.make_Node(
            owner=self.logged_in_user, status=self.status,
            architecture=make_usable_architecture(self))
        response = self.client.put(
            self.get_node_uri(node), {'hostname': factory.make_name('host')})
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))

        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(node.status, parsed_result['substatus'])


class TestPowerState(APITransactionTestCase):

    def setUp(self):
        super(TestPowerState, self).setUp()
        self.useFixture(RegionEventLoopFixture("database-tasks", "rpc"))
        self.useFixture(RunningEventLoopFixture())

    def get_node_uri(self, node):
        """Get the API URI for a node."""
        return reverse('node_handler', args=[node.system_id])

    def prepare_rpc(self, nodegroup, side_effect=None):
        self.rpc_fixture = self.useFixture(MockLiveRegionToClusterRPCFixture())
        protocol = self.rpc_fixture.makeCluster(
            nodegroup, cluster_module.PowerQuery)
        if side_effect is None:
            protocol.PowerQuery.side_effect = always_succeed_with({})
        else:
            protocol.PowerQuery.side_effect = side_effect

    def assertPowerState(self, node, state):
        dbtasks = eventloop.services.getServiceNamed("database-tasks")
        dbtasks.syncTask().wait(
            timeout=5)  # Wait for all pending tasks to run.
        self.assertThat(reload_object(node).power_state, Equals(state))

    def test__catches_no_connection_error(self):
        getClientFor = self.patch(nodes_module, 'getClientFor')
        getClientFor.side_effect = NoConnectionsAvailable()
        node = factory.make_Node(power_state=POWER_STATE.ON)

        response = self.client.get(
            self.get_node_uri(node), {"op": "query_power_state"})

        self.assertResponseCode(http.client.SERVICE_UNAVAILABLE, response)
        self.assertIn(
            "Unable to connect to cluster controller",
            response.content.decode(settings.DEFAULT_CHARSET))
        # The node's power state is unchanged.
        self.assertPowerState(node, POWER_STATE.ON)

    def test__catches_timeout_error(self):
        mock_client = Mock()
        mock_client().wait.side_effect = crochet.TimeoutError("error")
        getClientFor = self.patch(nodes_module, 'getClientFor')
        getClientFor.return_value = mock_client
        node = factory.make_Node(power_state=POWER_STATE.ON, power_type="ipmi")

        response = self.client.get(
            self.get_node_uri(node), {"op": "query_power_state"})

        self.assertResponseCode(http.client.SERVICE_UNAVAILABLE, response)
        self.assertIn(
            "Timed out waiting for power response",
            response.content.decode(settings.DEFAULT_CHARSET))
        # The node's power state is unchanged.
        self.assertPowerState(node, POWER_STATE.ON)

    def test__catches_unknown_power_type(self):
        self.patch(nodes_module, 'getClientFor')
        node = factory.make_Node(power_state=POWER_STATE.OFF, power_type="")

        response = self.client.get(
            self.get_node_uri(node), {"op": "query_power_state"})

        self.assertResponseCode(http.client.SERVICE_UNAVAILABLE, response)
        self.assertIn(
            "Power state is not queryable",
            response.content.decode(settings.DEFAULT_CHARSET))
        # The node's power state is now "unknown".
        self.assertPowerState(node, POWER_STATE.UNKNOWN)

    def test__catches_poweraction_fail(self):
        node = factory.make_Node(power_state=POWER_STATE.ON, power_type="ipmi")
        error_message = factory.make_name("error")
        self.prepare_rpc(
            node.nodegroup, side_effect=PowerActionFail(error_message))

        response = self.client.get(
            self.get_node_uri(node), {"op": "query_power_state"})

        self.assertResponseCode(http.client.SERVICE_UNAVAILABLE, response)
        self.assertIn(
            error_message.encode(settings.DEFAULT_CHARSET), response.content)
        # The node's power state is now "error".
        self.assertPowerState(node, POWER_STATE.ERROR)

    def test__catches_operation_not_implemented(self):
        node = factory.make_Node(power_state=POWER_STATE.ON, power_type="ipmi")
        error_message = factory.make_name("error")
        self.prepare_rpc(
            node.nodegroup, side_effect=NotImplementedError(error_message))

        response = self.client.get(
            self.get_node_uri(node), {"op": "query_power_state"})

        self.assertResponseCode(http.client.SERVICE_UNAVAILABLE, response)
        self.assertIn(error_message.encode(
            settings.DEFAULT_CHARSET), response.content)
        # The node's power state is now "unknown".
        self.assertPowerState(node, POWER_STATE.UNKNOWN)

    def test__returns_400_if_device(self):
        device = factory.make_Device()
        response = self.client.get(
            self.get_node_uri(device), {"op": "query_power_state"})
        self.assertResponseCode(http.client.BAD_REQUEST, response)

    def test__returns_actual_state(self):
        node = factory.make_Node(power_type="ipmi")
        random_state = random.choice(["on", "off", "error"])
        self.prepare_rpc(
            node.nodegroup,
            side_effect=always_succeed_with({"state": random_state}))

        response = self.client.get(
            self.get_node_uri(node), {"op": "query_power_state"})

        self.assertResponseCode(http.client.OK, response)
        response = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))
        self.assertEqual({"state": random_state}, response)
        # The node's power state is now `random_state`.
        self.assertPowerState(node, random_state)
