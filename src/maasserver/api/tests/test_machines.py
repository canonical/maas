# Copyright 2013-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the machines API."""

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
from maasserver.api import (
    machines as machines_module,
    nodes as nodes_module,
)
from maasserver.api.utils import get_overridden_query_dict
from maasserver.enum import (
    INTERFACE_TYPE,
    NODE_STATUS,
    NODE_STATUS_CHOICES_DICT,
    NODE_TYPE,
    NODEGROUP_STATUS,
    NODEGROUPINTERFACE_MANAGEMENT,
    POWER_STATE,
)
from maasserver.exceptions import ClusterUnavailable
from maasserver.models import (
    Config,
    Machine,
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
    Not,
)


class TestGetStorageLayoutParams(MAASServerTestCase):

    def test_sets_request_data_to_mutable(self):
        data = {
            'op': 'acquire',
            'storage_layout': 'flat',
        }
        request = RequestFactory().post(reverse('machines_handler'), data)
        request.data = request.POST.copy()
        request.data._mutable = False
        machines_module.get_storage_layout_params(request)
        self.assertTrue(request.data._mutable)


class MachineHostnameTest(
        MultipleUsersScenarios, MAASServerTestCase):

    scenarios = [
        ('user', dict(userfactory=factory.make_User)),
        ('admin', dict(userfactory=factory.make_admin)),
    ]

    def test_GET_returns_fqdn_with_domain_name_from_cluster(self):
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
        response = self.client.get(reverse('machines_handler'))
        self.assertEqual(
            http.client.OK.value, response.status_code, response.content)
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))
        self.assertItemsEqual(
            [expected_hostname],
            [machine.get('hostname') for machine in parsed_result])


class AnonymousIsRegisteredAPITest(MAASServerTestCase):

    def test_is_registered_returns_True_if_machine_registered(self):
        mac_address = factory.make_mac_address()
        factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, mac_address=mac_address)
        response = self.client.get(
            reverse('machines_handler'),
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
            reverse('machines_handler'),
            {
                'op': 'is_registered',
                'mac_address': non_normalized_mac_address2
            })
        self.assertEqual(
            (http.client.OK.value, "true"),
            (response.status_code,
             response.content.decode(settings.DEFAULT_CHARSET)))

    def test_is_registered_returns_False_if_machine_not_registered(self):
        mac_address = factory.make_mac_address()
        response = self.client.get(
            reverse('machines_handler'),
            {'op': 'is_registered', 'mac_address': mac_address})
        self.assertEqual(
            (http.client.OK.value, "false"),
            (response.status_code,
             response.content.decode(settings.DEFAULT_CHARSET)))


def extract_system_ids(parsed_result):
    """List the system_ids of the machines in `parsed_result`."""
    return [machine.get('system_id') for machine in parsed_result]


def extract_system_ids_from_machines(machines):
    return [machine.system_id for machine in machines]


class RequestFixture:
    def __init__(self, dict, fields):
        self.user = factory.make_User()
        self.GET = get_overridden_query_dict(dict, QueryDict(''), fields)


class TestMachinesAPI(APITestCase):
    """Tests for /api/1.0/machines/."""

    def test_handler_path(self):
        self.assertEqual(
            '/api/1.0/machines/', reverse('machines_handler'))

    def test_POST_new_creates_machine(self):
        # The API allows a non-admin logged-in user to create a Machine.
        hostname = factory.make_name('host')
        architecture = make_usable_architecture(self)
        macs = {
            factory.make_mac_address()
            for _ in range(random.randint(1, 2))
        }
        response = self.client.post(
            reverse('machines_handler'),
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
        machine = Machine.objects.get(system_id=system_id)
        self.expectThat(machine.hostname, Equals(hostname))
        self.expectThat(machine.architecture, Equals(architecture))
        self.expectThat(
            {nic.mac_address for nic in machine.interface_set.all()},
            Equals(macs))

    def test_POST_new_when_logged_in_creates_machine_in_declared_state(self):
        # When a user enlists a machine, it goes into the New state.
        # This will change once we start doing proper commissioning.
        response = self.client.post(
            reverse('machines_handler'),
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
            reverse('machines_handler'),
            {
                'op': 'new',
                'nodegroup': cluster.id,
                'architecture': make_usable_architecture(self),
                'mac_addresses': [factory.make_mac_address()],
            })
        self.assertEqual(http.client.OK, response.status_code)
        system_id = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))['system_id']
        machine = Machine.objects.get(system_id=system_id)
        self.assertEqual(default_disable_ipv4, machine.disable_ipv4)

    def test_POST_new_takes_default_disable_ipv4_from_guessed_cluster(self):
        default_disable_ipv4 = factory.pick_bool()
        master_cluster = NodeGroup.objects.ensure_master()
        master_cluster.default_disable_ipv4 = default_disable_ipv4
        master_cluster.save()
        response = self.client.post(
            reverse('machines_handler'),
            {
                'op': 'new',
                'autodetect_nodegroup': '1',
                'architecture': make_usable_architecture(self),
                'mac_addresses': [factory.make_mac_address()],
            })
        self.assertEqual(http.client.OK, response.status_code)
        system_id = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))['system_id']
        machine = Machine.objects.get(system_id=system_id)
        self.assertEqual(default_disable_ipv4, machine.disable_ipv4)

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
            reverse('machines_handler'),
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

    def test_GET_lists_machines(self):
        # The api allows for fetching the list of Machines.
        machine1 = factory.make_Node()
        machine2 = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=self.logged_in_user)
        response = self.client.get(reverse('machines_handler'))
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))

        self.assertEqual(http.client.OK, response.status_code)
        self.assertItemsEqual(
            [machine1.system_id, machine2.system_id],
            extract_system_ids(parsed_result))

    def create_machines(self, nodegroup, nb):
        for _ in range(nb):
            factory.make_Node(nodegroup=nodegroup, interface=True)

    def test_GET_machines_issues_constant_number_of_queries(self):
        # XXX: GavinPanella 2014-10-03 bug=1377335
        self.skip("Unreliable; something is causing varying counts.")

        nodegroup = factory.make_NodeGroup()
        self.create_machines(nodegroup, 10)
        num_queries1, response1 = count_queries(
            self.client.get, reverse('machines_handler'))
        self.create_machines(nodegroup, 10)
        num_queries2, response2 = count_queries(
            self.client.get, reverse('machines_handler'))
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

    def test_GET_without_machines_returns_empty_list(self):
        # If there are no machines to list, the "read" op still works but
        # returns an empty list.
        response = self.client.get(reverse('machines_handler'))
        self.assertItemsEqual(
            [], json.loads(response.content.decode(settings.DEFAULT_CHARSET)))

    def test_GET_orders_by_id(self):
        # Machines are returned in id order.
        machines = [factory.make_Node() for counter in range(3)]
        response = self.client.get(reverse('machines_handler'))
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))
        self.assertSequenceEqual(
            [machine.system_id for machine in machines],
            extract_system_ids(parsed_result))

    def test_GET_with_id_returns_matching_machines(self):
        # The "read" operation takes optional "id" parameters.  Only
        # machines with matching ids will be returned.
        ids = [factory.make_Node().system_id for counter in range(3)]
        matching_id = ids[0]
        response = self.client.get(reverse('machines_handler'), {
            'id': [matching_id],
        })
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))
        self.assertItemsEqual(
            [matching_id], extract_system_ids(parsed_result))

    def test_GET_with_nonexistent_id_returns_empty_list(self):
        # Trying to list a nonexistent machine id returns a list containing
        # no machines -- even if other (non-matching) machines exist.
        existing_id = factory.make_Node().system_id
        nonexistent_id = existing_id + factory.make_string()
        response = self.client.get(reverse('machines_handler'), {
            'id': [nonexistent_id],
        })
        self.assertItemsEqual([], json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)))

    def test_GET_with_ids_orders_by_id(self):
        # Even when ids are passed to "list," machines are returned in id
        # order, not necessarily in the order of the id arguments.
        ids = [factory.make_Node().system_id for counter in range(3)]
        response = self.client.get(reverse('machines_handler'), {
            'id': list(reversed(ids)),
        })
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))
        self.assertSequenceEqual(ids, extract_system_ids(parsed_result))

    def test_GET_with_some_matching_ids_returns_matching_machines(self):
        # If some machines match the requested ids and some don't, only the
        # matching ones are returned.
        existing_id = factory.make_Node().system_id
        nonexistent_id = existing_id + factory.make_string()
        response = self.client.get(reverse('machines_handler'), {
            'id': [existing_id, nonexistent_id],
        })
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))
        self.assertItemsEqual(
            [existing_id], extract_system_ids(parsed_result))

    def test_GET_with_hostname_returns_matching_machines(self):
        # The read operation takes optional "hostname" parameters. Only
        # machines with matching hostnames will be returned.
        machines = [factory.make_Node() for _ in range(3)]
        matching_hostname = machines[0].hostname
        matching_system_id = machines[0].system_id
        response = self.client.get(reverse('machines_handler'), {
            'hostname': [matching_hostname],
        })
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))
        self.assertItemsEqual(
            [matching_system_id], extract_system_ids(parsed_result))

    def test_GET_with_macs_returns_matching_machines(self):
        # The "read" operation takes optional "mac_address" parameters. Only
        # machines with matching MAC addresses will be returned.
        interfaces = [
            factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
            for _ in range(3)
        ]
        matching_mac = interfaces[0].mac_address
        matching_system_id = interfaces[0].node.system_id
        response = self.client.get(reverse('machines_handler'), {
            'mac_address': [matching_mac],
        })
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))
        self.assertItemsEqual(
            [matching_system_id], extract_system_ids(parsed_result))

    def test_GET_with_invalid_macs_returns_sensible_error(self):
        # If specifying an invalid MAC, make sure the error that's
        # returned is not a crazy stack trace, but something nice to
        # humans.
        bad_mac1 = '00:E0:81:DD:D1:ZZ'  # ZZ is bad.
        bad_mac2 = '00:E0:81:DD:D1:XX'  # XX is bad.
        ok_mac = str(
            factory.make_Interface(INTERFACE_TYPE.PHYSICAL).mac_address)
        response = self.client.get(reverse('machines_handler'), {
            'mac_address': [bad_mac1, bad_mac2, ok_mac],
        })
        self.assertEqual(http.client.BAD_REQUEST, response.status_code)
        self.assertIn(
            "Invalid MAC address(es): 00:E0:81:DD:D1:ZZ, 00:E0:81:DD:D1:XX",
            response.content.decode(settings.DEFAULT_CHARSET))

    def test_GET_with_agent_name_filters_by_agent_name(self):
        non_listed_machine = factory.make_Node(
            agent_name=factory.make_name('agent_name'))
        ignore_unused(non_listed_machine)
        agent_name = factory.make_name('agent-name')
        machine = factory.make_Node(agent_name=agent_name)
        response = self.client.get(reverse('machines_handler'), {
            'agent_name': agent_name,
        })
        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))
        self.assertSequenceEqual(
            [machine.system_id], extract_system_ids(parsed_result))

    def test_GET_with_agent_name_filters_with_empty_string(self):
        factory.make_Node(agent_name=factory.make_name('agent-name'))
        machine = factory.make_Node(agent_name='')
        response = self.client.get(reverse('machines_handler'), {
            'agent_name': '',
        })
        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))
        self.assertSequenceEqual(
            [machine.system_id], extract_system_ids(parsed_result))

    def test_GET_without_agent_name_does_not_filter(self):
        machines = [
            factory.make_Node(agent_name=factory.make_name('agent-name'))
            for _ in range(3)]
        response = self.client.get(reverse('machines_handler'))
        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))
        self.assertSequenceEqual(
            [machine.system_id for machine in machines],
            extract_system_ids(parsed_result))

    def test_GET_doesnt_list_devices(self):
        machines = [
            factory.make_Node(agent_name=factory.make_name('agent-name'))
            for _ in range(3)]
        # Create devices.
        machines = [
            factory.make_Node(node_type=NODE_TYPE.DEVICE)
            for _ in range(3)]
        response = self.client.get(reverse('machines_handler'))
        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))
        system_ids = extract_system_ids(parsed_result)
        self.assertEqual(
            [],
            [machine.system_id
             for machine in machines if machine.system_id in system_ids],
            "Machine listing contains devices.")

    def test_GET_with_zone_filters_by_zone(self):
        non_listed_machine = factory.make_Node(
            zone=factory.make_Zone(name='twilight'))
        ignore_unused(non_listed_machine)
        zone = factory.make_Zone()
        machine = factory.make_Node(zone=zone)
        response = self.client.get(reverse('machines_handler'), {
            'zone': zone.name,
        })
        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))
        self.assertSequenceEqual(
            [machine.system_id], extract_system_ids(parsed_result))

    def test_GET_without_zone_does_not_filter(self):
        machines = [
            factory.make_Node(zone=factory.make_Zone())
            for _ in range(3)]
        response = self.client.get(reverse('machines_handler'))
        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))
        self.assertSequenceEqual(
            [machine.system_id for machine in machines],
            extract_system_ids(parsed_result))

    def test_GET_list_allocated_returns_only_allocated_with_user_token(self):
        # If the user's allocated machines have different session tokens,
        # list_allocated should only return the machines that have the
        # current request's token on them.
        machine_1 = factory.make_Node(
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

        # At this point we have two machines owned by the same user but
        # allocated with different tokens, and a third machine allocated to
        # someone else entirely.  We expect list_allocated to
        # return the machine with the same token as the one used in
        # self.client, which is the one we set on machine_1 above.

        response = self.client.get(reverse('machines_handler'), {
            'op': 'list_allocated'})
        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))
        self.assertItemsEqual(
            [machine_1.system_id], extract_system_ids(parsed_result))

    def test_GET_list_allocated_filters_by_id(self):
        # list_allocated takes an optional list of 'id' parameters to
        # filter returned results.
        current_token = get_auth_tokens(self.logged_in_user)[0]
        machines = []
        for _ in range(3):
            machines.append(factory.make_Node(
                status=NODE_STATUS.ALLOCATED,
                owner=self.logged_in_user, token=current_token))

        required_machine_ids = [machines[0].system_id, machines[1].system_id]
        response = self.client.get(reverse('machines_handler'), {
            'op': 'list_allocated',
            'id': required_machine_ids,
        })
        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))
        self.assertItemsEqual(
            required_machine_ids, extract_system_ids(parsed_result))

    def test_POST_acquire_returns_available_machine(self):
        # The "acquire" operation returns an available machine.
        available_status = NODE_STATUS.READY
        machine = factory.make_Node(
            status=available_status, owner=None, with_boot_disk=True)
        response = self.client.post(
            reverse('machines_handler'), {'op': 'acquire'})
        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))
        self.assertEqual(machine.system_id, parsed_result['system_id'])

    def test_POST_acquire_allocates_machine(self):
        # The "acquire" operation allocates the machine it returns.
        available_status = NODE_STATUS.READY
        machine = factory.make_Node(
            status=available_status, owner=None, with_boot_disk=True)
        self.client.post(reverse('machines_handler'), {'op': 'acquire'})
        machine = Machine.objects.get(system_id=machine.system_id)
        self.assertEqual(self.logged_in_user, machine.owner)

    def test_POST_acquire_uses_machine_acquire_lock(self):
        # The "acquire" operation allocates the machine it returns.
        available_status = NODE_STATUS.READY
        factory.make_Node(
            status=available_status, owner=None, with_boot_disk=True)
        machine_acquire = self.patch(machines_module.locks, 'node_acquire')
        self.client.post(reverse('machines_handler'), {'op': 'acquire'})
        self.assertThat(machine_acquire.__enter__, MockCalledOnceWith())
        self.assertThat(
            machine_acquire.__exit__, MockCalledOnceWith(None, None, None))

    def test_POST_acquire_sets_agent_name(self):
        available_status = NODE_STATUS.READY
        machine = factory.make_Node(
            status=available_status, owner=None,
            agent_name=factory.make_name('agent-name'), with_boot_disk=True)
        agent_name = factory.make_name('agent-name')
        self.client.post(
            reverse('machines_handler'),
            {'op': 'acquire', 'agent_name': agent_name})
        machine = Machine.objects.get(system_id=machine.system_id)
        self.assertEqual(agent_name, machine.agent_name)

    def test_POST_acquire_agent_name_defaults_to_empty_string(self):
        available_status = NODE_STATUS.READY
        agent_name = factory.make_name('agent-name')
        machine = factory.make_Node(
            status=available_status, owner=None, agent_name=agent_name,
            with_boot_disk=True)
        self.client.post(reverse('machines_handler'), {'op': 'acquire'})
        machine = Machine.objects.get(system_id=machine.system_id)
        self.assertEqual('', machine.agent_name)

    def test_POST_acquire_fails_if_no_machine_present(self):
        # The "acquire" operation returns a Conflict error if no machines
        # are available.
        response = self.client.post(
            reverse('machines_handler'), {'op': 'acquire'})
        # Fails with Conflict error: resource can't satisfy request.
        self.assertEqual(http.client.CONFLICT, response.status_code)

    def test_POST_acquire_failure_shows_no_constraints_if_none_given(self):
        response = self.client.post(
            reverse('machines_handler'), {'op': 'acquire'})
        self.assertEqual(http.client.CONFLICT, response.status_code)
        self.assertEqual(
            "No machine available.",
            response.content.decode(settings.DEFAULT_CHARSET))

    def test_POST_acquire_failure_shows_constraints_if_given(self):
        hostname = factory.make_name('host')
        response = self.client.post(
            reverse('machines_handler'), {
                'op': 'acquire',
                'name': hostname,
            })
        expected_response = (
            "No available machine matches constraints: name=%s" % hostname
        ).encode(settings.DEFAULT_CHARSET)
        self.assertEqual(http.client.CONFLICT, response.status_code)
        self.assertEqual(expected_response, response.content)

    def test_POST_acquire_ignores_already_allocated_machine(self):
        factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=factory.make_User(),
            with_boot_disk=True)
        response = self.client.post(
            reverse('machines_handler'), {'op': 'acquire'})
        self.assertEqual(http.client.CONFLICT, response.status_code)

    def test_POST_acquire_chooses_candidate_matching_constraint(self):
        # If "acquire" is passed a constraint, it will go for a machine
        # matching that constraint even if there's tons of other machines
        # available.
        # (Creating lots of machines here to minimize the chances of this
        # passing by accident).
        available_machines = [
            factory.make_Node(
                status=NODE_STATUS.READY, owner=None, with_boot_disk=True)
            for counter in range(20)]
        desired_machine = random.choice(available_machines)
        response = self.client.post(reverse('machines_handler'), {
            'op': 'acquire',
            'name': desired_machine.hostname,
        })
        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))
        domain_name = desired_machine.nodegroup.name
        self.assertEqual(
            "%s.%s" % (desired_machine.hostname, domain_name),
            parsed_result['hostname'])

    def test_POST_acquire_would_rather_fail_than_disobey_constraint(self):
        # If "acquire" is passed a constraint, it won't return a machine
        # that does not meet that constraint.  Even if it means that it
        # can't meet the request.
        factory.make_Node(
            status=NODE_STATUS.READY, owner=None, with_boot_disk=True)
        desired_machine = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=factory.make_User())
        response = self.client.post(reverse('machines_handler'), {
            'op': 'acquire',
            'name': desired_machine.system_id,
        })
        self.assertEqual(http.client.CONFLICT, response.status_code)

    def test_POST_acquire_ignores_unknown_constraint(self):
        machine = factory.make_Node(
            status=NODE_STATUS.READY, owner=None, with_boot_disk=True)
        response = self.client.post(reverse('machines_handler'), {
            'op': 'acquire',
            factory.make_string(): factory.make_string(),
        })
        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))
        self.assertEqual(machine.system_id, parsed_result['system_id'])

    def test_POST_acquire_allocates_machine_by_name(self):
        # Positive test for name constraint.
        # If a name constraint is given, "acquire" attempts to allocate
        # a machine of that name.
        machine = factory.make_Node(
            status=NODE_STATUS.READY, owner=None, with_boot_disk=True)
        response = self.client.post(reverse('machines_handler'), {
            'op': 'acquire',
            'name': machine.hostname,
        })
        self.assertEqual(http.client.OK, response.status_code)
        nodegroup = NodeGroup.objects.ensure_master()
        domain_name = nodegroup.name
        self.assertEqual(
            "%s.%s" % (machine.hostname, domain_name),
            json.loads(
                response.content.decode(settings.DEFAULT_CHARSET))['hostname'])

    def test_POST_acquire_treats_unknown_name_as_resource_conflict(self):
        # A name constraint naming an unknown machine produces a resource
        # conflict: most likely the machine existed but has changed or
        # disappeared.
        # Certainly it's not a 404, since the resource named in the URL
        # is "machines/," which does exist.
        factory.make_Node(
            status=NODE_STATUS.READY, owner=None, with_boot_disk=True)
        response = self.client.post(reverse('machines_handler'), {
            'op': 'acquire',
            'name': factory.make_string(),
        })
        self.assertEqual(http.client.CONFLICT, response.status_code)

    def test_POST_acquire_allocates_machine_by_arch(self):
        # Asking for a particular arch acquires a machine with that arch.
        arch = make_usable_architecture(self)
        machine = factory.make_Node(
            status=NODE_STATUS.READY, architecture=arch, with_boot_disk=True)
        response = self.client.post(reverse('machines_handler'), {
            'op': 'acquire',
            'arch': arch,
        })
        self.assertEqual(http.client.OK, response.status_code)
        response_json = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))
        self.assertEqual(machine.architecture, response_json['architecture'])

    def test_POST_acquire_treats_unknown_arch_as_bad_request(self):
        # Asking for an unknown arch returns an HTTP "400 Bad Request"
        factory.make_Node(
            status=NODE_STATUS.READY, with_boot_disk=True)
        response = self.client.post(reverse('machines_handler'), {
            'op': 'acquire',
            'arch': 'sparc',
        })
        self.assertEqual(http.client.BAD_REQUEST, response.status_code)

    def test_POST_acquire_allocates_machine_by_cpu(self):
        # Asking for enough cpu acquires a machine with at least that.
        machine = factory.make_Node(
            status=NODE_STATUS.READY, cpu_count=3, with_boot_disk=True)
        response = self.client.post(reverse('machines_handler'), {
            'op': 'acquire',
            'cpu_count': 2,
        })
        self.assertResponseCode(http.client.OK, response)
        response_json = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))
        self.assertEqual(machine.system_id, response_json['system_id'])

    def test_POST_acquire_allocates_machine_by_float_cpu(self):
        # Asking for a needlessly precise number of cpus works.
        machine = factory.make_Node(
            status=NODE_STATUS.READY, cpu_count=1, with_boot_disk=True)
        response = self.client.post(reverse('machines_handler'), {
            'op': 'acquire',
            'cpu_count': '1.0',
        })
        self.assertResponseCode(http.client.OK, response)
        response_json = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))
        self.assertEqual(machine.system_id, response_json['system_id'])

    def test_POST_acquire_fails_with_invalid_cpu(self):
        # Asking for an invalid amount of cpu returns a bad request.
        factory.make_Node(
            status=NODE_STATUS.READY, with_boot_disk=True)
        response = self.client.post(reverse('machines_handler'), {
            'op': 'acquire',
            'cpu_count': 'plenty',
        })
        self.assertResponseCode(http.client.BAD_REQUEST, response)

    def test_POST_acquire_allocates_machine_by_mem(self):
        # Asking for enough memory acquires a machine with at least that.
        machine = factory.make_Node(
            status=NODE_STATUS.READY, memory=1024, with_boot_disk=True)
        response = self.client.post(reverse('machines_handler'), {
            'op': 'acquire',
            'mem': 1024,
        })
        self.assertResponseCode(http.client.OK, response)
        response_json = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))
        self.assertEqual(machine.system_id, response_json['system_id'])

    def test_POST_acquire_fails_with_invalid_mem(self):
        # Asking for an invalid amount of memory returns a bad request.
        factory.make_Node(
            status=NODE_STATUS.READY, with_boot_disk=True)
        response = self.client.post(reverse('machines_handler'), {
            'op': 'acquire',
            'mem': 'bags',
        })
        self.assertResponseCode(http.client.BAD_REQUEST, response)

    def test_POST_acquire_allocates_machine_by_tags(self):
        machine = factory.make_Node(
            status=NODE_STATUS.READY, with_boot_disk=True)
        machine_tag_names = ["fast", "stable", "cute"]
        machine.tags = [factory.make_Tag(t) for t in machine_tag_names]
        # Legacy call using comma-separated tags.
        response = self.client.post(reverse('machines_handler'), {
            'op': 'acquire',
            'tags': ['fast', 'stable'],
        })
        self.assertResponseCode(http.client.OK, response)
        response_json = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))
        self.assertItemsEqual(machine_tag_names, response_json['tag_names'])

    def test_POST_acquire_allocates_machine_by_negated_tags(self):
        tagged_machine = factory.make_Node(
            status=NODE_STATUS.READY, with_boot_disk=True)
        partially_tagged_machine = factory.make_Node(
            status=NODE_STATUS.READY, with_boot_disk=True)
        machine_tag_names = ["fast", "stable", "cute"]
        tags = [factory.make_Tag(t) for t in machine_tag_names]
        tagged_machine.tags = tags
        partially_tagged_machine.tags = tags[:-1]
        # Legacy call using comma-separated tags.
        response = self.client.post(reverse('machines_handler'), {
            'op': 'acquire',
            'not_tags': ['cute']
        })
        self.assertResponseCode(http.client.OK, response)
        response_json = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))
        self.assertEqual(
            partially_tagged_machine.system_id,
            response_json['system_id'])
        self.assertItemsEqual(
            machine_tag_names[:-1], response_json['tag_names'])

    def test_POST_acquire_allocates_machine_by_zone(self):
        factory.make_Node(
            status=NODE_STATUS.READY, with_boot_disk=True)
        zone = factory.make_Zone()
        machine = factory.make_Node(
            status=NODE_STATUS.READY, zone=zone, with_boot_disk=True)
        response = self.client.post(reverse('machines_handler'), {
            'op': 'acquire',
            'zone': zone.name,
        })
        self.assertResponseCode(http.client.OK, response)
        response_json = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))
        self.assertEqual(machine.system_id, response_json['system_id'])

    def test_POST_acquire_allocates_machine_by_zone_fails_if_no_machine(self):
        factory.make_Node(
            status=NODE_STATUS.READY, with_boot_disk=True)
        zone = factory.make_Zone()
        response = self.client.post(reverse('machines_handler'), {
            'op': 'acquire',
            'zone': zone.name,
        })
        self.assertResponseCode(http.client.CONFLICT, response)

    def test_POST_acquire_rejects_unknown_zone(self):
        response = self.client.post(reverse('machines_handler'), {
            'op': 'acquire',
            'zone': factory.make_name('zone'),
        })
        self.assertEqual(http.client.BAD_REQUEST, response.status_code)

    def test_POST_acquire_allocates_machine_by_tags_comma_separated(self):
        machine = factory.make_Node(
            status=NODE_STATUS.READY, with_boot_disk=True)
        machine_tag_names = ["fast", "stable", "cute"]
        machine.tags = [factory.make_Tag(t) for t in machine_tag_names]
        # Legacy call using comma-separated tags.
        response = self.client.post(reverse('machines_handler'), {
            'op': 'acquire',
            'tags': 'fast, stable',
        })
        self.assertResponseCode(http.client.OK, response)
        response_json = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))
        self.assertItemsEqual(machine_tag_names, response_json['tag_names'])

    def test_POST_acquire_allocates_machine_by_tags_space_separated(self):
        machine = factory.make_Node(
            status=NODE_STATUS.READY, with_boot_disk=True)
        machine_tag_names = ["fast", "stable", "cute"]
        machine.tags = [factory.make_Tag(t) for t in machine_tag_names]
        # Legacy call using space-separated tags.
        response = self.client.post(reverse('machines_handler'), {
            'op': 'acquire',
            'tags': 'fast stable',
        })
        self.assertResponseCode(http.client.OK, response)
        response_json = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))
        self.assertItemsEqual(machine_tag_names, response_json['tag_names'])

    def test_POST_acquire_allocates_machine_by_tags_comma_space_delim(self):
        machine = factory.make_Node(
            status=NODE_STATUS.READY, with_boot_disk=True)
        machine_tag_names = ["fast", "stable", "cute"]
        machine.tags = [factory.make_Tag(t) for t in machine_tag_names]
        # Legacy call using comma-and-space-separated tags.
        response = self.client.post(reverse('machines_handler'), {
            'op': 'acquire',
            'tags': 'fast, stable cute',
        })
        self.assertResponseCode(http.client.OK, response)
        response_json = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))
        self.assertItemsEqual(machine_tag_names, response_json['tag_names'])

    def test_POST_acquire_allocates_machine_by_tags_mixed_input(self):
        machine = factory.make_Node(
            status=NODE_STATUS.READY, with_boot_disk=True)
        machine_tag_names = ["fast", "stable", "cute"]
        machine.tags = [factory.make_Tag(t) for t in machine_tag_names]
        # Mixed call using comma-separated tags in a list.
        response = self.client.post(reverse('machines_handler'), {
            'op': 'acquire',
            'tags': ['fast, stable', 'cute'],
        })
        self.assertResponseCode(http.client.OK, response)
        response_json = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))
        self.assertItemsEqual(machine_tag_names, response_json['tag_names'])

    def test_POST_acquire_allocates_machine_by_storage(self):
        """Storage label is returned alongside machine data"""
        machine = factory.make_Node(
            status=NODE_STATUS.READY, with_boot_disk=False)
        # The ID may always be '1', which won't be interesting for testing.
        for _ in range(1, random.choice([1, 3, 5])):
            factory.make_PhysicalBlockDevice()
        factory.make_PhysicalBlockDevice(
            node=machine, size=11 * (1000 ** 3), tags=['ssd'])
        response = self.client.post(reverse('machines_handler'), {
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

    def test_POST_acquire_allocates_machine_by_storage_with_verbose(self):
        """Storage label is returned alongside machine data"""
        machine = factory.make_Node(
            status=NODE_STATUS.READY, with_boot_disk=False)
        # The ID may always be '1', which won't be interesting for testing.
        for _ in range(1, random.choice([1, 3, 5])):
            factory.make_PhysicalBlockDevice()
        factory.make_PhysicalBlockDevice(
            node=machine, size=11 * (1000 ** 3), tags=['ssd'])
        response = self.client.post(reverse('machines_handler'), {
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
        self.expectThat(verbose_storage, Contains(str(machine.id)))
        self.expectThat(
            verbose_storage[str(machine.id)], Equals(constraint_map))

    def test_POST_acquire_allocates_machine_by_interfaces(self):
        """Interface label is returned alongside machine data"""
        fabric = factory.make_Fabric('ubuntu')
        # The ID may always be '1', which won't be interesting for testing.
        for _ in range(1, random.choice([1, 3, 5])):
            factory.make_Interface()
        machine = factory.make_Node_with_Interface_on_Subnet(
            status=NODE_STATUS.READY, fabric=fabric)
        iface = machine.get_boot_interface()
        response = self.client.post(reverse('machines_handler'), {
            'op': 'acquire',
            'interfaces': 'needed:fabric=ubuntu',
        })
        self.assertResponseCode(http.client.OK, response)
        response_json = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))
        self.expectThat(
            response_json['status'], Equals(NODE_STATUS.ALLOCATED))
        constraints = response_json['constraints_by_type']
        self.expectThat(constraints, Contains('interfaces'))
        interfaces = constraints.get('interfaces')
        self.expectThat(interfaces, Contains('needed'))
        self.expectThat(interfaces['needed'], Contains(iface.id))
        self.expectThat(constraints, Not(Contains('verbose_interfaces')))

    def test_POST_acquire_allocates_machine_by_interfaces_dry_run_with_verbose(
            self):
        """Interface label is returned alongside machine data"""
        fabric = factory.make_Fabric('ubuntu')
        # The ID may always be '1', which won't be interesting for testing.
        for _ in range(1, random.choice([1, 3, 5])):
            factory.make_Interface()
        machine = factory.make_Node_with_Interface_on_Subnet(
            status=NODE_STATUS.READY, fabric=fabric)
        iface = machine.get_boot_interface()
        response = self.client.post(reverse('machines_handler'), {
            'op': 'acquire',
            'interfaces': 'needed:fabric=ubuntu',
            'verbose': 'true',
            'dry_run': 'true',
        })
        self.assertResponseCode(http.client.OK, response)
        response_json = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))
        self.expectThat(
            response_json['status'], Equals(NODE_STATUS.READY))
        # Check that we still got the verbose constraints output even if
        # it was a dry run.
        constraints = response_json['constraints_by_type']
        self.expectThat(constraints, Contains('interfaces'))
        interfaces = constraints.get('interfaces')
        self.expectThat(interfaces, Contains('needed'))
        self.expectThat(interfaces['needed'], Contains(iface.id))
        verbose_interfaces = constraints.get('verbose_interfaces')
        self.expectThat(
            verbose_interfaces['needed'], Contains(str(machine.id)))
        self.expectThat(
            verbose_interfaces['needed'][str(machine.id)],
            Contains(iface.id))

    def test_POST_acquire_allocates_machine_by_interfaces_with_verbose(self):
        """Interface label is returned alongside machine data"""
        fabric = factory.make_Fabric('ubuntu')
        # The ID may always be '1', which won't be interesting for testing.
        for _ in range(1, random.choice([1, 3, 5])):
            factory.make_Interface()
        factory.make_Node()
        machine = factory.make_Node_with_Interface_on_Subnet(
            status=NODE_STATUS.READY, fabric=fabric)
        iface = machine.get_boot_interface()
        response = self.client.post(reverse('machines_handler'), {
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
            verbose_interfaces['needed'], Contains(str(machine.id)))
        self.expectThat(
            verbose_interfaces['needed'][str(machine.id)],
            Contains(iface.id))

    def test_POST_acquire_fails_without_all_tags(self):
        # Asking for particular tags does not acquire if no machine has all
        # tags.
        machine1 = factory.make_Node(
            status=NODE_STATUS.READY, with_boot_disk=True)
        machine1.tags = [
            factory.make_Tag(t) for t in ("fast", "stable", "cute")]
        machine2 = factory.make_Node(
            status=NODE_STATUS.READY, with_boot_disk=True)
        machine2.tags = [factory.make_Tag("cheap")]
        response = self.client.post(reverse('machines_handler'), {
            'op': 'acquire',
            'tags': 'fast, cheap',
        })
        self.assertResponseCode(http.client.CONFLICT, response)

    def test_POST_acquire_fails_with_unknown_tags(self):
        # Asking for a tag that does not exist gives a specific error.
        machine = factory.make_Node(
            status=NODE_STATUS.READY, with_boot_disk=True)
        machine.tags = [factory.make_Tag("fast")]
        response = self.client.post(reverse('machines_handler'), {
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

    def test_POST_acquire_allocates_machine_by_network(self):
        subnets = [
            factory.make_Subnet()
            for _ in range(5)
        ]
        machines = [
            factory.make_Node_with_Interface_on_Subnet(
                status=NODE_STATUS.READY, with_boot_disk=True, subnet=subnet)
            for subnet in subnets
        ]
        # We'll make it so that only the machine and subnet at this index will
        # match the request.
        pick = 2

        response = self.client.post(reverse('machines_handler'), {
            'op': 'acquire',
            'networks': [subnets[pick].name],
        })

        self.assertResponseCode(http.client.OK, response)
        response_json = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))
        self.assertEqual(
            machines[pick].system_id, response_json['system_id'])

    def test_POST_acquire_allocates_machine_by_not_network(self):
        subnets = [
            factory.make_Subnet()
            for _ in range(5)
        ]
        for subnet in subnets:
            factory.make_Node_with_Interface_on_Subnet(
                status=NODE_STATUS.READY, with_boot_disk=True, subnet=subnet)
        right_machine = factory.make_Node_with_Interface_on_Subnet(
            status=NODE_STATUS.READY, with_boot_disk=True)

        response = self.client.post(reverse('machines_handler'), {
            'op': 'acquire',
            'not_networks': [subnet.name for subnet in subnets],
        })

        self.assertResponseCode(http.client.OK, response)
        response_json = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))
        self.assertEqual(right_machine.system_id, response_json['system_id'])

    def test_POST_acquire_obeys_not_in_zone(self):
        # Zone we don't want to acquire from.
        not_in_zone = factory.make_Zone()
        machines = [
            factory.make_Node(
                status=NODE_STATUS.READY, zone=not_in_zone,
                with_boot_disk=True)
            for _ in range(5)
        ]
        # Pick a machine in the middle to avoid false negatives if acquire()
        # always tries the oldest, or the newest, machine first.
        eligible_machine = machines[2]
        eligible_machine.zone = factory.make_Zone()
        eligible_machine.save()

        response = self.client.post(
            reverse('machines_handler'),
            {
                'op': 'acquire',
                'not_in_zone': [not_in_zone.name],
            })
        self.assertEqual(http.client.OK, response.status_code)
        system_id = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))['system_id']
        self.assertEqual(eligible_machine.system_id, system_id)

    def test_POST_acquire_sets_a_token(self):
        # "acquire" should set the Token being used in the request on
        # the Machine that is allocated.
        available_status = NODE_STATUS.READY
        machine = factory.make_Node(
            status=available_status, owner=None, with_boot_disk=True)
        self.client.post(reverse('machines_handler'), {'op': 'acquire'})
        machine = Machine.objects.get(system_id=machine.system_id)
        oauth_key = self.client.token.key
        self.assertEqual(oauth_key, machine.token.key)

    def test_POST_accept_gets_machine_out_of_declared_state(self):
        # This will change when we add provisioning.  Until then,
        # acceptance gets a machine straight to Ready state.
        self.patch_autospec(Machine, 'start_transition_monitor')
        self.become_admin()
        target_state = NODE_STATUS.COMMISSIONING

        machine = factory.make_Node(status=NODE_STATUS.NEW)
        response = self.client.post(
            reverse('machines_handler'),
            {'op': 'accept', 'machines': [machine.system_id]})
        accepted_ids = [
            accepted_machine['system_id']
            for accepted_machine in json.loads(
                response.content.decode(settings.DEFAULT_CHARSET))]
        self.assertEqual(
            (http.client.OK, [machine.system_id]),
            (response.status_code, accepted_ids))
        self.assertEqual(target_state, reload_object(machine).status)

    def test_POST_quietly_accepts_empty_set(self):
        response = self.client.post(
            reverse('machines_handler'), {'op': 'accept'})
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
        machines = {
            status: factory.make_Node(status=status)
            for status in unacceptable_states}
        responses = {
            status: self.client.post(
                reverse('machines_handler'), {
                    'op': 'accept',
                    'machines': [machine.system_id],
                })
            for status, machine in machines.items()}
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
            # Each error names the machine it encountered a problem with.
            self.assertIn(
                machines[status].system_id.encode(
                    settings.DEFAULT_CHARSET), response.content)
            # Each error names the machine state that the request conflicted
            # with.
            self.assertIn(
                NODE_STATUS_CHOICES_DICT[status].encode(
                    settings.DEFAULT_CHARSET),
                response.content)

    def test_POST_accept_fails_if_machine_does_not_exist(self):
        self.become_admin()
        # Make sure there is a machine, it just isn't the one being accepted
        factory.make_Node()
        machine_id = factory.make_string()
        response = self.client.post(
            reverse('machines_handler'),
            {'op': 'accept', 'machines': [machine_id]})
        self.assertEqual(
            (http.client.BAD_REQUEST,
             ("Unknown machine(s): %s." % machine_id).encode(
                 settings.DEFAULT_CHARSET)),
            (response.status_code, response.content))

    def test_POST_accept_fails_for_device(self):
        self.become_admin()
        factory.make_Device()
        machine_id = factory.make_string()
        response = self.client.post(
            reverse('machines_handler'),
            {'op': 'accept', 'machines': [machine_id]})
        self.assertEqual(
            (http.client.BAD_REQUEST,
             ("Unknown machine(s): %s." % machine_id).encode(
                 settings.DEFAULT_CHARSET)),
            (response.status_code, response.content))

    def test_POST_accept_accepts_multiple_machines(self):
        # This will change when we add provisioning.  Until then,
        # acceptance gets a machine straight to Ready state.
        self.patch_autospec(Machine, 'start_transition_monitor')
        self.become_admin()
        target_state = NODE_STATUS.COMMISSIONING

        machines = [
            factory.make_Node(status=NODE_STATUS.NEW)
            for counter in range(2)]
        machine_ids = [machine.system_id for machine in machines]
        response = self.client.post(reverse('machines_handler'), {
            'op': 'accept',
            'machines': machine_ids,
        })
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(
            [target_state] * len(machines),
            [reload_object(machine).status for machine in machines])

    def test_POST_accept_returns_actually_accepted_machines(self):
        self.patch_autospec(Machine, 'start_transition_monitor')
        self.become_admin()
        acceptable_machines = [
            factory.make_Node(status=NODE_STATUS.NEW)
            for counter in range(2)
        ]
        accepted_machine = factory.make_Node(status=NODE_STATUS.READY)
        machines = acceptable_machines + [accepted_machine]
        response = self.client.post(reverse('machines_handler'), {
            'op': 'accept',
            'machines': [machine.system_id for machine in machines],
        })
        self.assertEqual(http.client.OK, response.status_code)
        accepted_ids = [
            machine['system_id']
            for machine in json.loads(
                response.content.decode(settings.DEFAULT_CHARSET))]
        self.assertItemsEqual(
            [machine.system_id
             for machine in acceptable_machines], accepted_ids)
        self.assertNotIn(accepted_machine.system_id, accepted_ids)

    def test_POST_quietly_releases_empty_set(self):
        response = self.client.post(
            reverse('machines_handler'), {'op': 'release'})
        self.assertEqual(
            (http.client.OK.value, "[]"),
            (response.status_code,
             response.content.decode(settings.DEFAULT_CHARSET)))

    def test_POST_release_ignores_devices(self):
        device_ids = {
            factory.make_Device().system_id
            for _ in range(3)
        }
        response = self.client.post(
            reverse('machines_handler'), {
                'op': 'release',
                'machines': device_ids
            })
        self.assertEqual(http.client.BAD_REQUEST, response.status_code)

    def test_POST_release_rejects_request_from_unauthorized_user(self):
        machine = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=factory.make_User())
        response = self.client.post(
            reverse('machines_handler'), {
                'op': 'release',
                'machines': [machine.system_id],
            })
        self.assertEqual(http.client.FORBIDDEN, response.status_code)
        self.assertEqual(NODE_STATUS.ALLOCATED, reload_object(machine).status)

    def test_POST_release_fails_if_machines_do_not_exist(self):
        # Make sure there is a machine, it just isn't among the ones to release
        factory.make_Node()
        machine_ids = {factory.make_string() for _ in range(5)}
        response = self.client.post(
            reverse('machines_handler'), {
                'op': 'release',
                'machines': machine_ids
            })
        # Awkward parsing, but the order may vary and it's not JSON
        s = response.content.decode(settings.DEFAULT_CHARSET)
        returned_ids = s[s.find(':') + 2:s.rfind('.')].split(', ')
        self.assertEqual(http.client.BAD_REQUEST, response.status_code)
        self.assertIn(
            "Unknown machine(s): ",
            response.content.decode(settings.DEFAULT_CHARSET))
        self.assertItemsEqual(machine_ids, returned_ids)

    def test_POST_release_forbidden_if_user_cannot_edit_machine(self):
        # Create a bunch of machines, owned by the logged in user
        machine_ids = {
            factory.make_Node(
                status=NODE_STATUS.ALLOCATED,
                owner=self.logged_in_user).system_id
            for _ in range(3)
        }
        # And one with no owner
        another_machine = factory.make_Node(status=NODE_STATUS.RESERVED)
        machine_ids.add(another_machine.system_id)
        response = self.client.post(
            reverse('machines_handler'), {
                'op': 'release',
                'machines': machine_ids
            })
        expected_response = (
            "You don't have the required permission to release the following "
            "machine(s): %s." % another_machine.system_id).encode(
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
        machines = [
            factory.make_Node(status=status, owner=owner)
            for status in unacceptable_states]
        response = self.client.post(
            reverse('machines_handler'), {
                'op': 'release',
                'machines': [machine.system_id for machine in machines],
            })
        # Awkward parsing again, because a string is returned, not JSON
        expected = [
            "%s ('%s')" % (machine.system_id, machine.display_status())
            for machine in machines
            if machine.status not in acceptable_states]
        s = response.content.decode(settings.DEFAULT_CHARSET)
        returned = s[s.rfind(':') + 2:s.rfind('.')].split(', ')
        self.assertEqual(http.client.CONFLICT, response.status_code)
        self.assertIn(
            "Machine(s) cannot be released in their current state:",
            response.content.decode(settings.DEFAULT_CHARSET))
        self.assertItemsEqual(expected, returned)

    def test_POST_release_returns_modified_machines(self):
        owner = self.logged_in_user
        acceptable_states = [NODE_STATUS.READY] + RELEASABLE_STATUSES
        machines = [
            factory.make_Node(status=status, owner=owner)
            for status in acceptable_states
        ]
        response = self.client.post(
            reverse('machines_handler'), {
                'op': 'release',
                'machines': [machine.system_id for machine in machines],
            })
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))
        self.assertEqual(http.client.OK, response.status_code)
        # The first machine is READY, so shouldn't be touched.
        self.assertItemsEqual(
            [machine.system_id for machine in machines[1:]],
            parsed_result)

    def test_POST_release_erases_disks_when_enabled(self):
        owner = self.logged_in_user
        machine = factory.make_Node(status=NODE_STATUS.ALLOCATED, owner=owner)
        Config.objects.set_config(
            'enable_disk_erasing_on_release', True)
        response = self.client.post(
            reverse('machines_handler'), {
                'op': 'release',
                'machines': [machine.system_id],
            })
        self.assertEqual(http.client.OK.value, response.status_code, response)
        machine = reload_object(machine)
        self.assertEqual(NODE_STATUS.DISK_ERASING, machine.status)

    def test_POST_set_zone_sets_zone_on_machines(self):
        self.become_admin()
        machine = factory.make_Node()
        zone = factory.make_Zone()
        response = self.client.post(
            reverse('machines_handler'),
            {
                'op': 'set_zone',
                'nodes': [machine.system_id],
                'zone': zone.name
            })
        self.assertEqual(http.client.OK, response.status_code)
        machine = reload_object(machine)
        self.assertEqual(zone, machine.zone)

    def test_POST_set_zone_does_not_affect_other_machines(self):
        self.become_admin()
        machine = factory.make_Node()
        original_zone = machine.zone
        response = self.client.post(
            reverse('machines_handler'),
            {
                'op': 'set_zone',
                'nodes': [factory.make_Node().system_id],
                'zone': factory.make_Zone().name
            })
        self.assertEqual(http.client.OK, response.status_code)
        machine = reload_object(machine)
        self.assertEqual(original_zone, machine.zone)

    def test_POST_set_zone_requires_admin(self):
        machine = factory.make_Node(owner=self.logged_in_user)
        original_zone = machine.zone
        response = self.client.post(
            reverse('machines_handler'),
            {
                'op': 'set_zone',
                'nodes': [machine.system_id],
                'zone': factory.make_Zone().name
            })
        self.assertEqual(http.client.FORBIDDEN, response.status_code)
        machine = reload_object(machine)
        self.assertEqual(original_zone, machine.zone)

    def test_GET_power_parameters_requires_admin(self):
        response = self.client.get(
            reverse('machines_handler'),
            {
                'op': 'power_parameters',
            })
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content)

    def test_GET_power_parameters_without_ids_does_not_filter(self):
        self.become_admin()
        machines = [
            factory.make_Node(
                power_parameters=factory.make_name("power_parameters"))
            for _ in range(0, 3)
        ]
        response = self.client.get(
            reverse('machines_handler'),
            {
                'op': 'power_parameters',
            })
        self.assertEqual(
            http.client.OK, response.status_code, response.content)
        parsed = json.loads(response.content.decode(settings.DEFAULT_CHARSET))
        expected = {
            machine.system_id: machine.power_parameters
            for machine in machines
        }
        self.assertEqual(expected, parsed)

    def test_GET_power_parameters_with_ids_filters(self):
        self.become_admin()
        machines = [
            factory.make_Node(
                power_parameters=factory.make_name("power_parameters"))
            for _ in range(0, 6)
        ]
        expected_machines = random.sample(machines, 3)
        response = self.client.get(
            reverse('machines_handler'),
            {
                'op': 'power_parameters',
                'id': [machine.system_id for machine in expected_machines],
            })
        self.assertEqual(
            http.client.OK, response.status_code, response.content)
        parsed = json.loads(response.content.decode(settings.DEFAULT_CHARSET))
        expected = {
            machine.system_id: machine.power_parameters
            for machine in expected_machines
        }
        self.assertEqual(expected, parsed)


class TestDeploymentStatus(APITestCase):
    """Tests for /api/1.0/machines/?op=deployment_status."""

    endpoint = reverse('machines_handler')

    def test_GET_returns_single_matching_machine(self):
        owned_machine = factory.make_Node(
            owner=self.logged_in_user, status=NODE_STATUS.DEPLOYED)
        response = self.client.get(
            self.endpoint,
            {'op': 'deployment_status', 'machines': [owned_machine.system_id]})
        self.assertEqual(
            http.client.OK, response.status_code, response.content)
        expected = {owned_machine.system_id: "Deployed"}
        self.assertEqual(
            expected, json.loads(
                response.content.decode(settings.DEFAULT_CHARSET)))

    def test_GET_returns_multiple_matching_machines(self):
        machines = []
        expected = dict()
        for _ in range(3):
            machine = factory.make_Node(
                owner=self.logged_in_user, status=NODE_STATUS.DEPLOYED)
            machines.append(machine)
            expected[machine.system_id] = "Deployed"
        ids = [n.system_id for n in machines]
        response = self.client.get(
            self.endpoint, {'op': 'deployment_status', 'machines': ids})
        self.assertEqual(
            http.client.OK, response.status_code, response.content)
        self.assertItemsEqual(
            expected, json.loads(
                response.content.decode(settings.DEFAULT_CHARSET)))

    def test_GET_rejects_unviewable_machines(self):
        owned_machine = factory.make_Node(owner=self.logged_in_user)
        unowned_machine = factory.make_Node(owner=factory.make_User())
        machine_ids = [owned_machine.system_id, unowned_machine.system_id]
        response = self.client.get(
            self.endpoint,
            {'op': 'deployment_status', 'machines': machine_ids})
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content)
        expected_response = (
            "You don't have the required permission to view the following "
            "machine(s): %s." % unowned_machine.system_id).encode(
            settings.DEFAULT_CHARSET)
        self.assertEqual(expected_response, response.content)

    def test_GET_rejects_invalid_machine_ids(self):
        response = self.client.get(
            self.endpoint,
            {'op': 'deployment_status', 'machines': ['foo', 'bar']})
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content)
        response_string = response.content.decode(settings.DEFAULT_CHARSET)
        # The order in which "foo" and "bar" appear is not guaranteed, but they
        # should be in the string, as well as the error message.
        self.assertIn("Unknown machine(s):", response_string)
        self.assertIn("foo", response_string)
        self.assertIn("bar", response_string)

    def test_GET_rejects_devices(self):
        owned_machine = factory.make_Device(owner=self.logged_in_user)
        response = self.client.get(
            self.endpoint,
            {'op': 'deployment_status', 'machines': [owned_machine.system_id]})
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content)
        self.assertIn(
            "Unknown machine(s)",
            response.content.decode(settings.DEFAULT_CHARSET))


class TestPowerState(APITransactionTestCase):

    def setUp(self):
        super(TestPowerState, self).setUp()
        self.useFixture(RegionEventLoopFixture("database-tasks", "rpc"))
        self.useFixture(RunningEventLoopFixture())

    def get_machine_uri(self, machine):
        """Get the API URI for a machine."""
        return reverse('machine_handler', args=[machine.system_id])

    def prepare_rpc(self, nodegroup, side_effect=None):
        self.rpc_fixture = self.useFixture(MockLiveRegionToClusterRPCFixture())
        protocol = self.rpc_fixture.makeCluster(
            nodegroup, cluster_module.PowerQuery)
        if side_effect is None:
            protocol.PowerQuery.side_effect = always_succeed_with({})
        else:
            protocol.PowerQuery.side_effect = side_effect

    def assertPowerState(self, machine, state):
        dbtasks = eventloop.services.getServiceNamed("database-tasks")
        dbtasks.syncTask().wait(
            timeout=5)  # Wait for all pending tasks to run.
        self.assertThat(reload_object(machine).power_state, Equals(state))

    def test__catches_no_connection_error(self):
        getClientFor = self.patch(nodes_module, 'getClientFor')
        getClientFor.side_effect = NoConnectionsAvailable()
        machine = factory.make_Node(
            power_state=POWER_STATE.ON, power_type=None)

        response = self.client.get(
            self.get_machine_uri(machine), {"op": "query_power_state"})

        self.assertResponseCode(http.client.SERVICE_UNAVAILABLE, response)
        self.assertIn(
            "Unable to connect to cluster controller",
            response.content.decode(settings.DEFAULT_CHARSET))
        # The machine's power state is unchanged.
        self.assertPowerState(machine, POWER_STATE.ON)

    def test__catches_timeout_error(self):
        mock_client = Mock()
        mock_client().wait.side_effect = crochet.TimeoutError("error")
        getClientFor = self.patch(nodes_module, 'getClientFor')
        getClientFor.return_value = mock_client
        machine = factory.make_Node(
            power_state=POWER_STATE.ON, power_type="ipmi")

        response = self.client.get(
            self.get_machine_uri(machine), {"op": "query_power_state"})

        self.assertResponseCode(http.client.SERVICE_UNAVAILABLE, response)
        self.assertIn(
            "Timed out waiting for power response",
            response.content.decode(settings.DEFAULT_CHARSET))
        # The machine's power state is unchanged.
        self.assertPowerState(machine, POWER_STATE.ON)

    def test__catches_unknown_power_type(self):
        self.patch(nodes_module, 'getClientFor')
        machine = factory.make_Node(power_state=POWER_STATE.OFF, power_type="")

        response = self.client.get(
            self.get_machine_uri(machine), {"op": "query_power_state"})

        self.assertResponseCode(http.client.SERVICE_UNAVAILABLE, response)
        self.assertIn(
            "Power state is not queryable",
            response.content.decode(settings.DEFAULT_CHARSET))
        # The machine's power state is now "unknown".
        self.assertPowerState(machine, POWER_STATE.UNKNOWN)

    def test__catches_poweraction_fail(self):
        machine = factory.make_Node(
            power_state=POWER_STATE.ON, power_type="ipmi")
        error_message = factory.make_name("error")
        self.prepare_rpc(
            machine.nodegroup, side_effect=PowerActionFail(error_message))

        response = self.client.get(
            self.get_machine_uri(machine), {"op": "query_power_state"})

        self.assertResponseCode(http.client.SERVICE_UNAVAILABLE, response)
        self.assertIn(
            error_message.encode(settings.DEFAULT_CHARSET), response.content)
        # The machine's power state is now "error".
        self.assertPowerState(machine, POWER_STATE.ERROR)

    def test__catches_operation_not_implemented(self):
        machine = factory.make_Node(
            power_state=POWER_STATE.ON, power_type="ipmi")
        error_message = factory.make_name("error")
        self.prepare_rpc(
            machine.nodegroup, side_effect=NotImplementedError(error_message))

        response = self.client.get(
            self.get_machine_uri(machine), {"op": "query_power_state"})

        self.assertResponseCode(http.client.SERVICE_UNAVAILABLE, response)
        self.assertIn(error_message.encode(
            settings.DEFAULT_CHARSET), response.content)
        # The machine's power state is now "unknown".
        self.assertPowerState(machine, POWER_STATE.UNKNOWN)

    def test__returns_actual_state(self):
        machine = factory.make_Node(power_type="ipmi")
        random_state = random.choice(["on", "off", "error"])
        self.prepare_rpc(
            machine.nodegroup,
            side_effect=always_succeed_with({"state": random_state}))

        response = self.client.get(
            self.get_machine_uri(machine), {"op": "query_power_state"})

        self.assertResponseCode(http.client.OK, response)
        response = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))
        self.assertEqual({"state": random_state}, response)
        # The machine's power state is now `random_state`.
        self.assertPowerState(machine, random_state)
