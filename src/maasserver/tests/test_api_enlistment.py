# Copyright 2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for enlistment-related portions of the API."""

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

from django.contrib.auth.models import AnonymousUser
from django.core.urlresolvers import reverse
from maasserver.enum import (
    ARCHITECTURE_CHOICES,
    NODE_AFTER_COMMISSIONING_ACTION,
    NODE_STATUS,
    NODEGROUP_STATUS,
    NODEGROUPINTERFACE_MANAGEMENT,
    )
from maasserver.models import (
    Node,
    NodeGroup,
    )
from maasserver.testing import reload_object
from maasserver.testing.api import MultipleUsersScenarios
from maasserver.testing.factory import factory
from maasserver.testing.testcase import (
    AdminLoggedInTestCase,
    LoggedInTestCase,
    MAASServerTestCase,
    )
from maasserver.utils import strip_domain
from maasserver.utils.orm import get_one
from netaddr import IPNetwork
from provisioningserver.enum import POWER_TYPE


class EnlistmentAPITest(MultipleUsersScenarios,
                        MAASServerTestCase):
    """Enlistment tests."""
    scenarios = [
        ('anon', dict(userfactory=lambda: AnonymousUser())),
        ('user', dict(userfactory=factory.make_user)),
        ('admin', dict(userfactory=factory.make_admin)),
        ]

    def test_POST_new_creates_node(self):
        architecture = factory.getRandomChoice(ARCHITECTURE_CHOICES)
        response = self.client.post(
            reverse('nodes_handler'),
            {
                'op': 'new',
                'hostname': 'diane',
                'architecture': architecture,
                'after_commissioning_action': (
                    NODE_AFTER_COMMISSIONING_ACTION.DEFAULT),
                'mac_addresses': ['aa:bb:cc:dd:ee:ff', '22:bb:cc:dd:ee:ff'],
            })

        self.assertEqual(httplib.OK, response.status_code)
        parsed_result = json.loads(response.content)
        self.assertIn('application/json', response['Content-Type'])
        self.assertEqual('diane', parsed_result['hostname'])
        self.assertNotEqual(0, len(parsed_result.get('system_id')))
        [diane] = Node.objects.filter(hostname='diane')
        self.assertEqual(architecture, diane.architecture)

    def test_POST_new_generates_hostname_if_ip_based_hostname(self):
        hostname = '192-168-5-19.domain'
        response = self.client.post(
            reverse('nodes_handler'),
            {
                'op': 'new',
                'hostname': hostname,
                'architecture': factory.getRandomChoice(ARCHITECTURE_CHOICES),
                'after_commissioning_action': (
                    NODE_AFTER_COMMISSIONING_ACTION.DEFAULT),
                'mac_addresses': [factory.getRandomMACAddress()],
            })
        parsed_result = json.loads(response.content)

        self.assertEqual(httplib.OK, response.status_code)
        system_id = parsed_result.get('system_id')
        node = Node.objects.get(system_id=system_id)
        self.assertNotEqual(hostname, node.hostname)

    def test_POST_new_creates_node_with_power_parameters(self):
        # We're setting power parameters so we disable start_commissioning to
        # prevent anything from attempting to issue power instructions.
        self.patch(Node, "start_commissioning")
        hostname = factory.make_name("hostname")
        architecture = factory.getRandomChoice(ARCHITECTURE_CHOICES)
        power_type = POWER_TYPE.IPMI
        power_parameters = {
            "power_user": factory.make_name("power-user"),
            "power_pass": factory.make_name("power-pass"),
            }
        response = self.client.post(
            reverse('nodes_handler'),
            {
                'op': 'new',
                'hostname': hostname,
                'architecture': architecture,
                'mac_addresses': factory.getRandomMACAddress(),
                'power_parameters': json.dumps(power_parameters),
                'power_type': power_type,
            })
        self.assertEqual(httplib.OK, response.status_code)
        [node] = Node.objects.filter(hostname=hostname)
        self.assertEqual(power_parameters, node.power_parameters)
        self.assertEqual(power_type, node.power_type)

    def test_POST_new_creates_node_with_arch_only(self):
        architecture = factory.getRandomChoice(
            [choice for choice in ARCHITECTURE_CHOICES
             if choice[0].endswith('/generic')])
        response = self.client.post(
            reverse('nodes_handler'),
            {
                'op': 'new',
                'hostname': 'diane',
                'architecture': architecture.split('/')[0],
                'after_commissioning_action': (
                    NODE_AFTER_COMMISSIONING_ACTION.DEFAULT),
                'mac_addresses': ['aa:bb:cc:dd:ee:ff', '22:bb:cc:dd:ee:ff'],
            })

        self.assertEqual(httplib.OK, response.status_code)
        parsed_result = json.loads(response.content)
        self.assertIn('application/json', response['Content-Type'])
        self.assertEqual('diane', parsed_result['hostname'])
        self.assertNotEqual(0, len(parsed_result.get('system_id')))
        [diane] = Node.objects.filter(hostname='diane')
        self.assertEqual(architecture, diane.architecture)

    def test_POST_new_creates_node_with_subarchitecture(self):
        # The API allows a Node to be created.
        architecture = factory.getRandomChoice(ARCHITECTURE_CHOICES)
        response = self.client.post(
            reverse('nodes_handler'),
            {
                'op': 'new',
                'hostname': 'diane',
                'architecture': architecture.split('/')[0],
                'subarchitecture': architecture.split('/')[1],
                'after_commissioning_action': (
                    NODE_AFTER_COMMISSIONING_ACTION.DEFAULT),
                'mac_addresses': ['aa:bb:cc:dd:ee:ff', '22:bb:cc:dd:ee:ff'],
            })

        self.assertEqual(httplib.OK, response.status_code)
        parsed_result = json.loads(response.content)
        self.assertIn('application/json', response['Content-Type'])
        self.assertEqual('diane', parsed_result['hostname'])
        self.assertNotEqual(0, len(parsed_result.get('system_id')))
        [diane] = Node.objects.filter(hostname='diane')
        self.assertEqual(architecture, diane.architecture)

    def test_POST_new_fails_node_with_double_subarchitecture(self):
        architecture = factory.getRandomChoice(ARCHITECTURE_CHOICES)
        response = self.client.post(
            reverse('nodes_handler'),
            {
                'op': 'new',
                'hostname': 'diane',
                'architecture': architecture,
                'subarchitecture': architecture.split('/')[1],
                'after_commissioning_action': (
                    NODE_AFTER_COMMISSIONING_ACTION.DEFAULT),
                'mac_addresses': ['aa:bb:cc:dd:ee:ff', '22:bb:cc:dd:ee:ff'],
            })
        self.assertEqual(httplib.BAD_REQUEST, response.status_code)
        self.assertIn('text/plain', response['Content-Type'])
        self.assertEqual(
            "Subarchitecture cannot be specified twice.",
            response.content)

    def test_POST_new_power_type_defaults_to_asking_config(self):
        architecture = factory.getRandomChoice(ARCHITECTURE_CHOICES)
        response = self.client.post(
            reverse('nodes_handler'), {
                'op': 'new',
                'architecture': architecture,
                'mac_addresses': ['00:11:22:33:44:55'],
                })
        node = Node.objects.get(
            system_id=json.loads(response.content)['system_id'])
        self.assertEqual(POWER_TYPE.DEFAULT, node.power_type)

    def test_POST_new_associates_mac_addresses(self):
        # The API allows a Node to be created and associated with MAC
        # Addresses.
        architecture = factory.getRandomChoice(ARCHITECTURE_CHOICES)
        self.client.post(
            reverse('nodes_handler'),
            {
                'op': 'new',
                'hostname': 'diane',
                'architecture': architecture,
                'after_commissioning_action': (
                    NODE_AFTER_COMMISSIONING_ACTION.DEFAULT),
                'mac_addresses': ['aa:bb:cc:dd:ee:ff', '22:bb:cc:dd:ee:ff'],
            })
        diane = get_one(Node.objects.filter(hostname='diane'))
        self.assertItemsEqual(
            ['aa:bb:cc:dd:ee:ff', '22:bb:cc:dd:ee:ff'],
            [mac.mac_address for mac in diane.macaddress_set.all()])

    def test_POST_new_initializes_nodegroup_to_master_by_default(self):
        hostname = factory.make_name('host')
        self.client.post(
            reverse('nodes_handler'),
            {
                'op': 'new',
                'hostname': hostname,
                'architecture': factory.getRandomChoice(ARCHITECTURE_CHOICES),
                'mac_addresses': [factory.getRandomMACAddress()],
            })
        self.assertEqual(
            NodeGroup.objects.ensure_master(),
            Node.objects.get(hostname=hostname).nodegroup)

    def test_POST_with_no_hostname_auto_populates_hostname(self):
        architecture = factory.getRandomChoice(ARCHITECTURE_CHOICES)
        response = self.client.post(
            reverse('nodes_handler'),
            {
                'op': 'new',
                'architecture': architecture,
                'mac_addresses': [factory.getRandomMACAddress()],
            })
        node = Node.objects.get(
            system_id=json.loads(response.content)['system_id'])
        self.assertEqual(5, len(strip_domain(node.hostname)))

    def test_POST_fails_without_operation(self):
        # If there is no operation ('op=operation_name') specified in the
        # request data, a 'Bad request' response is returned.
        response = self.client.post(
            reverse('nodes_handler'),
            {
                'hostname': 'diane',
                'mac_addresses': ['aa:bb:cc:dd:ee:ff', 'invalid'],
            })

        self.assertEqual(httplib.BAD_REQUEST, response.status_code)
        self.assertIn('text/html', response['Content-Type'])
        self.assertEqual(
            "Unrecognised signature: POST None",
            response.content)

    def test_POST_fails_if_mac_duplicated(self):
        # Mac Addresses should be unique.
        mac = 'aa:bb:cc:dd:ee:ff'
        factory.make_mac_address(mac)
        architecture = factory.getRandomChoice(ARCHITECTURE_CHOICES)
        response = self.client.post(
            reverse('nodes_handler'),
            {
                'op': 'new',
                'architecture': architecture,
                'hostname': factory.getRandomString(),
                'mac_addresses': [mac],
            })
        parsed_result = json.loads(response.content)

        self.assertEqual(httplib.BAD_REQUEST, response.status_code)
        self.assertIn('application/json', response['Content-Type'])
        self.assertEqual(
            ["Mac address %s already in use." % mac],
            parsed_result['mac_addresses'])

    def test_POST_fails_with_bad_operation(self):
        # If the operation ('op=operation_name') specified in the
        # request data is unknown, a 'Bad request' response is returned.
        response = self.client.post(
            reverse('nodes_handler'),
            {
                'op': 'invalid_operation',
                'hostname': 'diane',
                'mac_addresses': ['aa:bb:cc:dd:ee:ff', 'invalid'],
            })

        self.assertEqual(httplib.BAD_REQUEST, response.status_code)
        self.assertEqual(
            "Unrecognised signature: POST invalid_operation",
            response.content)

    def test_POST_new_rejects_invalid_data(self):
        # If the data provided to create a node with an invalid MAC
        # Address, a 'Bad request' response is returned.
        response = self.client.post(
            reverse('nodes_handler'),
            {
                'op': 'new',
                'hostname': 'diane',
                'mac_addresses': ['aa:bb:cc:dd:ee:ff', 'invalid'],
            })
        parsed_result = json.loads(response.content)

        self.assertEqual(httplib.BAD_REQUEST, response.status_code)
        self.assertIn('application/json', response['Content-Type'])
        self.assertEqual(
            ["One or more MAC addresses is invalid."],
            parsed_result['mac_addresses'])

    def test_POST_invalid_architecture_returns_bad_request(self):
        # If the architecture name provided to create a node is not a valid
        # architecture name, a 'Bad request' response is returned.
        response = self.client.post(
            reverse('nodes_handler'),
            {
                'op': 'new',
                'hostname': 'diane',
                'mac_addresses': ['aa:bb:cc:dd:ee:ff'],
                'architecture': 'invalid-architecture',
            })
        parsed_result = json.loads(response.content)

        self.assertEqual(httplib.BAD_REQUEST, response.status_code)
        self.assertIn('application/json', response['Content-Type'])
        self.assertItemsEqual(['architecture'], parsed_result)


class NodeHostnameEnlistmentTest(MultipleUsersScenarios,
                                 MAASServerTestCase):

    scenarios = [
        ('anon', dict(userfactory=lambda: AnonymousUser())),
        ('user', dict(userfactory=factory.make_user)),
        ('admin', dict(userfactory=factory.make_admin)),
        ]

    def test_created_node_has_domain_from_cluster(self):
        hostname_without_domain = factory.make_name('hostname')
        hostname_with_domain = '%s.%s' % (
            hostname_without_domain, factory.getRandomString())
        domain = factory.make_name('domain')
        factory.make_node_group(
            status=NODEGROUP_STATUS.ACCEPTED,
            name=domain,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS)
        response = self.client.post(
            reverse('nodes_handler'),
            {
                'op': 'new',
                'hostname': hostname_with_domain,
                'architecture': factory.getRandomChoice(ARCHITECTURE_CHOICES),
                'after_commissioning_action': (
                    NODE_AFTER_COMMISSIONING_ACTION.DEFAULT),
                'mac_addresses': [factory.getRandomMACAddress()],
            })
        self.assertEqual(httplib.OK, response.status_code, response.content)
        parsed_result = json.loads(response.content)
        expected_hostname = '%s.%s' % (hostname_without_domain, domain)
        self.assertEqual(
            expected_hostname, parsed_result.get('hostname'))

    def test_created_node_gets_domain_from_cluster_appended(self):
        hostname_without_domain = factory.make_name('hostname')
        domain = factory.make_name('domain')
        factory.make_node_group(
            status=NODEGROUP_STATUS.ACCEPTED,
            name=domain,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS)
        response = self.client.post(
            reverse('nodes_handler'),
            {
                'op': 'new',
                'hostname': hostname_without_domain,
                'architecture': factory.getRandomChoice(ARCHITECTURE_CHOICES),
                'after_commissioning_action': (
                    NODE_AFTER_COMMISSIONING_ACTION.DEFAULT),
                'mac_addresses': [factory.getRandomMACAddress()],
            })
        self.assertEqual(httplib.OK, response.status_code, response.content)
        parsed_result = json.loads(response.content)
        expected_hostname = '%s.%s' % (hostname_without_domain, domain)
        self.assertEqual(
            expected_hostname, parsed_result.get('hostname'))

    def test_created_node_nodegroup_is_inferred_from_origin_network(self):
        network = IPNetwork('192.168.0.3/24')
        origin_ip = factory.getRandomIPInNetwork(network)
        NodeGroup.objects.ensure_master()
        nodegroup = factory.make_node_group(network=network)
        response = self.client.post(
            reverse('nodes_handler'),
            data={
                'op': 'new',
                'hostname': factory.make_name('hostname'),
                'architecture': factory.getRandomChoice(ARCHITECTURE_CHOICES),
                'after_commissioning_action': (
                    NODE_AFTER_COMMISSIONING_ACTION.DEFAULT),
                'mac_addresses': [factory.getRandomMACAddress()],
            },
            REMOTE_ADDR=origin_ip)
        self.assertEqual(httplib.OK, response.status_code, response.content)
        parsed_result = json.loads(response.content)
        node = Node.objects.get(system_id=parsed_result.get('system_id'))
        self.assertEqual(nodegroup, node.nodegroup)

    def test_created_node_uses_default_nodegroup_if_origin_not_found(self):
        unknown_host = factory.make_name('host')
        response = self.client.post(
            reverse('nodes_handler'),
            data={
                'op': 'new',
                'hostname': factory.make_name('hostname'),
                'architecture': factory.getRandomChoice(ARCHITECTURE_CHOICES),
                'after_commissioning_action': (
                    NODE_AFTER_COMMISSIONING_ACTION.DEFAULT),
                'mac_addresses': [factory.getRandomMACAddress()],
            },
            HTTP_HOST=unknown_host)
        self.assertEqual(httplib.OK, response.status_code, response.content)
        parsed_result = json.loads(response.content)
        node = Node.objects.get(system_id=parsed_result.get('system_id'))
        self.assertEqual(NodeGroup.objects.ensure_master(), node.nodegroup)


class NonAdminEnlistmentAPITest(MultipleUsersScenarios,
                                MAASServerTestCase):
    # Enlistment tests for non-admin users.

    scenarios = [
        ('anon', dict(userfactory=lambda: AnonymousUser())),
        ('user', dict(userfactory=factory.make_user)),
        ]

    def test_POST_non_admin_creates_node_in_declared_state(self):
        # Upon non-admin enlistment, a node goes into the Declared
        # state.  Deliberate approval is required before we start
        # reinstalling the system, wiping its disks etc.
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


class AnonymousEnlistmentAPITest(MAASServerTestCase):
    # Enlistment tests specific to anonymous users.

    def test_POST_accept_not_allowed(self):
        # An anonymous user is not allowed to accept an anonymously
        # enlisted node.  That would defeat the whole purpose of holding
        # those nodes for approval.
        node_id = factory.make_node(status=NODE_STATUS.DECLARED).system_id
        response = self.client.post(
            reverse('nodes_handler'), {'op': 'accept', 'nodes': [node_id]})
        self.assertEqual(
            (httplib.UNAUTHORIZED, "You must be logged in to accept nodes."),
            (response.status_code, response.content))

    def test_POST_returns_limited_fields(self):
        response = self.client.post(
            reverse('nodes_handler'),
            {
                'op': 'new',
                'architecture': factory.getRandomChoice(ARCHITECTURE_CHOICES),
                'hostname': factory.getRandomString(),
                'after_commissioning_action': (
                    NODE_AFTER_COMMISSIONING_ACTION.DEFAULT),
                'mac_addresses': ['aa:bb:cc:dd:ee:ff', '22:bb:cc:dd:ee:ff'],
            })
        parsed_result = json.loads(response.content)
        self.assertItemsEqual(
            [
                'hostname',
                'owner',
                'system_id',
                'macaddress_set',
                'architecture',
                'status',
                'netboot',
                'power_type',
                'tag_names',
                'ip_addresses',
                'resource_uri',
                'cpu_count',
                'storage',
                'memory',
                'routers',
            ],
            list(parsed_result))


class SimpleUserLoggedInEnlistmentAPITest(LoggedInTestCase):
    # Enlistment tests specific to simple (non-admin) users.

    def test_POST_accept_not_allowed(self):
        # An non-admin user is not allowed to accept an anonymously
        # enlisted node.  That would defeat the whole purpose of holding
        # those nodes for approval.
        node_id = factory.make_node(status=NODE_STATUS.DECLARED).system_id
        response = self.client.post(
            reverse('nodes_handler'), {'op': 'accept', 'nodes': [node_id]})
        self.assertEqual(
            (httplib.FORBIDDEN,
                "You don't have the required permission to accept the "
                "following node(s): %s." % node_id),
            (response.status_code, response.content))

    def test_POST_accept_all_does_not_accept_anything(self):
        # It is not an error for a non-admin user to attempt to accept all
        # anonymously enlisted nodes, but only those for which he/she has
        # admin privs will be accepted, which currently equates to none of
        # them.
        factory.make_node(status=NODE_STATUS.DECLARED),
        factory.make_node(status=NODE_STATUS.DECLARED),
        response = self.client.post(
            reverse('nodes_handler'), {'op': 'accept_all'})
        self.assertEqual(httplib.OK, response.status_code)
        nodes_returned = json.loads(response.content)
        self.assertEqual([], nodes_returned)

    def test_POST_simple_user_can_set_power_type_and_parameters(self):
        new_power_address = factory.getRandomString()
        response = self.client.post(
            reverse('nodes_handler'), {
                'op': 'new',
                'architecture': factory.getRandomChoice(ARCHITECTURE_CHOICES),
                'power_type': POWER_TYPE.WAKE_ON_LAN,
                'power_parameters': json.dumps(
                    {"power_address": new_power_address}),
                'mac_addresses': ['AA:BB:CC:DD:EE:FF'],
                })

        node = Node.objects.get(
            system_id=json.loads(response.content)['system_id'])
        self.assertEqual(
            (httplib.OK, {"power_address": new_power_address},
             POWER_TYPE.WAKE_ON_LAN),
            (response.status_code, node.power_parameters,
             node.power_type))

    def test_POST_returns_limited_fields(self):
        response = self.client.post(
            reverse('nodes_handler'),
            {
                'op': 'new',
                'hostname': factory.getRandomString(),
                'architecture': factory.getRandomChoice(ARCHITECTURE_CHOICES),
                'after_commissioning_action': (
                    NODE_AFTER_COMMISSIONING_ACTION.DEFAULT),
                'mac_addresses': ['aa:bb:cc:dd:ee:ff', '22:bb:cc:dd:ee:ff'],
            })
        parsed_result = json.loads(response.content)
        self.assertItemsEqual(
            [
                'hostname',
                'owner',
                'system_id',
                'macaddress_set',
                'architecture',
                'status',
                'netboot',
                'power_type',
                'resource_uri',
                'tag_names',
                'ip_addresses',
                'cpu_count',
                'storage',
                'memory',
                'routers',
            ],
            list(parsed_result))


class AdminLoggedInEnlistmentAPITest(AdminLoggedInTestCase):
    # Enlistment tests specific to admin users.

    def test_POST_new_creates_node_default_values_for_power_settings(self):
        architecture = factory.getRandomChoice(ARCHITECTURE_CHOICES)
        mac_address = 'AA:BB:CC:DD:EE:FF'
        response = self.client.post(
            reverse('nodes_handler'), {
                'op': 'new',
                'architecture': architecture,
                'mac_addresses': [mac_address],
                })
        node = Node.objects.get(
            system_id=json.loads(response.content)['system_id'])
        self.assertAttributes(
            node,
            dict(
                architecture=architecture, power_type=POWER_TYPE.DEFAULT,
                power_parameters=''))

    def test_POST_new_sets_power_type_if_admin(self):
        response = self.client.post(
            reverse('nodes_handler'), {
                'op': 'new',
                'architecture': factory.getRandomChoice(ARCHITECTURE_CHOICES),
                'power_type': POWER_TYPE.WAKE_ON_LAN,
                'mac_addresses': ['00:11:22:33:44:55'],
                })
        node = Node.objects.get(
            system_id=json.loads(response.content)['system_id'])
        self.assertEqual(POWER_TYPE.WAKE_ON_LAN, node.power_type)
        self.assertEqual('', node.power_parameters)

    def test_POST_new_sets_power_parameters_field(self):
        # The api allows the setting of a Node's power_parameters field.
        # Create a power_parameter valid for the selected power_type.
        new_mac_address = factory.getRandomMACAddress()
        response = self.client.post(
            reverse('nodes_handler'), {
                'op': 'new',
                'architecture': factory.getRandomChoice(ARCHITECTURE_CHOICES),
                'power_type': POWER_TYPE.WAKE_ON_LAN,
                'power_parameters_mac_address': new_mac_address,
                'mac_addresses': ['AA:BB:CC:DD:EE:FF'],
                })

        node = Node.objects.get(
            system_id=json.loads(response.content)['system_id'])
        self.assertEqual(httplib.OK, response.status_code)
        self.assertEqual(
            {'mac_address': new_mac_address},
            reload_object(node).power_parameters)

    def test_POST_updates_power_parameters_rejects_unknown_param(self):
        hostname = factory.getRandomString()
        response = self.client.post(
            reverse('nodes_handler'), {
                'op': 'new',
                'hostname': hostname,
                'architecture': factory.getRandomChoice(ARCHITECTURE_CHOICES),
                'power_type': POWER_TYPE.WAKE_ON_LAN,
                'power_parameters_unknown_param': factory.getRandomString(),
                'mac_addresses': [factory.getRandomMACAddress()],
                })

        self.assertEqual(
            (
                httplib.BAD_REQUEST,
                {'power_parameters': ["Unknown parameter(s): unknown_param."]}
            ),
            (response.status_code, json.loads(response.content)))
        self.assertFalse(Node.objects.filter(hostname=hostname).exists())

    def test_POST_new_sets_power_parameters_skip_check(self):
        # The api allows to skip the validation step and set arbitrary
        # power parameters.
        param = factory.getRandomString()
        response = self.client.post(
            reverse('nodes_handler'), {
                'op': 'new',
                'architecture': factory.getRandomChoice(ARCHITECTURE_CHOICES),
                'power_type': POWER_TYPE.WAKE_ON_LAN,
                'power_parameters_param': param,
                'power_parameters_skip_check': 'true',
                'mac_addresses': ['AA:BB:CC:DD:EE:FF'],
                })

        node = Node.objects.get(
            system_id=json.loads(response.content)['system_id'])
        self.assertEqual(httplib.OK, response.status_code)
        self.assertEqual(
            {'param': param},
            reload_object(node).power_parameters)

    def test_POST_admin_creates_node_in_commissioning_state(self):
        # When an admin user enlists a node, it goes into the
        # Commissioning state.
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
            NODE_STATUS.COMMISSIONING,
            Node.objects.get(system_id=system_id).status)

    def test_POST_returns_limited_fields(self):
        response = self.client.post(
            reverse('nodes_handler'),
            {
                'op': 'new',
                'hostname': factory.getRandomString(),
                'architecture': factory.getRandomChoice(ARCHITECTURE_CHOICES),
                'after_commissioning_action': (
                    NODE_AFTER_COMMISSIONING_ACTION.DEFAULT),
                'mac_addresses': ['aa:bb:cc:dd:ee:ff', '22:bb:cc:dd:ee:ff'],
            })
        parsed_result = json.loads(response.content)
        self.assertItemsEqual(
            [
                'hostname',
                'owner',
                'system_id',
                'macaddress_set',
                'architecture',
                'status',
                'netboot',
                'power_type',
                'resource_uri',
                'tag_names',
                'ip_addresses',
                'cpu_count',
                'storage',
                'memory',
                'routers',
            ],
            list(parsed_result))

    def test_POST_accept_all(self):
        # An admin user can accept all anonymously enlisted nodes.
        nodes = [
            factory.make_node(status=NODE_STATUS.DECLARED),
            factory.make_node(status=NODE_STATUS.DECLARED),
            ]
        response = self.client.post(
            reverse('nodes_handler'), {'op': 'accept_all'})
        self.assertEqual(httplib.OK, response.status_code)
        nodes_returned = json.loads(response.content)
        self.assertSetEqual(
            {node.system_id for node in nodes},
            {node["system_id"] for node in nodes_returned})
