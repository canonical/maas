# Copyright 2013-2014 Canonical Ltd.  This software is licensed under the
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
    NODE_BOOT,
    NODE_STATUS,
    NODEGROUP_STATUS,
    NODEGROUPINTERFACE_MANAGEMENT,
    )
from maasserver.models import (
    Node,
    node as node_module,
    NodeGroup,
    )
from maasserver.testing.api import MultipleUsersScenarios
from maasserver.testing.architecture import make_usable_architecture
from maasserver.testing.factory import factory
from maasserver.testing.orm import reload_object
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils import strip_domain
from maasserver.utils.orm import get_one
from netaddr import IPNetwork


class EnlistmentAPITest(MultipleUsersScenarios,
                        MAASServerTestCase):
    """Enlistment tests."""
    scenarios = [
        ('anon', dict(userfactory=lambda: AnonymousUser())),
        ('user', dict(userfactory=factory.make_User)),
        ('admin', dict(userfactory=factory.make_admin)),
        ]

    def setUp(self):
        super(EnlistmentAPITest, self).setUp()
        self.patch_autospec(node_module, 'wait_for_power_commands')

    def test_POST_new_creates_node(self):
        architecture = make_usable_architecture(self)
        response = self.client.post(
            reverse('nodes_handler'),
            {
                'op': 'new',
                'autodetect_nodegroup': '1',
                'hostname': 'diane',
                'architecture': architecture,
                'power_type': 'ether_wake',
                'mac_addresses': ['aa:bb:cc:dd:ee:ff', '22:bb:cc:dd:ee:ff'],
            })

        self.assertEqual(httplib.OK, response.status_code)
        parsed_result = json.loads(response.content)
        self.assertIn('application/json', response['Content-Type'])
        self.assertEqual('diane', parsed_result['hostname'])
        self.assertNotEqual(0, len(parsed_result.get('system_id')))
        [diane] = Node.objects.filter(hostname='diane')
        self.assertEqual(architecture, diane.architecture)
        self.assertEqual(NODE_BOOT.FASTPATH, diane.boot_type)

    def test_POST_new_generates_hostname_if_ip_based_hostname(self):
        hostname = '192-168-5-19.domain'
        response = self.client.post(
            reverse('nodes_handler'),
            {
                'op': 'new',
                'autodetect_nodegroup': '1',
                'hostname': hostname,
                'architecture': make_usable_architecture(self),
                'power_type': 'ether_wake',
                'mac_addresses': [factory.make_mac_address()],
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
        architecture = make_usable_architecture(self)
        power_type = 'ipmi'
        power_parameters = {
            "power_user": factory.make_name("power-user"),
            "power_pass": factory.make_name("power-pass"),
            }
        response = self.client.post(
            reverse('nodes_handler'),
            {
                'op': 'new',
                'autodetect_nodegroup': '1',
                'hostname': hostname,
                'architecture': architecture,
                'power_type': 'ether_wake',
                'mac_addresses': factory.make_mac_address(),
                'power_parameters': json.dumps(power_parameters),
                'power_type': power_type,
            })
        self.assertEqual(httplib.OK, response.status_code)
        [node] = Node.objects.filter(hostname=hostname)
        self.assertEqual(power_parameters, node.power_parameters)
        self.assertEqual(power_type, node.power_type)

    def test_POST_new_creates_node_with_arch_only(self):
        architecture = make_usable_architecture(self, subarch_name="generic")
        response = self.client.post(
            reverse('nodes_handler'),
            {
                'op': 'new',
                'autodetect_nodegroup': '1',
                'hostname': 'diane',
                'architecture': architecture.split('/')[0],
                'power_type': 'ether_wake',
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
        architecture = make_usable_architecture(self)
        response = self.client.post(
            reverse('nodes_handler'),
            {
                'op': 'new',
                'autodetect_nodegroup': '1',
                'hostname': 'diane',
                'architecture': architecture.split('/')[0],
                'subarchitecture': architecture.split('/')[1],
                'power_type': 'ether_wake',
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
        architecture = make_usable_architecture(self)
        response = self.client.post(
            reverse('nodes_handler'),
            {
                'op': 'new',
                'autodetect_nodegroup': '1',
                'hostname': 'diane',
                'architecture': architecture,
                'subarchitecture': architecture.split('/')[1],
                'mac_addresses': ['aa:bb:cc:dd:ee:ff', '22:bb:cc:dd:ee:ff'],
            })
        self.assertEqual(httplib.BAD_REQUEST, response.status_code)
        self.assertIn('text/plain', response['Content-Type'])
        self.assertEqual(
            "Subarchitecture cannot be specified twice.",
            response.content)

    def test_POST_new_associates_mac_addresses(self):
        # The API allows a Node to be created and associated with MAC
        # Addresses.
        architecture = make_usable_architecture(self)
        self.client.post(
            reverse('nodes_handler'),
            {
                'op': 'new',
                'autodetect_nodegroup': '1',
                'hostname': 'diane',
                'architecture': architecture,
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
                'autodetect_nodegroup': '1',
                'hostname': hostname,
                'architecture': make_usable_architecture(self),
                'mac_addresses': [factory.make_mac_address()],
            })
        self.assertEqual(
            NodeGroup.objects.ensure_master(),
            Node.objects.get(hostname=hostname).nodegroup)

    def test_POST_with_no_hostname_auto_populates_hostname(self):
        architecture = make_usable_architecture(self)
        response = self.client.post(
            reverse('nodes_handler'),
            {
                'op': 'new',
                'autodetect_nodegroup': '1',
                'architecture': architecture,
                'power_type': 'ether_wake',
                'mac_addresses': [factory.make_mac_address()],
            })
        node = Node.objects.get(
            system_id=json.loads(response.content)['system_id'])
        self.assertNotEqual("", strip_domain(node.hostname))

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
        self.assertIn('text/plain', response['Content-Type'])
        self.assertEqual(
            "Unrecognised signature: POST None",
            response.content)

    def test_POST_new_fails_if_autodetect_nodegroup_required(self):
        # If new() is called with no nodegroup, we require the client to
        # explicitly also supply autodetect_nodegroup (with any value)
        # to force the autodetection. If it's not supplied then an error
        # is raised.
        architecture = make_usable_architecture(self)
        response = self.client.post(
            reverse('nodes_handler'),
            {
                'op': 'new',
                'architecture': architecture,
                'power_type': 'ether_wake',
                'mac_addresses': [factory.make_mac_address()],
            })
        self.assertEqual(httplib.BAD_REQUEST, response.status_code)
        self.assertIn('text/plain', response['Content-Type'])
        self.assertEqual(
            "'autodetect_nodegroup' must be specified if 'nodegroup' "
            "parameter missing", response.content)

    def test_POST_fails_if_mac_duplicated(self):
        # Mac Addresses should be unique.
        mac = 'aa:bb:cc:dd:ee:ff'
        factory.make_MACAddress(mac)
        architecture = make_usable_architecture(self)
        response = self.client.post(
            reverse('nodes_handler'),
            {
                'op': 'new',
                'autodetect_nodegroup': '1',
                'architecture': architecture,
                'hostname': factory.make_string(),
                'mac_addresses': [mac],
            })
        parsed_result = json.loads(response.content)

        self.assertEqual(httplib.BAD_REQUEST, response.status_code)
        self.assertIn('application/json', response['Content-Type'])
        self.assertEqual(
            ["MAC address %s already in use." % mac],
            parsed_result['mac_addresses'])

    def test_POST_fails_with_bad_operation(self):
        # If the operation ('op=operation_name') specified in the
        # request data is unknown, a 'Bad request' response is returned.
        response = self.client.post(
            reverse('nodes_handler'),
            {
                'op': 'invalid_operation',
                'autodetect_nodegroup': '1',
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
                'autodetect_nodegroup': '1',
                'hostname': 'diane',
                'mac_addresses': ['aa:bb:cc:dd:ee:ff', 'invalid'],
            })
        parsed_result = json.loads(response.content)

        self.assertEqual(httplib.BAD_REQUEST, response.status_code)
        self.assertIn('application/json', response['Content-Type'])
        self.assertEqual(
            [
                "One or more MAC addresses is invalid. "
                "('invalid' is not a valid MAC address.)"
            ],
            parsed_result['mac_addresses'])

    def test_POST_invalid_architecture_returns_bad_request(self):
        # If the architecture name provided to create a node is not a valid
        # architecture name, a 'Bad request' response is returned.
        response = self.client.post(
            reverse('nodes_handler'),
            {
                'op': 'new',
                'autodetect_nodegroup': '1',
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

    def setUp(self):
        super(NodeHostnameEnlistmentTest, self).setUp()
        self.patch_autospec(node_module, 'wait_for_power_commands')

    scenarios = [
        ('anon', dict(userfactory=lambda: AnonymousUser())),
        ('user', dict(userfactory=factory.make_User)),
        ('admin', dict(userfactory=factory.make_admin)),
        ]

    def test_created_node_has_domain_from_cluster(self):
        hostname_without_domain = factory.make_name('hostname')
        hostname_with_domain = '%s.%s' % (
            hostname_without_domain, factory.make_string())
        domain = factory.make_name('domain')
        factory.make_NodeGroup(
            status=NODEGROUP_STATUS.ACCEPTED,
            name=domain,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS)
        response = self.client.post(
            reverse('nodes_handler'),
            {
                'op': 'new',
                'autodetect_nodegroup': '1',
                'hostname': hostname_with_domain,
                'architecture': make_usable_architecture(self),
                'power_type': 'ether_wake',
                'mac_addresses': [factory.make_mac_address()],
            })
        self.assertEqual(httplib.OK, response.status_code, response.content)
        parsed_result = json.loads(response.content)
        expected_hostname = '%s.%s' % (hostname_without_domain, domain)
        self.assertEqual(
            expected_hostname, parsed_result.get('hostname'))

    def test_created_node_gets_domain_from_cluster_appended(self):
        hostname_without_domain = factory.make_name('hostname')
        domain = factory.make_name('domain')
        factory.make_NodeGroup(
            status=NODEGROUP_STATUS.ACCEPTED,
            name=domain,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS)
        response = self.client.post(
            reverse('nodes_handler'),
            {
                'op': 'new',
                'autodetect_nodegroup': '1',
                'hostname': hostname_without_domain,
                'architecture': make_usable_architecture(self),
                'power_type': 'ether_wake',
                'mac_addresses': [factory.make_mac_address()],
            })
        self.assertEqual(httplib.OK, response.status_code, response.content)
        parsed_result = json.loads(response.content)
        expected_hostname = '%s.%s' % (hostname_without_domain, domain)
        self.assertEqual(
            expected_hostname, parsed_result.get('hostname'))

    def test_created_node_nodegroup_is_inferred_from_origin_network(self):
        network = IPNetwork('192.168.0.3/24')
        origin_ip = factory.pick_ip_in_network(network)
        NodeGroup.objects.ensure_master()
        nodegroup = factory.make_NodeGroup(
            network=network,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP)
        response = self.client.post(
            reverse('nodes_handler'),
            data={
                'op': 'new',
                'autodetect_nodegroup': '1',
                'hostname': factory.make_name('hostname'),
                'architecture': make_usable_architecture(self),
                'power_type': 'ether_wake',
                'mac_addresses': [factory.make_mac_address()],
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
                'autodetect_nodegroup': '1',
                'hostname': factory.make_name('hostname'),
                'architecture': make_usable_architecture(self),
                'power_type': 'ether_wake',
                'mac_addresses': [factory.make_mac_address()],
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
        ('user', dict(userfactory=factory.make_User)),
        ]

    def setUp(self):
        super(NonAdminEnlistmentAPITest, self).setUp()
        self.patch_autospec(node_module, 'wait_for_power_commands')

    def test_POST_non_admin_creates_node_in_declared_state(self):
        # Upon non-admin enlistment, a node goes into the New
        # state.  Deliberate approval is required before we start
        # reinstalling the system, wiping its disks etc.
        response = self.client.post(
            reverse('nodes_handler'),
            {
                'op': 'new',
                'autodetect_nodegroup': '1',
                'hostname': factory.make_string(),
                'architecture': make_usable_architecture(self),
                'mac_addresses': ['aa:bb:cc:dd:ee:ff'],
            })
        self.assertEqual(httplib.OK, response.status_code)
        system_id = json.loads(response.content)['system_id']
        self.assertEqual(
            NODE_STATUS.NEW,
            Node.objects.get(system_id=system_id).status)


class AnonymousEnlistmentAPITest(MAASServerTestCase):
    # Enlistment tests specific to anonymous users.

    def setUp(self):
        super(AnonymousEnlistmentAPITest, self).setUp()
        self.patch_autospec(node_module, 'wait_for_power_commands')

    def test_POST_accept_not_allowed(self):
        # An anonymous user is not allowed to accept an anonymously
        # enlisted node.  That would defeat the whole purpose of holding
        # those nodes for approval.
        node_id = factory.make_Node(status=NODE_STATUS.NEW).system_id
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
                'autodetect_nodegroup': '1',
                'architecture': make_usable_architecture(self),
                'hostname': factory.make_string(),
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
                'osystem',
                'distro_series',
                'netboot',
                'power_type',
                'tag_names',
                'ip_addresses',
                'resource_uri',
                'cpu_count',
                'storage',
                'memory',
                'routers',
                'zone',
                'disable_ipv4',
            ],
            list(parsed_result))


class SimpleUserLoggedInEnlistmentAPITest(MAASServerTestCase):
    """Enlistment tests from the perspective of regular, non-admin users."""

    def setUp(self):
        super(SimpleUserLoggedInEnlistmentAPITest, self).setUp()
        self.patch_autospec(node_module, 'wait_for_power_commands')

    def test_POST_accept_not_allowed(self):
        # An non-admin user is not allowed to accept an anonymously
        # enlisted node.  That would defeat the whole purpose of holding
        # those nodes for approval.
        self.client_log_in()
        node_id = factory.make_Node(status=NODE_STATUS.NEW).system_id
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
        self.client_log_in()
        factory.make_Node(status=NODE_STATUS.NEW),
        factory.make_Node(status=NODE_STATUS.NEW),
        response = self.client.post(
            reverse('nodes_handler'), {'op': 'accept_all'})
        self.assertEqual(httplib.OK, response.status_code)
        nodes_returned = json.loads(response.content)
        self.assertEqual([], nodes_returned)

    def test_POST_simple_user_can_set_power_type_and_parameters(self):
        self.client_log_in()
        new_power_address = factory.make_string()
        response = self.client.post(
            reverse('nodes_handler'), {
                'op': 'new',
                'autodetect_nodegroup': '1',
                'architecture': make_usable_architecture(self),
                'power_type': 'ether_wake',
                'power_parameters': json.dumps(
                    {"power_address": new_power_address}),
                'mac_addresses': ['AA:BB:CC:DD:EE:FF'],
                })

        node = Node.objects.get(
            system_id=json.loads(response.content)['system_id'])
        self.assertEqual(
            (httplib.OK, {"power_address": new_power_address},
             'ether_wake'),
            (response.status_code, node.power_parameters,
             node.power_type))

    def test_POST_returns_limited_fields(self):
        self.client_log_in()
        response = self.client.post(
            reverse('nodes_handler'),
            {
                'op': 'new',
                'autodetect_nodegroup': '1',
                'hostname': factory.make_string(),
                'architecture': make_usable_architecture(self),
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
                'substatus',
                'osystem',
                'distro_series',
                'netboot',
                'power_type',
                'resource_uri',
                'tag_names',
                'ip_addresses',
                'cpu_count',
                'storage',
                'memory',
                'routers',
                'zone',
                'disable_ipv4',
            ],
            list(parsed_result))


class AdminLoggedInEnlistmentAPITest(MAASServerTestCase):
    """Enlistment tests from the perspective of admin users."""

    def setUp(self):
        super(AdminLoggedInEnlistmentAPITest, self).setUp()
        self.patch_autospec(node_module, 'wait_for_power_commands')

    def test_POST_new_sets_power_type_if_admin(self):
        self.client_log_in(as_admin=True)
        response = self.client.post(
            reverse('nodes_handler'), {
                'op': 'new',
                'autodetect_nodegroup': '1',
                'architecture': make_usable_architecture(self),
                'power_type': 'ether_wake',
                'mac_addresses': ['00:11:22:33:44:55'],
                })
        node = Node.objects.get(
            system_id=json.loads(response.content)['system_id'])
        self.assertEqual('ether_wake', node.power_type)
        self.assertEqual('', node.power_parameters)

    def test_POST_new_sets_power_parameters_field(self):
        # The api allows the setting of a Node's power_parameters field.
        # Create a power_parameter valid for the selected power_type.
        self.client_log_in(as_admin=True)
        new_mac_address = factory.make_mac_address()
        response = self.client.post(
            reverse('nodes_handler'), {
                'op': 'new',
                'autodetect_nodegroup': '1',
                'architecture': make_usable_architecture(self),
                'power_type': 'ether_wake',
                'power_parameters_mac_address': new_mac_address,
                'mac_addresses': ['AA:BB:CC:DD:EE:FF'],
                })

        self.assertEqual(httplib.OK, response.status_code, response.content)
        node = Node.objects.get(
            system_id=json.loads(response.content)['system_id'])
        self.assertEqual(
            {'mac_address': new_mac_address},
            reload_object(node).power_parameters)

    def test_POST_updates_power_parameters_rejects_unknown_param(self):
        self.client_log_in(as_admin=True)
        hostname = factory.make_string()
        response = self.client.post(
            reverse('nodes_handler'), {
                'op': 'new',
                'autodetect_nodegroup': '1',
                'hostname': hostname,
                'architecture': make_usable_architecture(self),
                'power_type': 'ether_wake',
                'power_parameters_unknown_param': factory.make_string(),
                'mac_addresses': [factory.make_mac_address()],
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
        self.client_log_in(as_admin=True)
        param = factory.make_string()
        response = self.client.post(
            reverse('nodes_handler'), {
                'op': 'new',
                'autodetect_nodegroup': '1',
                'architecture': make_usable_architecture(self),
                'power_type': 'ether_wake',
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
        self.client_log_in(as_admin=True)
        response = self.client.post(
            reverse('nodes_handler'),
            {
                'op': 'new',
                'autodetect_nodegroup': '1',
                'hostname': factory.make_string(),
                'architecture': make_usable_architecture(self),
                'power_type': 'ether_wake',
                'mac_addresses': ['aa:bb:cc:dd:ee:ff'],
            })
        self.assertEqual(httplib.OK, response.status_code)
        system_id = json.loads(response.content)['system_id']
        self.assertEqual(
            NODE_STATUS.COMMISSIONING,
            Node.objects.get(system_id=system_id).status)

    def test_POST_returns_limited_fields(self):
        self.client_log_in(as_admin=True)
        response = self.client.post(
            reverse('nodes_handler'),
            {
                'op': 'new',
                'autodetect_nodegroup': '1',
                'hostname': factory.make_string(),
                'architecture': make_usable_architecture(self),
                'power_type': 'ether_wake',
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
                'substatus',
                'osystem',
                'distro_series',
                'netboot',
                'power_type',
                'resource_uri',
                'tag_names',
                'ip_addresses',
                'cpu_count',
                'storage',
                'memory',
                'routers',
                'zone',
                'disable_ipv4',
            ],
            list(parsed_result))

    def test_POST_accept_all(self):
        # An admin user can accept all anonymously enlisted nodes.
        self.client_log_in(as_admin=True)
        nodes = [
            factory.make_Node(status=NODE_STATUS.NEW),
            factory.make_Node(status=NODE_STATUS.NEW),
            ]
        response = self.client.post(
            reverse('nodes_handler'), {'op': 'accept_all'})
        self.assertEqual(httplib.OK, response.status_code)
        nodes_returned = json.loads(response.content)
        self.assertSetEqual(
            {node.system_id for node in nodes},
            {node["system_id"] for node in nodes_returned})
