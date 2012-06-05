# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test maasserver models."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from datetime import (
    datetime,
    timedelta,
    )

from django.conf import settings
from django.core.exceptions import (
    PermissionDenied,
    ValidationError,
    )
from django.db import transaction
from maasserver.enum import (
    NODE_PERMISSION,
    NODE_STATUS,
    NODE_STATUS_CHOICES,
    NODE_STATUS_CHOICES_DICT,
    )
from maasserver.exceptions import NodeStateViolation
from maasserver.models import (
    Config,
    create_auth_token,
    get_auth_tokens,
    get_db_state,
    MACAddress,
    Node,
    NODE_TRANSITIONS,
    now,
    )
from maasserver.provisioning import get_provisioning_api_proxy
from maasserver.testing import reload_object
from maasserver.testing.factory import factory
from maasserver.testing.testcase import (
    TestCase,
    TestModelTestCase,
    )
from maasserver.tests.models import TimestampedModelTestModel
from maasserver.utils import map_enum
from maastesting.celery import CeleryFixture
from maastesting.djangotestcase import (
    TestModelTransactionalTestCase,
    TransactionTestCase,
    )
from metadataserver.models import (
    NodeCommissionResult,
    NodeUserData,
    )
from piston.models import (
    KEY_SIZE,
    SECRET_SIZE,
    )
from provisioningserver.enum import POWER_TYPE
from provisioningserver.power.poweraction import PowerAction
from testtools.matchers import FileContains


class UtilitiesTest(TestCase):

    def test_now_returns_datetime(self):
        self.assertIsInstance(now(), datetime)

    def test_now_returns_same_datetime_inside_transaction(self):
        date_now = now()
        self.assertEqual(date_now, now())


class UtilitiesTransactionalTest(TransactionTestCase):

    def test_now_returns_transaction_time(self):
        date_now = now()
        # Perform a write database operation.
        factory.make_node()
        transaction.commit()
        self.assertLessEqual(date_now, now())


class TimestampedModelTest(TestModelTestCase):
    """Testing for the class `TimestampedModel`."""

    app = 'maasserver.tests'

    def test_created_populated_when_object_saved(self):
        obj = TimestampedModelTestModel()
        obj.save()
        self.assertIsNotNone(obj.created)

    def test_updated_populated_when_object_saved(self):
        obj = TimestampedModelTestModel()
        obj.save()
        self.assertIsNotNone(obj.updated)

    def test_updated_and_created_are_the_same_after_first_save(self):
        obj = TimestampedModelTestModel()
        obj.save()
        self.assertEqual(obj.created, obj.updated)

    def test_created_not_modified_by_subsequent_calls_to_save(self):
        obj = TimestampedModelTestModel()
        obj.save()
        old_created = obj.created
        obj.save()
        self.assertEqual(old_created, obj.created)


class TimestampedModelTransactionalTest(TestModelTransactionalTestCase):

    app = 'maasserver.tests'

    def test_created_bracketed_by_before_and_after_time(self):
        before = now()
        obj = TimestampedModelTestModel()
        obj.save()
        transaction.commit()
        after = now()
        self.assertLessEqual(before, obj.created)
        self.assertGreaterEqual(after, obj.created)

    def test_updated_is_updated_when_object_saved(self):
        obj = TimestampedModelTestModel()
        obj.save()
        old_updated = obj.updated
        transaction.commit()
        obj.save()
        self.assertLessEqual(old_updated, obj.updated)


class NodeTest(TestCase):

    def test_system_id(self):
        """
        The generated system_id looks good.

        """
        node = factory.make_node()
        self.assertEqual(len(node.system_id), 41)
        self.assertTrue(node.system_id.startswith('node-'))

    def test_display_status_shows_default_status(self):
        node = factory.make_node()
        self.assertEqual(
            NODE_STATUS_CHOICES_DICT[node.status],
            node.display_status())

    def test_display_status_for_allocated_node_shows_owner(self):
        node = factory.make_node(
            owner=factory.make_user(), status=NODE_STATUS.ALLOCATED)
        self.assertEqual(
            "Allocated to %s" % node.owner.username,
            node.display_status())

    def test_add_node_with_token(self):
        user = factory.make_user()
        token = create_auth_token(user)
        node = factory.make_node(token=token)
        self.assertEqual(token, node.token)

    def test_add_mac_address(self):
        node = factory.make_node()
        node.add_mac_address('AA:BB:CC:DD:EE:FF')
        macs = MACAddress.objects.filter(
            node=node, mac_address='AA:BB:CC:DD:EE:FF').count()
        self.assertEqual(1, macs)

    def test_remove_mac_address(self):
        node = factory.make_node()
        node.add_mac_address('AA:BB:CC:DD:EE:FF')
        node.remove_mac_address('AA:BB:CC:DD:EE:FF')
        macs = MACAddress.objects.filter(
            node=node, mac_address='AA:BB:CC:DD:EE:FF').count()
        self.assertEqual(0, macs)

    def test_get_primary_mac_returns_mac_address(self):
        node = factory.make_node()
        mac = factory.getRandomMACAddress()
        node.add_mac_address(mac)
        self.assertEqual(mac, node.get_primary_mac().mac_address)

    def test_get_primary_mac_returns_None_if_node_has_no_mac(self):
        node = factory.make_node()
        self.assertIsNone(node.get_primary_mac())

    def test_get_primary_mac_returns_oldest_mac(self):
        node = factory.make_node()
        macs = [factory.getRandomMACAddress() for counter in range(3)]
        offset = timedelta(0)
        for mac in macs:
            mac_address = node.add_mac_address(mac)
            mac_address.created += offset
            mac_address.save()
            offset += timedelta(1)
        self.assertEqual(macs[0], node.get_primary_mac().mac_address)

    def test_delete_node_deletes_related_mac(self):
        node = factory.make_node()
        mac = node.add_mac_address('AA:BB:CC:DD:EE:FF')
        node.delete()
        self.assertRaises(
            MACAddress.DoesNotExist, MACAddress.objects.get, id=mac.id)

    def test_cannot_delete_allocated_node(self):
        node = factory.make_node(status=NODE_STATUS.ALLOCATED)
        self.assertRaises(NodeStateViolation, node.delete)

    def test_set_mac_based_hostname_default_enlistment_domain(self):
        # The enlistment domain defaults to `local`.
        node = factory.make_node()
        node.set_mac_based_hostname('AA:BB:CC:DD:EE:FF')
        hostname = 'node-aabbccddeeff.local'
        self.assertEqual(hostname, node.hostname)

    def test_set_mac_based_hostname_alt_enlistment_domain(self):
        # A non-default enlistment domain can be specified.
        Config.objects.set_config("enlistment_domain", "example.com")
        node = factory.make_node()
        node.set_mac_based_hostname('AA:BB:CC:DD:EE:FF')
        hostname = 'node-aabbccddeeff.example.com'
        self.assertEqual(hostname, node.hostname)

    def test_set_mac_based_hostname_cleaning_enlistment_domain(self):
        # Leading and trailing dots and whitespace are cleaned from the
        # configured enlistment domain before it's joined to the hostname.
        Config.objects.set_config("enlistment_domain", " .example.com. ")
        node = factory.make_node()
        node.set_mac_based_hostname('AA:BB:CC:DD:EE:FF')
        hostname = 'node-aabbccddeeff.example.com'
        self.assertEqual(hostname, node.hostname)

    def test_set_mac_based_hostname_no_enlistment_domain(self):
        # The enlistment domain can be set to the empty string and
        # set_mac_based_hostname sets a hostname with no domain.
        Config.objects.set_config("enlistment_domain", "")
        node = factory.make_node()
        node.set_mac_based_hostname('AA:BB:CC:DD:EE:FF')
        hostname = 'node-aabbccddeeff'
        self.assertEqual(hostname, node.hostname)

    def test_get_effective_power_type_defaults_to_config(self):
        power_types = list(map_enum(POWER_TYPE).values())
        power_types.remove(POWER_TYPE.DEFAULT)
        node = factory.make_node(power_type=POWER_TYPE.DEFAULT)
        effective_types = []
        for power_type in power_types:
            Config.objects.set_config('node_power_type', power_type)
            effective_types.append(node.get_effective_power_type())
        self.assertEqual(power_types, effective_types)

    def test_get_effective_power_type_reads_node_field(self):
        power_types = list(map_enum(POWER_TYPE).values())
        power_types.remove(POWER_TYPE.DEFAULT)
        nodes = [
            factory.make_node(power_type=power_type)
            for power_type in power_types]
        self.assertEqual(
            power_types, [node.get_effective_power_type() for node in nodes])

    def test_get_effective_power_type_rejects_default_as_config_value(self):
        node = factory.make_node(power_type=POWER_TYPE.DEFAULT)
        Config.objects.set_config('node_power_type', POWER_TYPE.DEFAULT)
        self.assertRaises(ValueError, node.get_effective_power_type)

    def test_power_parameters(self):
        node = factory.make_node(power_type=POWER_TYPE.DEFAULT)
        parameters = dict(user="tarquin", address="10.1.2.3")
        node.power_parameters = parameters
        node.save()
        node = reload_object(node)
        self.assertEqual(parameters, node.power_parameters)

    def test_power_parameters_default(self):
        node = factory.make_node(power_type=POWER_TYPE.DEFAULT)
        self.assertEqual("", node.power_parameters)

    def test_get_effective_power_parameters_returns_power_parameters(self):
        params = {'test_parameter': factory.getRandomString()}
        node = factory.make_node(power_parameters=params)
        self.assertEqual(
            params['test_parameter'],
            node.get_effective_power_parameters()['test_parameter'])

    def test_get_effective_power_parameters_adds_system_id(self):
        node = factory.make_node()
        self.assertEqual(
            node.system_id,
            node.get_effective_power_parameters()['system_id'])

    def test_get_effective_power_parameters_adds_mac_if_no_params_set(self):
        node = factory.make_node()
        mac = factory.getRandomMACAddress()
        node.add_mac_address(mac)
        self.assertEqual(mac, node.get_effective_power_parameters()['mac'])

    def test_get_effective_power_parameters_adds_no_mac_if_params_set(self):
        node = factory.make_node(power_parameters={'foo': 'bar'})
        mac = factory.getRandomMACAddress()
        node.add_mac_address(mac)
        self.assertNotIn('mac', node.get_effective_power_parameters())

    def test_get_effective_power_parameters_provides_usable_defaults(self):
        # For some power types at least, the defaults provided by
        # get_effective_power_parameters are enough to get a basic setup
        # working.
        configless_power_types = [
            POWER_TYPE.WAKE_ON_LAN,
            POWER_TYPE.VIRSH,
            ]
        # We don't actually want to fire off power events, but we'll go
        # through the motions right up to the point where we'd normally
        # run shell commands.
        self.patch(PowerAction, 'run_shell', lambda *args, **kwargs: ('', ''))
        user = factory.make_admin()
        nodes = [
            factory.make_node(power_type=power_type)
            for power_type in configless_power_types]
        for node in nodes:
            node.add_mac_address(factory.getRandomMACAddress())
        node_power_types = {
            node: node.get_effective_power_type()
            for node in nodes}
        started_nodes = Node.objects.start_nodes(
            list(node_power_types.keys()), user)
        successful_types = [node_power_types[node] for node in started_nodes]
        self.assertItemsEqual(configless_power_types, successful_types)

    def test_acquire(self):
        node = factory.make_node(status=NODE_STATUS.READY)
        user = factory.make_user()
        token = create_auth_token(user)
        node.acquire(user, token)
        self.assertEqual(user, node.owner)
        self.assertEqual(NODE_STATUS.ALLOCATED, node.status)

    def test_release(self):
        node = factory.make_node(
            status=NODE_STATUS.ALLOCATED, owner=factory.make_user())
        node.release()
        self.assertEqual((NODE_STATUS.READY, None), (node.status, node.owner))

    def test_accept_enlistment_gets_node_out_of_declared_state(self):
        # If called on a node in Declared state, accept_enlistment()
        # changes the node's status, and returns the node.
        target_state = NODE_STATUS.COMMISSIONING

        node = factory.make_node(status=NODE_STATUS.DECLARED)
        return_value = node.accept_enlistment(factory.make_user())
        self.assertEqual((node, target_state), (return_value, node.status))

    def test_accept_enlistment_does_nothing_if_already_accepted(self):
        # If a node has already been accepted, but not assigned a role
        # yet, calling accept_enlistment on it is meaningless but not an
        # error.  The method returns None in this case.
        accepted_states = [
            NODE_STATUS.COMMISSIONING,
            NODE_STATUS.READY,
            ]
        nodes = {
            status: factory.make_node(status=status)
            for status in accepted_states}

        return_values = {
            status: node.accept_enlistment(factory.make_user())
            for status, node in nodes.items()}

        self.assertEqual(
            {status: None for status in accepted_states}, return_values)
        self.assertEqual(
            {status: status for status in accepted_states},
            {status: node.status for status, node in nodes.items()})

    def test_accept_enlistment_rejects_bad_state_change(self):
        # If a node is neither Declared nor in one of the "accepted"
        # states where acceptance is a safe no-op, accept_enlistment
        # raises a node state violation and leaves the node's state
        # unchanged.
        all_states = map_enum(NODE_STATUS).values()
        acceptable_states = [
            NODE_STATUS.DECLARED,
            NODE_STATUS.COMMISSIONING,
            NODE_STATUS.READY,
            ]
        unacceptable_states = set(all_states) - set(acceptable_states)
        nodes = {
            status: factory.make_node(status=status)
            for status in unacceptable_states}

        exceptions = {status: False for status in unacceptable_states}
        for status, node in nodes.items():
            try:
                node.accept_enlistment(factory.make_user())
            except NodeStateViolation:
                exceptions[status] = True

        self.assertEqual(
            {status: True for status in unacceptable_states}, exceptions)
        self.assertEqual(
            {status: status for status in unacceptable_states},
            {status: node.status for status, node in nodes.items()})

    def test_start_commissioning_changes_status_and_starts_node(self):
        fixture = self.useFixture(CeleryFixture())
        user = factory.make_user()
        node = factory.make_node(
            status=NODE_STATUS.DECLARED, power_type=POWER_TYPE.WAKE_ON_LAN)
        factory.make_mac_address(node=node)
        node.start_commissioning(user)

        expected_attrs = {
            'status': NODE_STATUS.COMMISSIONING,
            'owner': user,
        }
        self.assertAttributes(node, expected_attrs)
        self.assertEqual(
            (1, 'provisioningserver.tasks.power_on'),
            (len(fixture.tasks), fixture.tasks[0]['task'].name))

    def test_start_commissioning_sets_user_data(self):
        node = factory.make_node(status=NODE_STATUS.DECLARED)
        node.start_commissioning(factory.make_admin())
        path = settings.COMMISSIONING_SCRIPT
        self.assertThat(
            path, FileContains(NodeUserData.objects.get_user_data(node)))

    def test_missing_commissioning_script(self):
        self.patch(
            settings, 'COMMISSIONING_SCRIPT',
            '/etc/' + factory.getRandomString(10))
        node = factory.make_node(status=NODE_STATUS.DECLARED)
        self.assertRaises(
            ValidationError,
            node.start_commissioning, factory.make_admin())

    def test_start_commissioning_clears_node_commissioning_results(self):
        node = factory.make_node(status=NODE_STATUS.DECLARED)
        NodeCommissionResult.objects.store_data(
            node, factory.getRandomString(), factory.getRandomString())
        node.start_commissioning(factory.make_admin())
        self.assertItemsEqual([], node.nodecommissionresult_set.all())

    def test_start_commissioning_ignores_other_commissioning_results(self):
        node = factory.make_node()
        filename = factory.getRandomString()
        text = factory.getRandomString()
        NodeCommissionResult.objects.store_data(node, filename, text)
        other_node = factory.make_node(status=NODE_STATUS.DECLARED)
        other_node.start_commissioning(factory.make_admin())
        self.assertEqual(
            text, NodeCommissionResult.objects.get_data(node, filename))

    def test_full_clean_checks_status_transition_and_raises_if_invalid(self):
        # RETIRED -> ALLOCATED is an invalid transition.
        node = factory.make_node(
            status=NODE_STATUS.RETIRED, owner=factory.make_user())
        node.status = NODE_STATUS.ALLOCATED
        self.assertRaisesRegexp(
            NodeStateViolation,
            "Invalid transition: Retired -> Allocated.",
            node.full_clean)

    def test_full_clean_passes_if_status_unchanged(self):
        status = factory.getRandomChoice(NODE_STATUS_CHOICES)
        node = factory.make_node(status=status)
        node.status = status
        node.full_clean()
        # The test is that this does not raise an error.
        pass

    def test_full_clean_passes_if_status_valid_transition(self):
        # NODE_STATUS.READY -> NODE_STATUS.ALLOCATED is a valid
        # transition.
        status = NODE_STATUS.READY
        node = factory.make_node(status=status)
        node.status = NODE_STATUS.ALLOCATED
        node.full_clean()
        # The test is that this does not raise an error.
        pass

    def test_save_raises_node_state_violation_on_bad_transition(self):
        # RETIRED -> ALLOCATED is an invalid transition.
        node = factory.make_node(
            status=NODE_STATUS.RETIRED, owner=factory.make_user())
        node.status = NODE_STATUS.ALLOCATED
        self.assertRaisesRegexp(
            NodeStateViolation,
            "Invalid transition: Retired -> Allocated.",
            node.save)


class NodeTransitionsTests(TestCase):
    """Test the structure of NODE_TRANSITIONS."""

    def test_NODE_TRANSITIONS_initial_states(self):
        allowed_states = set(NODE_STATUS_CHOICES_DICT.keys() + [None])

        self.assertTrue(set(NODE_TRANSITIONS.keys()) <= allowed_states)

    def test_NODE_TRANSITIONS_destination_state(self):
        all_destination_states = []
        for destination_states in NODE_TRANSITIONS.values():
            all_destination_states.extend(destination_states)
        allowed_states = set(NODE_STATUS_CHOICES_DICT.keys())

        self.assertTrue(set(all_destination_states) <= allowed_states)


class GetDbStateTest(TestCase):
    """Testing for the method `get_db_state`."""

    def test_get_db_state_returns_db_state(self):
        status = factory.getRandomChoice(NODE_STATUS_CHOICES)
        node = factory.make_node(status=status)
        another_status = factory.getRandomChoice(
            NODE_STATUS_CHOICES, but_not=[status])
        node.status = another_status
        self.assertEqual(status, get_db_state(node, 'status'))


class NodeManagerTest(TestCase):

    def make_node(self, user=None, **kwargs):
        """Create a node, allocated to `user` if given."""
        if user is None:
            status = NODE_STATUS.READY
        else:
            status = NODE_STATUS.ALLOCATED
        return factory.make_node(
            set_hostname=True, status=status, owner=user, **kwargs)

    def make_node_with_mac(self, user=None, **kwargs):
        node = self.make_node(user, **kwargs)
        mac = factory.make_mac_address(node=node)
        return node, mac

    def make_user_data(self):
        """Create a blob of arbitrary user-data."""
        return factory.getRandomString().encode('ascii')

    def test_filter_by_ids_filters_nodes_by_ids(self):
        nodes = [factory.make_node() for counter in range(5)]
        ids = [node.system_id for node in nodes]
        selection = slice(1, 3)
        self.assertItemsEqual(
            nodes[selection],
            Node.objects.filter_by_ids(Node.objects.all(), ids[selection]))

    def test_filter_by_ids_with_empty_list_returns_empty(self):
        factory.make_node()
        self.assertItemsEqual(
            [], Node.objects.filter_by_ids(Node.objects.all(), []))

    def test_filter_by_ids_without_ids_returns_full(self):
        node = factory.make_node()
        self.assertItemsEqual(
            [node], Node.objects.filter_by_ids(Node.objects.all(), None))

    def test_get_nodes_for_user_lists_visible_nodes(self):
        """get_nodes with perm=NODE_PERMISSION.VIEW lists the nodes a user
        has access to.

        When run for a regular user it returns unowned nodes, and nodes
        owned by that user.
        """
        user = factory.make_user()
        visible_nodes = [self.make_node(owner) for owner in [None, user]]
        self.make_node(factory.make_user())
        self.assertItemsEqual(
            visible_nodes, Node.objects.get_nodes(user, NODE_PERMISSION.VIEW))

    def test_get_nodes_admin_lists_all_nodes(self):
        admin = factory.make_admin()
        owners = [
            None,
            factory.make_user(),
            factory.make_admin(),
            admin,
            ]
        nodes = [self.make_node(owner) for owner in owners]
        self.assertItemsEqual(
            nodes, Node.objects.get_nodes(admin, NODE_PERMISSION.VIEW))

    def test_get_nodes_filters_by_id(self):
        user = factory.make_user()
        nodes = [self.make_node(user) for counter in range(5)]
        ids = [node.system_id for node in nodes]
        wanted_slice = slice(0, 3)
        self.assertItemsEqual(
            nodes[wanted_slice],
            Node.objects.get_nodes(
                user, NODE_PERMISSION.VIEW, ids=ids[wanted_slice]))

    def test_get_nodes_with_edit_perm_for_user_lists_owned_nodes(self):
        user = factory.make_user()
        visible_node = self.make_node(user)
        self.make_node(None)
        self.make_node(factory.make_user())
        self.assertItemsEqual(
            [visible_node],
            Node.objects.get_nodes(user, NODE_PERMISSION.EDIT))

    def test_get_nodes_with_edit_perm_admin_lists_all_nodes(self):
        admin = factory.make_admin()
        owners = [
            None,
            factory.make_user(),
            factory.make_admin(),
            admin,
            ]
        nodes = [self.make_node(owner) for owner in owners]
        self.assertItemsEqual(
            nodes, Node.objects.get_nodes(admin, NODE_PERMISSION.EDIT))

    def test_get_nodes_with_admin_perm_returns_empty_list_for_user(self):
        user = factory.make_user()
        [self.make_node(user) for counter in range(5)]
        self.assertItemsEqual(
            [],
            Node.objects.get_nodes(user, NODE_PERMISSION.ADMIN))

    def test_get_nodes_with_admin_perm_returns_all_nodes_for_admin(self):
        user = factory.make_user()
        nodes = [self.make_node(user) for counter in range(5)]
        self.assertItemsEqual(
            nodes,
            Node.objects.get_nodes(
                factory.make_admin(), NODE_PERMISSION.ADMIN))

    def test_get_visible_node_or_404_ok(self):
        """get_node_or_404 fetches nodes by system_id."""
        user = factory.make_user()
        node = self.make_node(user)
        self.assertEqual(
            node,
            Node.objects.get_node_or_404(
                node.system_id, user, NODE_PERMISSION.VIEW))

    def test_get_visible_node_or_404_raises_PermissionDenied(self):
        """get_node_or_404 raises PermissionDenied if the provided
        user has not the right permission on the returned node."""
        user_node = self.make_node(factory.make_user())
        self.assertRaises(
            PermissionDenied,
            Node.objects.get_node_or_404,
            user_node.system_id, factory.make_user(), NODE_PERMISSION.VIEW)

    def test_get_available_node_for_acquisition_finds_available_node(self):
        user = factory.make_user()
        node = self.make_node(None)
        self.assertEqual(
            node, Node.objects.get_available_node_for_acquisition(user))

    def test_get_available_node_for_acquisition_returns_none_if_empty(self):
        user = factory.make_user()
        self.assertEqual(
            None, Node.objects.get_available_node_for_acquisition(user))

    def test_get_available_node_for_acquisition_ignores_taken_nodes(self):
        user = factory.make_user()
        available_status = NODE_STATUS.READY
        unavailable_statuses = (
            set(NODE_STATUS_CHOICES_DICT) - set([available_status]))
        for status in unavailable_statuses:
            factory.make_node(status=status)
        self.assertEqual(
            None, Node.objects.get_available_node_for_acquisition(user))

    def test_get_available_node_for_acquisition_ignores_invisible_nodes(self):
        user = factory.make_user()
        node = self.make_node()
        node.owner = factory.make_user()
        node.save()
        self.assertEqual(
            None, Node.objects.get_available_node_for_acquisition(user))

    def test_get_available_node_combines_constraint_with_availability(self):
        user = factory.make_user()
        node = self.make_node(factory.make_user())
        self.assertEqual(
            None,
            Node.objects.get_available_node_for_acquisition(
                user, {'name': node.system_id}))

    def test_get_available_node_constrains_by_name(self):
        user = factory.make_user()
        nodes = [self.make_node() for counter in range(3)]
        self.assertEqual(
            nodes[1],
            Node.objects.get_available_node_for_acquisition(
                user, {'name': nodes[1].hostname}))

    def test_get_available_node_returns_None_if_name_is_unknown(self):
        user = factory.make_user()
        self.assertEqual(
            None,
            Node.objects.get_available_node_for_acquisition(
                user, {'name': factory.getRandomString()}))

    def test_stop_nodes_stops_nodes(self):
        user = factory.make_user()
        node = self.make_node(user)
        output = Node.objects.stop_nodes([node.system_id], user)

        self.assertItemsEqual([node], output)
        power_status = get_provisioning_api_proxy().power_status
        self.assertEqual('stop', power_status[node.system_id])

    def test_stop_nodes_ignores_uneditable_nodes(self):
        nodes = [
            self.make_node_with_mac(
                factory.make_user(), power_type=POWER_TYPE.WAKE_ON_LAN)
            for counter in range(3)]
        ids = [node.system_id for node, mac in nodes]
        stoppable_node = nodes[0][0]
        self.assertItemsEqual(
            [stoppable_node],
            Node.objects.stop_nodes(ids, stoppable_node.owner))

    def test_start_nodes_starts_nodes(self):
        fixture = self.useFixture(CeleryFixture())

        user = factory.make_user()
        node, mac = self.make_node_with_mac(
            user, power_type=POWER_TYPE.WAKE_ON_LAN)
        output = Node.objects.start_nodes([node.system_id], user)

        self.assertItemsEqual([node], output)
        self.assertEqual(
            (1, 'provisioningserver.tasks.power_on', mac.mac_address),
            (
                len(fixture.tasks),
                fixture.tasks[0]['task'].name,
                fixture.tasks[0]['kwargs']['mac'],
            ))

    def test_start_nodes_sets_commissioning_profile(self):
        # Starting up a node should always set a profile. Here we test
        # that a commissioning profile was set for nodes in the
        # commissioning status.
        self.useFixture(CeleryFixture())
        user = factory.make_user()
        node = factory.make_node(
            set_hostname=True, status=NODE_STATUS.COMMISSIONING, owner=user)
        factory.make_mac_address(node=node)
        output = Node.objects.start_nodes([node.system_id], user)
        self.assertItemsEqual([node], output)
        profile = get_provisioning_api_proxy().nodes[node.system_id]['profile']
        self.assertEqual('maas-precise-i386-commissioning', profile)

    def test_start_nodes_doesnt_set_commissioning_profile(self):
        # Starting up a node should always set a profile. Complement the
        # above test to show that a different profile can be set.
        self.useFixture(CeleryFixture())
        user = factory.make_user()
        node = self.make_node(user)
        factory.make_mac_address(node=node)
        output = Node.objects.start_nodes([node.system_id], user)

        self.assertItemsEqual([node], output)
        profile = get_provisioning_api_proxy().nodes[node.system_id]['profile']
        self.assertEqual('maas-precise-i386', profile)

    def test_start_nodes_uses_default_power_type_if_not_node_specific(self):
        # If the node has a power_type set to POWER_TYPE.DEFAULT,
        # NodeManager.start_node(this_node) should use the default
        # power_type.
        fixture = self.useFixture(CeleryFixture())

        Config.objects.set_config('node_power_type', POWER_TYPE.WAKE_ON_LAN)
        user = factory.make_user()
        node, unused = self.make_node_with_mac(
            user, power_type=POWER_TYPE.DEFAULT)
        output = Node.objects.start_nodes([node.system_id], user)

        self.assertItemsEqual([node], output)
        self.assertEqual(
            (1, 'provisioningserver.tasks.power_on'),
            (len(fixture.tasks), fixture.tasks[0]['task'].name))

    def test_start_nodes_wakeonlan_prefers_power_parameters(self):
        # If power_parameters is set we should prefer it to sifting
        # through related MAC addresses.
        fixture = self.useFixture(CeleryFixture())

        user = factory.make_user()
        preferred_mac = factory.getRandomMACAddress()
        node, mac = self.make_node_with_mac(
            user, power_type=POWER_TYPE.WAKE_ON_LAN,
            power_parameters=dict(mac=preferred_mac))
        output = Node.objects.start_nodes([node.system_id], user)

        self.assertItemsEqual([node], output)
        self.assertEqual(
            (1, 'provisioningserver.tasks.power_on', preferred_mac),
            (
                len(fixture.tasks),
                fixture.tasks[0]['task'].name,
                fixture.tasks[0]['kwargs']['mac'],
            ))

    def test_start_nodes_wakeonlan_ignores_invalid_parameters(self):
        # If node.power_params is set but doesn't have "mac" in it, then
        # the node shouldn't be started.
        fixture = self.useFixture(CeleryFixture())
        user = factory.make_user()
        node, mac = self.make_node_with_mac(
            user, power_type=POWER_TYPE.WAKE_ON_LAN,
            power_parameters=dict(jarjar="binks"))
        output = Node.objects.start_nodes([node.system_id], user)
        self.assertItemsEqual([], output)
        self.assertEqual([], fixture.tasks)

    def test_start_nodes_wakeonlan_ignores_empty_mac_parameter(self):
        fixture = self.useFixture(CeleryFixture())
        user = factory.make_user()
        node, mac = self.make_node_with_mac(
            user, power_type=POWER_TYPE.WAKE_ON_LAN,
            power_parameters=dict(mac=""))
        output = Node.objects.start_nodes([node.system_id], user)
        self.assertItemsEqual([], output)
        self.assertEqual([], fixture.tasks)

    def test_start_nodes_ignores_nodes_without_mac(self):
        user = factory.make_user()
        node = self.make_node(user)
        output = Node.objects.start_nodes([node.system_id], user)

        self.assertItemsEqual([], output)

    def test_start_nodes_ignores_uneditable_nodes(self):
        nodes = [
            self.make_node_with_mac(
                factory.make_user(), power_type=POWER_TYPE.WAKE_ON_LAN)[0]
                for counter in range(3)]
        ids = [node.system_id for node in nodes]
        startable_node = nodes[0]
        self.assertItemsEqual(
            [startable_node],
            Node.objects.start_nodes(ids, startable_node.owner))

    def test_start_nodes_stores_user_data(self):
        node = factory.make_node(owner=factory.make_user())
        user_data = self.make_user_data()
        Node.objects.start_nodes(
            [node.system_id], node.owner, user_data=user_data)
        self.assertEqual(user_data, NodeUserData.objects.get_user_data(node))

    def test_start_nodes_does_not_store_user_data_for_uneditable_nodes(self):
        node = factory.make_node(owner=factory.make_user())
        original_user_data = self.make_user_data()
        NodeUserData.objects.set_user_data(node, original_user_data)
        Node.objects.start_nodes(
            [node.system_id], factory.make_user(),
            user_data=self.make_user_data())
        self.assertEqual(
            original_user_data, NodeUserData.objects.get_user_data(node))

    def test_start_nodes_without_user_data_clears_existing_data(self):
        node = factory.make_node(owner=factory.make_user())
        user_data = self.make_user_data()
        NodeUserData.objects.set_user_data(node, user_data)
        Node.objects.start_nodes([node.system_id], node.owner, user_data=None)
        self.assertRaises(
            NodeUserData.DoesNotExist,
            NodeUserData.objects.get_user_data, node)

    def test_start_nodes_with_user_data_overwrites_existing_data(self):
        node = factory.make_node(owner=factory.make_user())
        NodeUserData.objects.set_user_data(node, self.make_user_data())
        user_data = self.make_user_data()
        Node.objects.start_nodes(
            [node.system_id], node.owner, user_data=user_data)
        self.assertEqual(user_data, NodeUserData.objects.get_user_data(node))


class MACAddressTest(TestCase):

    def make_MAC(self, address):
        """Create a MAC address."""
        node = factory.make_node()
        return MACAddress(mac_address=address, node=node)

    def test_stores_to_database(self):
        mac = self.make_MAC('00:11:22:33:44:55')
        mac.save()
        self.assertEqual([mac], list(MACAddress.objects.all()))

    def test_invalid_address_raises_validation_error(self):
        mac = self.make_MAC('aa:bb:ccxdd:ee:ff')
        self.assertRaises(ValidationError, mac.full_clean)


class AuthTokensTest(TestCase):
    """Test creation and retrieval of auth tokens."""

    def assertTokenValid(self, token):
        self.assertIsInstance(token.key, basestring)
        self.assertEqual(KEY_SIZE, len(token.key))
        self.assertIsInstance(token.secret, basestring)
        self.assertEqual(SECRET_SIZE, len(token.secret))

    def assertConsumerValid(self, consumer):
        self.assertIsInstance(consumer.key, basestring)
        self.assertEqual(KEY_SIZE, len(consumer.key))
        self.assertEqual('', consumer.secret)

    def test_create_auth_token(self):
        user = factory.make_user()
        token = create_auth_token(user)
        self.assertEqual(user, token.user)
        self.assertEqual(user, token.consumer.user)
        self.assertTrue(token.is_approved)
        self.assertConsumerValid(token.consumer)
        self.assertTokenValid(token)

    def test_get_auth_tokens_finds_tokens_for_user(self):
        user = factory.make_user()
        token = create_auth_token(user)
        self.assertIn(token, get_auth_tokens(user))

    def test_get_auth_tokens_ignores_other_users(self):
        user, other_user = factory.make_user(), factory.make_user()
        unrelated_token = create_auth_token(other_user)
        self.assertNotIn(unrelated_token, get_auth_tokens(user))

    def test_get_auth_tokens_ignores_unapproved_tokens(self):
        user = factory.make_user()
        token = create_auth_token(user)
        token.is_approved = False
        token.save()
        self.assertNotIn(token, get_auth_tokens(user))
