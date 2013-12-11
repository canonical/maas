# Copyright 2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the nodes API."""

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
import random

from django.core.urlresolvers import reverse
from maasserver.enum import (
    ARCHITECTURE,
    ARCHITECTURE_CHOICES,
    NODE_AFTER_COMMISSIONING_ACTION,
    NODE_STATUS,
    NODE_STATUS_CHOICES_DICT,
    NODEGROUP_STATUS,
    NODEGROUPINTERFACE_MANAGEMENT,
    )
from maasserver.fields import MAC
from maasserver.models import Node
from maasserver.models.user import (
    create_auth_token,
    get_auth_tokens,
    )
from maasserver.testing import reload_object
from maasserver.testing.api import (
    APITestCase,
    MultipleUsersScenarios,
    )
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils import (
    ignore_unused,
    map_enum,
    )
from maasserver.utils.orm import get_one
from testtools.matchers import (
    Contains,
    Equals,
    MatchesListwise,
    )


class NodeHostnameTest(MultipleUsersScenarios,
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
        factory.make_node(
            hostname=hostname_with_domain, nodegroup=nodegroup)
        expected_hostname = '%s.%s' % (hostname_without_domain, domain)
        response = self.client.get(reverse('nodes_handler'), {'op': 'list'})
        self.assertEqual(httplib.OK, response.status_code, response.content)
        parsed_result = json.loads(response.content)
        self.assertItemsEqual(
            [expected_hostname],
            [node.get('hostname') for node in parsed_result])


class AnonymousIsRegisteredAPITest(MAASServerTestCase):

    def test_is_registered_returns_True_if_node_registered(self):
        mac_address = factory.getRandomMACAddress()
        factory.make_mac_address(mac_address)
        response = self.client.get(
            reverse('nodes_handler'),
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
            reverse('nodes_handler'),
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
            reverse('nodes_handler'),
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
            reverse('nodes_handler'),
            {'op': 'is_registered', 'mac_address': mac_address})
        self.assertEqual(
            (httplib.OK, "false"),
            (response.status_code, response.content))


def extract_system_ids(parsed_result):
    """List the system_ids of the nodes in `parsed_result`."""
    return [node.get('system_id') for node in parsed_result]


class TestNodesAPI(APITestCase):
    """Tests for /api/1.0/nodes/."""

    def test_handler_path(self):
        self.assertEqual(
            '/api/1.0/nodes/', reverse('nodes_handler'))

    def test_POST_new_creates_node(self):
        # The API allows a non-admin logged-in user to create a Node.
        architecture = factory.getRandomChoice(ARCHITECTURE_CHOICES)
        response = self.client.post(
            reverse('nodes_handler'),
            {
                'op': 'new',
                'hostname': factory.getRandomString(),
                'architecture': architecture,
                'after_commissioning_action': (
                    NODE_AFTER_COMMISSIONING_ACTION.DEFAULT),
                'mac_addresses': ['aa:bb:cc:dd:ee:ff', '22:bb:cc:dd:ee:ff'],
            })

        self.assertEqual(httplib.OK, response.status_code)

    def test_POST_new_when_logged_in_creates_node_in_declared_state(self):
        # When a user enlists a node, it goes into the Declared state.
        # This will change once we start doing proper commissioning.
        response = self.client.post(
            reverse('nodes_handler'),
            {
                'op': 'new',
                'hostname': factory.getRandomString(),
                'architecture': factory.getRandomChoice(ARCHITECTURE_CHOICES),
                'after_commissioning_action': (
                    NODE_AFTER_COMMISSIONING_ACTION.DEFAULT),
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
        response = self.client.get(reverse('nodes_handler'), {'op': 'list'})
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
            self.client.get, reverse('nodes_handler'), {'op': 'list'})
        self.create_nodes(nodegroup, 10)
        num_queries2, response2 = self.getNumQueries(
            self.client.get, reverse('nodes_handler'), {'op': 'list'})
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
        response = self.client.get(reverse('nodes_handler'), {'op': 'list'})
        self.assertItemsEqual([], json.loads(response.content))

    def test_GET_list_orders_by_id(self):
        # Nodes are returned in id order.
        nodes = [factory.make_node() for counter in range(3)]
        response = self.client.get(reverse('nodes_handler'), {'op': 'list'})
        parsed_result = json.loads(response.content)
        self.assertSequenceEqual(
            [node.system_id for node in nodes],
            extract_system_ids(parsed_result))

    def test_GET_list_with_id_returns_matching_nodes(self):
        # The "list" operation takes optional "id" parameters.  Only
        # nodes with matching ids will be returned.
        ids = [factory.make_node().system_id for counter in range(3)]
        matching_id = ids[0]
        response = self.client.get(reverse('nodes_handler'), {
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
        response = self.client.get(reverse('nodes_handler'), {
            'op': 'list',
            'id': [nonexistent_id],
        })
        self.assertItemsEqual([], json.loads(response.content))

    def test_GET_list_with_ids_orders_by_id(self):
        # Even when ids are passed to "list," nodes are returned in id
        # order, not necessarily in the order of the id arguments.
        ids = [factory.make_node().system_id for counter in range(3)]
        response = self.client.get(reverse('nodes_handler'), {
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
        response = self.client.get(reverse('nodes_handler'), {
            'op': 'list',
            'id': [existing_id, nonexistent_id],
        })
        parsed_result = json.loads(response.content)
        self.assertItemsEqual(
            [existing_id], extract_system_ids(parsed_result))

    def test_GET_list_with_hostname_returns_matching_nodes(self):
        # The list operation takes optional "hostname" parameters. Only nodes
        # with matching hostnames will be returned.
        nodes = [factory.make_node() for counter in range(3)]
        matching_hostname = nodes[0].hostname
        matching_system_id = nodes[0].system_id
        response = self.client.get(reverse('nodes_handler'), {
            'op': 'list',
            'hostname': [matching_hostname],
        })
        parsed_result = json.loads(response.content)
        self.assertItemsEqual(
            [matching_system_id], extract_system_ids(parsed_result))

    def test_GET_list_with_macs_returns_matching_nodes(self):
        # The "list" operation takes optional "mac_address" parameters. Only
        # nodes with matching MAC addresses will be returned.
        macs = [factory.make_mac_address() for counter in range(3)]
        matching_mac = macs[0].mac_address
        matching_system_id = macs[0].node.system_id
        response = self.client.get(reverse('nodes_handler'), {
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
        response = self.client.get(reverse('nodes_handler'), {
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

    def test_GET_list_with_agent_name_filters_by_agent_name(self):
        non_listed_node = factory.make_node(
            agent_name=factory.make_name('agent_name'))
        ignore_unused(non_listed_node)
        agent_name = factory.make_name('agent-name')
        node = factory.make_node(agent_name=agent_name)
        response = self.client.get(reverse('nodes_handler'), {
            'op': 'list',
            'agent_name': agent_name,
            })
        self.assertEqual(httplib.OK, response.status_code)
        parsed_result = json.loads(response.content)
        self.assertSequenceEqual(
            [node.system_id], extract_system_ids(parsed_result))

    def test_GET_list_with_agent_name_filters_with_empty_string(self):
        factory.make_node(agent_name=factory.make_name('agent-name'))
        node = factory.make_node(agent_name='')
        response = self.client.get(reverse('nodes_handler'), {
            'op': 'list',
            'agent_name': '',
            })
        self.assertEqual(httplib.OK, response.status_code)
        parsed_result = json.loads(response.content)
        self.assertSequenceEqual(
            [node.system_id], extract_system_ids(parsed_result))

    def test_GET_list_without_agent_name_does_not_filter(self):
        nodes = [
            factory.make_node(agent_name=factory.make_name('agent-name'))
            for i in range(3)]
        response = self.client.get(reverse('nodes_handler'), {'op': 'list'})
        self.assertEqual(httplib.OK, response.status_code)
        parsed_result = json.loads(response.content)
        self.assertSequenceEqual(
            [node.system_id for node in nodes],
            extract_system_ids(parsed_result))

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

        response = self.client.get(reverse('nodes_handler'), {
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
        response = self.client.get(reverse('nodes_handler'), {
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
        response = self.client.post(
            reverse('nodes_handler'), {'op': 'acquire'})
        self.assertEqual(httplib.OK, response.status_code)
        parsed_result = json.loads(response.content)
        self.assertEqual(node.system_id, parsed_result['system_id'])

    def test_POST_acquire_allocates_node(self):
        # The "acquire" operation allocates the node it returns.
        available_status = NODE_STATUS.READY
        node = factory.make_node(status=available_status, owner=None)
        self.client.post(reverse('nodes_handler'), {'op': 'acquire'})
        node = Node.objects.get(system_id=node.system_id)
        self.assertEqual(self.logged_in_user, node.owner)

    def test_POST_acquire_sets_agent_name(self):
        available_status = NODE_STATUS.READY
        node = factory.make_node(
            status=available_status, owner=None,
            agent_name=factory.make_name('agent-name'))
        agent_name = factory.make_name('agent-name')
        self.client.post(
            reverse('nodes_handler'),
            {'op': 'acquire', 'agent_name': agent_name})
        node = Node.objects.get(system_id=node.system_id)
        self.assertEqual(agent_name, node.agent_name)

    def test_POST_acquire_agent_name_defaults_to_empty_string(self):
        available_status = NODE_STATUS.READY
        agent_name = factory.make_name('agent-name')
        node = factory.make_node(
            status=available_status, owner=None, agent_name=agent_name)
        self.client.post(reverse('nodes_handler'), {'op': 'acquire'})
        node = Node.objects.get(system_id=node.system_id)
        self.assertEqual('', node.agent_name)

    def test_POST_acquire_fails_if_no_node_present(self):
        # The "acquire" operation returns a Conflict error if no nodes
        # are available.
        response = self.client.post(
            reverse('nodes_handler'), {'op': 'acquire'})
        # Fails with Conflict error: resource can't satisfy request.
        self.assertEqual(httplib.CONFLICT, response.status_code)

    def test_POST_ignores_already_allocated_node(self):
        factory.make_node(
            status=NODE_STATUS.ALLOCATED, owner=factory.make_user())
        response = self.client.post(
            reverse('nodes_handler'), {'op': 'acquire'})
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
        response = self.client.post(reverse('nodes_handler'), {
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
        response = self.client.post(reverse('nodes_handler'), {
            'op': 'acquire',
            'name': desired_node.system_id,
        })
        self.assertEqual(httplib.CONFLICT, response.status_code)

    def test_POST_acquire_ignores_unknown_constraint(self):
        node = factory.make_node(status=NODE_STATUS.READY, owner=None)
        response = self.client.post(reverse('nodes_handler'), {
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
        response = self.client.post(reverse('nodes_handler'), {
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
        response = self.client.post(reverse('nodes_handler'), {
            'op': 'acquire',
            'name': factory.getRandomString(),
        })
        self.assertEqual(httplib.CONFLICT, response.status_code)

    def test_POST_acquire_allocates_node_by_arch(self):
        # Asking for a particular arch acquires a node with that arch.
        node = factory.make_node(
            status=NODE_STATUS.READY, architecture=ARCHITECTURE.i386)
        response = self.client.post(reverse('nodes_handler'), {
            'op': 'acquire',
            'arch': 'i386/generic',
        })
        self.assertEqual(httplib.OK, response.status_code)
        response_json = json.loads(response.content)
        self.assertEqual(node.architecture, response_json['architecture'])

    def test_POST_acquire_treats_unknown_arch_as_bad_request(self):
        # Asking for an unknown arch returns an HTTP "400 Bad Request"
        factory.make_node(status=NODE_STATUS.READY)
        response = self.client.post(reverse('nodes_handler'), {
            'op': 'acquire',
            'arch': 'sparc',
        })
        self.assertEqual(httplib.BAD_REQUEST, response.status_code)

    def test_POST_acquire_allocates_node_by_cpu(self):
        # Asking for enough cpu acquires a node with at least that.
        node = factory.make_node(status=NODE_STATUS.READY, cpu_count=3)
        response = self.client.post(reverse('nodes_handler'), {
            'op': 'acquire',
            'cpu_count': 2,
        })
        self.assertResponseCode(httplib.OK, response)
        response_json = json.loads(response.content)
        self.assertEqual(node.system_id, response_json['system_id'])

    def test_POST_acquire_allocates_node_by_float_cpu(self):
        # Asking for a needlessly precise number of cpus works.
        node = factory.make_node(status=NODE_STATUS.READY, cpu_count=1)
        response = self.client.post(reverse('nodes_handler'), {
            'op': 'acquire',
            'cpu_count': '1.0',
        })
        self.assertResponseCode(httplib.OK, response)
        response_json = json.loads(response.content)
        self.assertEqual(node.system_id, response_json['system_id'])

    def test_POST_acquire_fails_with_invalid_cpu(self):
        # Asking for an invalid amount of cpu returns a bad request.
        factory.make_node(status=NODE_STATUS.READY)
        response = self.client.post(reverse('nodes_handler'), {
            'op': 'acquire',
            'cpu_count': 'plenty',
        })
        self.assertResponseCode(httplib.BAD_REQUEST, response)

    def test_POST_acquire_allocates_node_by_mem(self):
        # Asking for enough memory acquires a node with at least that.
        node = factory.make_node(status=NODE_STATUS.READY, memory=1024)
        response = self.client.post(reverse('nodes_handler'), {
            'op': 'acquire',
            'mem': 1024,
        })
        self.assertResponseCode(httplib.OK, response)
        response_json = json.loads(response.content)
        self.assertEqual(node.system_id, response_json['system_id'])

    def test_POST_acquire_fails_with_invalid_mem(self):
        # Asking for an invalid amount of memory returns a bad request.
        factory.make_node(status=NODE_STATUS.READY)
        response = self.client.post(reverse('nodes_handler'), {
            'op': 'acquire',
            'mem': 'bags',
        })
        self.assertResponseCode(httplib.BAD_REQUEST, response)

    def test_POST_acquire_allocates_node_by_tags(self):
        node = factory.make_node(status=NODE_STATUS.READY)
        node_tag_names = ["fast", "stable", "cute"]
        node.tags = [factory.make_tag(t) for t in node_tag_names]
        # Legacy call using comma-separated tags.
        response = self.client.post(reverse('nodes_handler'), {
            'op': 'acquire',
            'tags': ['fast', 'stable'],
        })
        self.assertResponseCode(httplib.OK, response)
        response_json = json.loads(response.content)
        self.assertEqual(node_tag_names, response_json['tag_names'])

    def test_POST_acquire_allocates_node_by_zone(self):
        factory.make_node(status=NODE_STATUS.READY)
        zone = factory.make_zone()
        node = factory.make_node(status=NODE_STATUS.READY, zone=zone)
        response = self.client.post(reverse('nodes_handler'), {
            'op': 'acquire',
            'zone': zone.name,
        })
        self.assertResponseCode(httplib.OK, response)
        response_json = json.loads(response.content)
        self.assertEqual(node.system_id, response_json['system_id'])

    def test_POST_acquire_allocates_node_by_zone_fails_if_no_node(self):
        factory.make_node(status=NODE_STATUS.READY)
        zone = factory.make_zone()
        response = self.client.post(reverse('nodes_handler'), {
            'op': 'acquire',
            'zone': zone.name,
        })
        self.assertResponseCode(httplib.CONFLICT, response)

    def test_POST_acquire_allocates_node_by_tags_comma_separated(self):
        node = factory.make_node(status=NODE_STATUS.READY)
        node_tag_names = ["fast", "stable", "cute"]
        node.tags = [factory.make_tag(t) for t in node_tag_names]
        # Legacy call using comma-separated tags.
        response = self.client.post(reverse('nodes_handler'), {
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
        response = self.client.post(reverse('nodes_handler'), {
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
        response = self.client.post(reverse('nodes_handler'), {
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
        response = self.client.post(reverse('nodes_handler'), {
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
        response = self.client.post(reverse('nodes_handler'), {
            'op': 'acquire',
            'tags': 'fast, cheap',
        })
        self.assertResponseCode(httplib.CONFLICT, response)

    def test_POST_acquire_fails_with_unknown_tags(self):
        # Asking for a tag that does not exist gives a specific error.
        node = factory.make_node(status=NODE_STATUS.READY)
        node.tags = [factory.make_tag("fast")]
        response = self.client.post(reverse('nodes_handler'), {
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

        response = self.client.post(reverse('nodes_handler'), {
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

        response = self.client.post(reverse('nodes_handler'), {
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
        self.client.post(reverse('nodes_handler'), {'op': 'acquire'})
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
            reverse('nodes_handler'),
            {'op': 'accept', 'nodes': [node.system_id]})
        accepted_ids = [
            accepted_node['system_id']
            for accepted_node in json.loads(response.content)]
        self.assertEqual(
            (httplib.OK, [node.system_id]),
            (response.status_code, accepted_ids))
        self.assertEqual(target_state, reload_object(node).status)

    def test_POST_quietly_accepts_empty_set(self):
        response = self.client.post(reverse('nodes_handler'), {'op': 'accept'})
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
                reverse('nodes_handler'), {
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
            reverse('nodes_handler'), {'op': 'accept', 'nodes': [node_id]})
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
        response = self.client.post(reverse('nodes_handler'), {
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
        response = self.client.post(reverse('nodes_handler'), {
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
        response = self.client.post(
            reverse('nodes_handler'), {'op': 'release'})
        self.assertEqual(
            (httplib.OK, "[]"), (response.status_code, response.content))

    def test_POST_release_rejects_request_from_unauthorized_user(self):
        node = factory.make_node(
            status=NODE_STATUS.ALLOCATED, owner=factory.make_user())
        response = self.client.post(
            reverse('nodes_handler'), {
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
            reverse('nodes_handler'), {
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
            reverse('nodes_handler'), {
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
            reverse('nodes_handler'), {
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
            reverse('nodes_handler'), {
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
            '/api/1.0/nodes/MAAS/api/1.0/nodes/',
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
