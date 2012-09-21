# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test forms."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

import json

from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import (
    PermissionDenied,
    ValidationError,
    )
from django.http import QueryDict
from maasserver.enum import (
    ARCHITECTURE,
    ARCHITECTURE_CHOICES,
    NODE_AFTER_COMMISSIONING_ACTION_CHOICES,
    NODE_STATUS,
    NODEGROUP_STATUS,
    NODEGROUPINTERFACE_MANAGEMENT,
    )
from maasserver.forms import (
    AdminNodeForm,
    AdminNodeWithMACAddressesForm,
    ConfigForm,
    EditUserForm,
    get_action_form,
    get_node_create_form,
    get_node_edit_form,
    HostnameFormField,
    initialize_node_group,
    INTERFACES_VALIDATION_ERROR_MESSAGE,
    MACAddressForm,
    NewUserCreationForm,
    NodeActionForm,
    NodeForm,
    NodeGroupInterfaceForm,
    NodeGroupWithInterfacesForm,
    NodeWithMACAddressesForm,
    ProfileForm,
    remove_None_values,
    validate_hostname,
    )
from maasserver.models import (
    Config,
    MACAddress,
    Node,
    NodeGroup,
    )
from maasserver.models.config import DEFAULT_CONFIG
from maasserver.node_action import (
    AcceptAndCommission,
    Delete,
    )
from maasserver.testing import reload_object
from maasserver.testing.factory import factory
from maasserver.testing.testcase import TestCase
from provisioningserver.enum import POWER_TYPE_CHOICES
from testtools.matchers import MatchesStructure
from testtools.testcase import ExpectedException


class TestHelpers(TestCase):

    def test_initialize_node_group_leaves_nodegroup_reference_intact(self):
        preselected_nodegroup = factory.make_node_group()
        node = factory.make_node(nodegroup=preselected_nodegroup)
        initialize_node_group(node)
        self.assertEqual(preselected_nodegroup, node.nodegroup)

    def test_initialize_node_group_initializes_nodegroup_to_form_value(self):
        node = Node(
            NODE_STATUS.DECLARED,
            architecture=factory.getRandomEnum(ARCHITECTURE))
        nodegroup = factory.make_node_group()
        initialize_node_group(node, nodegroup)
        self.assertEqual(nodegroup, node.nodegroup)

    def test_initialize_node_group_defaults_to_master(self):
        node = Node(
            NODE_STATUS.DECLARED,
            architecture=factory.getRandomEnum(ARCHITECTURE))
        initialize_node_group(node)
        self.assertEqual(NodeGroup.objects.ensure_master(), node.nodegroup)


class NodeWithMACAddressesFormTest(TestCase):

    def get_QueryDict(self, params):
        query_dict = QueryDict('', mutable=True)
        for k, v in params.items():
            if isinstance(v, list):
                query_dict.setlist(k, v)
            else:
                query_dict[k] = v
        return query_dict

    def make_params(self, mac_addresses=None, architecture=None,
                    nodegroup=None):
        if mac_addresses is None:
            mac_addresses = [factory.getRandomMACAddress()]
        if architecture is None:
            architecture = factory.getRandomEnum(ARCHITECTURE)
        params = {
            'mac_addresses': mac_addresses,
            'architecture': architecture,
        }
        if nodegroup is not None:
            params['nodegroup'] = nodegroup
        return self.get_QueryDict(params)

    def test_NodeWithMACAddressesForm_valid(self):
        architecture = factory.getRandomEnum(ARCHITECTURE)
        form = NodeWithMACAddressesForm(
            self.make_params(
                mac_addresses=['aa:bb:cc:dd:ee:ff', '9a:bb:c3:33:e5:7f'],
                architecture=architecture))

        self.assertTrue(form.is_valid())
        self.assertEqual(
            ['aa:bb:cc:dd:ee:ff', '9a:bb:c3:33:e5:7f'],
            form.cleaned_data['mac_addresses'])
        self.assertEqual(architecture, form.cleaned_data['architecture'])

    def test_NodeWithMACAddressesForm_simple_invalid(self):
        # If the form only has one (invalid) MAC address field to validate,
        # the error message in form.errors['mac_addresses'] is the
        # message from the field's validation error.
        form = NodeWithMACAddressesForm(
            self.make_params(mac_addresses=['invalid']))

        self.assertFalse(form.is_valid())
        self.assertEqual(['mac_addresses'], list(form.errors))
        self.assertEqual(
            ['Enter a valid MAC address (e.g. AA:BB:CC:DD:EE:FF).'],
            form.errors['mac_addresses'])

    def test_NodeWithMACAddressesForm_multiple_invalid(self):
        # If the form has multiple MAC address fields to validate,
        # if one or more fields are invalid, a single error message is
        # present in form.errors['mac_addresses'] after validation.
        form = NodeWithMACAddressesForm(
            self.make_params(mac_addresses=['invalid_1', 'invalid_2']))

        self.assertFalse(form.is_valid())
        self.assertEqual(['mac_addresses'], list(form.errors))
        self.assertEqual(
            ['One or more MAC addresses is invalid.'],
            form.errors['mac_addresses'])

    def test_NodeWithMACAddressesForm_empty(self):
        # Empty values in the list of MAC addresses are simply ignored.
        form = NodeWithMACAddressesForm(
            self.make_params(
                mac_addresses=[factory.getRandomMACAddress(), '']))

        self.assertTrue(form.is_valid())

    def test_NodeWithMACAddressesForm_save(self):
        macs = ['aa:bb:cc:dd:ee:ff', '9a:bb:c3:33:e5:7f']
        form = NodeWithMACAddressesForm(self.make_params(mac_addresses=macs))
        node = form.save()

        self.assertIsNotNone(node.id)  # The node is persisted.
        self.assertSequenceEqual(
            macs,
            [mac.mac_address for mac in node.macaddress_set.all()])

    def test_includes_nodegroup_field_for_new_node(self):
        self.assertIn(
            'nodegroup',
            NodeWithMACAddressesForm(self.make_params()).fields)

    def test_does_not_include_nodegroup_field_for_existing_node(self):
        params = self.make_params()
        node = factory.make_node()
        self.assertNotIn(
            'nodegroup',
            NodeWithMACAddressesForm(params, instance=node).fields)

    def test_sets_nodegroup_to_master_by_default(self):
        self.assertEqual(
            NodeGroup.objects.ensure_master(),
            NodeWithMACAddressesForm(self.make_params()).save().nodegroup)

    def test_sets_nodegroup_on_new_node_if_requested(self):
        nodegroup = factory.make_node_group(
            ip_range_low='192.168.14.2', ip_range_high='192.168.14.254',
            ip='192.168.14.1', subnet_mask='255.255.255.0')
        form = NodeWithMACAddressesForm(
            self.make_params(nodegroup=nodegroup.get_managed_interface().ip))
        self.assertEqual(nodegroup, form.save().nodegroup)

    def test_leaves_nodegroup_alone_if_unset_on_existing_node(self):
        # Selecting a node group for a node is only supported on new
        # nodes.  You can't change it later.
        original_nodegroup = factory.make_node_group()
        node = factory.make_node(nodegroup=original_nodegroup)
        factory.make_node_group(
            ip_range_low='10.0.0.1', ip_range_high='10.0.0.2',
            ip='10.0.0.1', subnet_mask='255.0.0.0')
        form = NodeWithMACAddressesForm(
            self.make_params(nodegroup='10.0.0.1'), instance=node)
        form.save()
        self.assertEqual(original_nodegroup, reload_object(node).nodegroup)


class TestOptionForm(ConfigForm):
    field1 = forms.CharField(label="Field 1", max_length=10)
    field2 = forms.BooleanField(label="Field 2", required=False)


class ConfigFormTest(TestCase):

    def test_form_valid_saves_into_db(self):
        value = factory.getRandomString(10)
        form = TestOptionForm({'field1': value, 'field2': False})
        result = form.save()

        self.assertTrue(result)
        self.assertEqual(value, Config.objects.get_config('field1'))
        self.assertFalse(Config.objects.get_config('field2'))

    def test_form_invalid_does_not_save_into_db(self):
        value_too_long = factory.getRandomString(20)
        form = TestOptionForm({'field1': value_too_long, 'field2': False})
        result = form.save()

        self.assertFalse(result)
        self.assertIn('field1', form._errors)
        self.assertIsNone(Config.objects.get_config('field1'))
        self.assertIsNone(Config.objects.get_config('field2'))

    def test_form_loads_initial_values(self):
        value = factory.getRandomString()
        Config.objects.set_config('field1', value)
        form = TestOptionForm()

        self.assertItemsEqual(['field1'], form.initial)
        self.assertEqual(value, form.initial['field1'])

    def test_form_loads_initial_values_from_default_value(self):
        value = factory.getRandomString()
        DEFAULT_CONFIG['field1'] = value
        form = TestOptionForm()

        self.assertItemsEqual(['field1'], form.initial)
        self.assertEqual(value, form.initial['field1'])


class FormWithHostname(forms.Form):
    hostname = HostnameFormField()


class NodeEditForms(TestCase):

    def test_NodeForm_contains_limited_set_of_fields(self):
        form = NodeForm()

        self.assertEqual(
            [
                'hostname',
                'after_commissioning_action',
                'architecture',
                'distro_series',
                'nodegroup',
            ], list(form.fields))

    def test_NodeForm_changes_node(self):
        node = factory.make_node()
        hostname = factory.getRandomString()
        after_commissioning_action = factory.getRandomChoice(
            NODE_AFTER_COMMISSIONING_ACTION_CHOICES)

        form = NodeForm(
            data={
                'hostname': hostname,
                'after_commissioning_action': after_commissioning_action,
                'architecture': factory.getRandomChoice(ARCHITECTURE_CHOICES),
                },
            instance=node)
        form.save()

        self.assertEqual(hostname, node.hostname)
        self.assertEqual(
            after_commissioning_action, node.after_commissioning_action)

    def test_AdminNodeForm_contains_limited_set_of_fields(self):
        node = factory.make_node()
        form = AdminNodeForm(instance=node)

        self.assertEqual(
            [
                'hostname',
                'after_commissioning_action',
                'architecture',
                'distro_series',
                'power_type',
                'power_parameters',
            ],
            list(form.fields))

    def test_AdminNodeForm_changes_node(self):
        node = factory.make_node()
        hostname = factory.getRandomString()
        after_commissioning_action = factory.getRandomChoice(
            NODE_AFTER_COMMISSIONING_ACTION_CHOICES)
        power_type = factory.getRandomChoice(POWER_TYPE_CHOICES)
        form = AdminNodeForm(
            data={
                'hostname': hostname,
                'after_commissioning_action': after_commissioning_action,
                'power_type': power_type,
                'architecture': factory.getRandomChoice(ARCHITECTURE_CHOICES),
                },
            instance=node)
        form.save()

        self.assertEqual(hostname, node.hostname)
        self.assertEqual(
            after_commissioning_action, node.after_commissioning_action)
        self.assertEqual(power_type, node.power_type)

    def test_remove_None_values_removes_None_values_in_dict(self):
        random_input = factory.getRandomString()
        self.assertEqual(
            {random_input: random_input},
            remove_None_values({
                random_input: random_input,
                factory.getRandomString(): None
                }))

    def test_remove_None_values_leaves_empty_dict_untouched(self):
        self.assertEqual({}, remove_None_values({}))

    def test_AdminNodeForm_changes_node_with_skip_check(self):
        node = factory.make_node()
        hostname = factory.getRandomString()
        after_commissioning_action = factory.getRandomChoice(
            NODE_AFTER_COMMISSIONING_ACTION_CHOICES)
        power_type = factory.getRandomChoice(POWER_TYPE_CHOICES)
        power_parameters_field = factory.getRandomString()
        form = AdminNodeForm(
            data={
                'hostname': hostname,
                'after_commissioning_action': after_commissioning_action,
                'architecture': factory.getRandomChoice(ARCHITECTURE_CHOICES),
                'power_type': power_type,
                'power_parameters_field': power_parameters_field,
                'power_parameters_skip_check': True,
                },
            instance=node)
        form.save()

        self.assertEqual(
            (hostname, after_commissioning_action, power_type,
                {'field': power_parameters_field}),
            (node.hostname, node.after_commissioning_action, node.power_type,
                node.power_parameters))

    def test_AdminForm_does_not_permit_nodegroup_change(self):
        # We had to make Node.nodegroup editable to get Django to
        # validate it as non-blankable, but that doesn't mean that we
        # actually want to allow people to edit it through API or UI.
        old_nodegroup = factory.make_node_group()
        node = factory.make_node(nodegroup=old_nodegroup)
        new_nodegroup = factory.make_node_group()
        form = AdminNodeForm(data={'nodegroup': new_nodegroup}, instance=node)
        self.assertRaises(ValueError, form.save)

    def test_get_node_edit_form_returns_NodeForm_if_non_admin(self):
        user = factory.make_user()
        self.assertEqual(NodeForm, get_node_edit_form(user))

    def test_get_node_edit_form_returns_APIAdminNodeEdit_if_admin(self):
        admin = factory.make_admin()
        self.assertEqual(AdminNodeForm, get_node_edit_form(admin))

    def test_get_node_create_form_if_non_admin(self):
        user = factory.make_user()
        self.assertEqual(
            NodeWithMACAddressesForm, get_node_create_form(user))

    def test_get_node_create_form_if_admin(self):
        admin = factory.make_admin()
        self.assertEqual(
            AdminNodeWithMACAddressesForm, get_node_create_form(admin))


class TestNodeActionForm(TestCase):

    def test_get_action_form_creates_form_class_with_attributes(self):
        user = factory.make_admin()
        form_class = get_action_form(user)

        self.assertEqual(user, form_class.user)

    def test_get_action_form_creates_form_class(self):
        user = factory.make_admin()
        node = factory.make_node(status=NODE_STATUS.DECLARED)
        form = get_action_form(user)(node)

        self.assertIsInstance(form, NodeActionForm)
        self.assertEqual(node, form.node)

    def test_get_action_form_for_admin(self):
        admin = factory.make_admin()
        node = factory.make_node(status=NODE_STATUS.DECLARED)
        form = get_action_form(admin)(node)

        self.assertItemsEqual(
            [AcceptAndCommission.display, Delete.display],
            form.actions)

    def test_get_action_form_for_user(self):
        user = factory.make_user()
        node = factory.make_node(status=NODE_STATUS.DECLARED)
        form = get_action_form(user)(node)

        self.assertIsInstance(form, NodeActionForm)
        self.assertEqual(node, form.node)
        self.assertItemsEqual({}, form.actions)

    def test_save_performs_requested_action(self):
        admin = factory.make_admin()
        node = factory.make_node(status=NODE_STATUS.DECLARED)
        form = get_action_form(admin)(
            node, {NodeActionForm.input_name: AcceptAndCommission.display})
        form.save()
        self.assertEqual(NODE_STATUS.COMMISSIONING, node.status)

    def test_save_refuses_disallowed_action(self):
        user = factory.make_user()
        node = factory.make_node(status=NODE_STATUS.DECLARED)
        form = get_action_form(user)(
            node, {NodeActionForm.input_name: AcceptAndCommission.display})
        self.assertRaises(PermissionDenied, form.save)

    def test_save_refuses_unknown_action(self):
        user = factory.make_user()
        node = factory.make_node(status=NODE_STATUS.DECLARED)
        form = get_action_form(user)(
            node, {NodeActionForm.input_name: factory.getRandomString()})
        self.assertRaises(PermissionDenied, form.save)

    def test_save_double_checks_for_inhibitions(self):
        admin = factory.make_admin()
        node = factory.make_node(
            status=NODE_STATUS.ALLOCATED, owner=factory.make_user())
        form = get_action_form(admin)(
            node, {NodeActionForm.input_name: Delete.display})
        with ExpectedException(PermissionDenied, "You cannot delete.*"):
            form.save()


class TestHostnameFormField(TestCase):

    def test_validate_hostname_validates_valid_hostnames(self):
        self.assertIsNone(validate_hostname('host.example.com'))
        self.assertIsNone(validate_hostname('host.my-example.com'))
        self.assertIsNone(validate_hostname('my-example.com'))
        #  No ValidationError.

    def test_validate_hostname_does_not_validate_invalid_hostnames(self):
        self.assertRaises(ValidationError, validate_hostname, 'invalid-host')

    def test_validate_hostname_does_not_validate_too_long_hostnames(self):
        self.assertRaises(ValidationError, validate_hostname, 'toolong' * 100)

    def test_hostname_field_validation_cleaned_data_if_hostname_valid(self):
        form = FormWithHostname({'hostname': 'host.example.com'})

        self.assertTrue(form.is_valid())
        self.assertEqual('host.example.com', form.cleaned_data['hostname'])

    def test_hostname_field_validation_error_if_invalid_hostname(self):
        form = FormWithHostname({'hostname': 'invalid-host'})

        self.assertFalse(form.is_valid())
        self.assertItemsEqual(['hostname'], list(form.errors))
        self.assertEqual(
            ["Enter a valid hostname (e.g. host.example.com)."],
            form.errors['hostname'])


class TestUniqueEmailForms(TestCase):

    def assertFormFailsValidationBecauseEmailNotUnique(self, form):
        self.assertFalse(form.is_valid())
        self.assertIn('email', form._errors)
        self.assertEqual(
            ["User with this E-mail address already exists."],
            form._errors['email'])

    def test_ProfileForm_fails_validation_if_email_taken(self):
        another_email = '%s@example.com' % factory.getRandomString()
        factory.make_user(email=another_email)
        email = '%s@example.com' % factory.getRandomString()
        user = factory.make_user(email=email)
        form = ProfileForm(instance=user, data={'email': another_email})
        self.assertFormFailsValidationBecauseEmailNotUnique(form)

    def test_ProfileForm_validates_if_email_unchanged(self):
        email = '%s@example.com' % factory.getRandomString()
        user = factory.make_user(email=email)
        form = ProfileForm(instance=user, data={'email': email})
        self.assertTrue(form.is_valid())

    def test_NewUserCreationForm_fails_validation_if_email_taken(self):
        email = '%s@example.com' % factory.getRandomString()
        username = factory.getRandomString()
        password = factory.getRandomString()
        factory.make_user(email=email)
        form = NewUserCreationForm(
            {
                'email': email,
                'username': username,
                'password1': password,
                'password2': password,
            })
        self.assertFormFailsValidationBecauseEmailNotUnique(form)

    def test_EditUserForm_fails_validation_if_email_taken(self):
        another_email = '%s@example.com' % factory.getRandomString()
        factory.make_user(email=another_email)
        email = '%s@example.com' % factory.getRandomString()
        user = factory.make_user(email=email)
        form = EditUserForm(instance=user, data={'email': another_email})
        self.assertFormFailsValidationBecauseEmailNotUnique(form)

    def test_EditUserForm_validates_if_email_unchanged(self):
        email = '%s@example.com' % factory.getRandomString()
        user = factory.make_user(email=email)
        form = EditUserForm(
            instance=user,
            data={
                'email': email,
                'username': factory.getRandomString(),
            })
        self.assertTrue(form.is_valid())


class TestNewUserCreationForm(TestCase):

    def test_saves_to_db_by_default(self):
        password = factory.make_name('password')
        params = {
            'email': '%s@example.com' % factory.getRandomString(),
            'username': factory.make_name('user'),
            'password1': password,
            'password2': password,
        }
        form = NewUserCreationForm(params)
        form.save()
        self.assertIsNotNone(User.objects.get(username=params['username']))

    def test_does_not_save_to_db_if_commit_is_False(self):
        password = factory.make_name('password')
        params = {
            'email': '%s@example.com' % factory.getRandomString(),
            'username': factory.make_name('user'),
            'password1': password,
            'password2': password,
        }
        form = NewUserCreationForm(params)
        form.save(commit=False)
        self.assertItemsEqual(
            [], User.objects.filter(username=params['username']))

    def test_fields_order(self):
        form = NewUserCreationForm()

        self.assertEqual(
            ['username', 'last_name', 'email', 'password1', 'password2',
                'is_superuser'],
            list(form.fields))


class TestMACAddressForm(TestCase):

    def test_MACAddressForm_creates_mac_address(self):
        node = factory.make_node()
        mac = factory.getRandomMACAddress()
        form = MACAddressForm(node=node, data={'mac_address': mac})
        form.save()
        self.assertTrue(
            MACAddress.objects.filter(node=node, mac_address=mac).exists())

    def test_saves_to_db_by_default(self):
        node = factory.make_node()
        mac = factory.getRandomMACAddress()
        form = MACAddressForm(node=node, data={'mac_address': mac})
        form.save()
        self.assertEqual(
            mac, MACAddress.objects.get(mac_address=mac).mac_address)

    def test_does_not_save_to_db_if_commit_is_False(self):
        node = factory.make_node()
        mac = factory.getRandomMACAddress()
        form = MACAddressForm(node=node, data={'mac_address': mac})
        form.save(commit=False)
        self.assertItemsEqual([], MACAddress.objects.filter(mac_address=mac))

    def test_MACAddressForm_displays_error_message_if_mac_already_used(self):
        mac = factory.getRandomMACAddress()
        node = factory.make_mac_address(address=mac)
        node = factory.make_node()
        form = MACAddressForm(node=node, data={'mac_address': mac})
        self.assertFalse(form.is_valid())
        self.assertEquals(
            {'mac_address': ['This MAC address is already registered.']},
            form._errors)
        self.assertFalse(
            MACAddress.objects.filter(node=node, mac_address=mac).exists())


def make_interface_settings():
    """Create a dict of arbitrary interface configuration parameters."""
    return {
        'ip': factory.getRandomIPAddress(),
        'interface': factory.make_name('interface'),
        'subnet_mask': factory.getRandomIPAddress(),
        'broadcast_ip': factory.getRandomIPAddress(),
        'router_ip': factory.getRandomIPAddress(),
        'ip_range_low': factory.getRandomIPAddress(),
        'ip_range_high': factory.getRandomIPAddress(),
        'management': factory.getRandomEnum(NODEGROUPINTERFACE_MANAGEMENT),
    }


class TestNodeGroupInterfaceForm(TestCase):

    def test_NodeGroupInterfaceForm_save_sets_nodegroup(self):
        nodegroup = factory.make_node_group(
            management=NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED)
        form = NodeGroupInterfaceForm(data=make_interface_settings())
        self.assertTrue(form.is_valid(), form._errors)
        interface = form.save(nodegroup=nodegroup)
        self.assertEqual(nodegroup, interface.nodegroup)

    def test_NodeGroupInterfaceForm_validates_parameters(self):
        form = NodeGroupInterfaceForm(data={'ip': factory.getRandomString()})
        self.assertFalse(form.is_valid())
        self.assertEquals(
            {'ip': ['Enter a valid IPv4 address.']}, form._errors)


class TestNodeGroupWithInterfacesForm(TestCase):

    def test_NodeGroupWithInterfacesForm_creates_pending_nodegroup(self):
        name = factory.make_name('name')
        uuid = factory.getRandomUUID()
        form = NodeGroupWithInterfacesForm(
            data={'name': name, 'uuid': uuid})
        self.assertTrue(form.is_valid(), form._errors)
        nodegroup = form.save()
        self.assertEqual(
            (uuid, name, NODEGROUP_STATUS.PENDING, 0),
            (
                nodegroup.uuid,
                nodegroup.name,
                nodegroup.status,
                nodegroup.nodegroupinterface_set.count(),
            ))

    def test_NodeGroupWithInterfacesForm_validates_parameters(self):
        name = factory.make_name('name')
        too_long_uuid = 'test' * 30
        form = NodeGroupWithInterfacesForm(
            data={'name': name, 'uuid': too_long_uuid})
        self.assertFalse(form.is_valid())
        self.assertEquals(
            {'uuid':
                ['Ensure this value has at most 36 characters (it has 120).']},
            form._errors)

    def test_NodeGroupWithInterfacesForm_rejects_invalid_json_interfaces(self):
        name = factory.make_name('name')
        uuid = factory.getRandomUUID()
        invalid_interfaces = factory.make_name('invalid_json_interfaces')
        form = NodeGroupWithInterfacesForm(
            data={
                'name': name, 'uuid': uuid, 'interfaces': invalid_interfaces})
        self.assertFalse(form.is_valid())
        self.assertEquals(
            {'interfaces': ['Invalid json value.']},
            form._errors)

    def test_NodeGroupWithInterfacesForm_rejects_invalid_list_interfaces(self):
        name = factory.make_name('name')
        uuid = factory.getRandomUUID()
        invalid_interfaces = json.dumps('invalid interface list')
        form = NodeGroupWithInterfacesForm(
            data={
                'name': name, 'uuid': uuid, 'interfaces': invalid_interfaces})
        self.assertFalse(form.is_valid())
        self.assertEquals(
            {'interfaces': [INTERFACES_VALIDATION_ERROR_MESSAGE]},
            form._errors)

    def test_NodeGroupWithInterfacesForm_rejects_invalid_interface(self):
        name = factory.make_name('name')
        uuid = factory.getRandomUUID()
        interface = make_interface_settings()
        # Make the interface invalid.
        interface['ip_range_high'] = 'invalid IP address'
        interfaces = json.dumps([interface])
        form = NodeGroupWithInterfacesForm(
            data={'name': name, 'uuid': uuid, 'interfaces': interfaces})
        self.assertFalse(form.is_valid())
        self.assertIn(
            "Enter a valid IPv4 address", form._errors['interfaces'][0])

    def test_NodeGroupWithInterfacesForm_creates_interface_from_params(self):
        name = factory.make_name('name')
        uuid = factory.getRandomUUID()
        interface = make_interface_settings()
        interfaces = json.dumps([interface])
        form = NodeGroupWithInterfacesForm(
            data={'name': name, 'uuid': uuid, 'interfaces': interfaces})
        self.assertTrue(form.is_valid(), form._errors)
        form.save()
        nodegroup = NodeGroup.objects.get(uuid=uuid)
        self.assertThat(
            nodegroup.nodegroupinterface_set.all()[0],
            MatchesStructure.byEquality(**interface))

    def test_form_checks_presence_of_other_managed_interfaces(self):
        name = factory.make_name('name')
        uuid = factory.getRandomUUID()
        interfaces = []
        for index in range(2):
            interface = make_interface_settings()
            interface['management'] = factory.getRandomEnum(
                NODEGROUPINTERFACE_MANAGEMENT,
                but_not=(NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED, ))
            interfaces.append(interface)
        interfaces = json.dumps(interfaces)
        form = NodeGroupWithInterfacesForm(
            data={'name': name, 'uuid': uuid, 'interfaces': interfaces})
        self.assertFalse(form.is_valid())
        self.assertIn(
            "Only one managed interface can be configured for this nodegroup",
            form._errors['interfaces'][0])

    def test_NodeGroupWithInterfacesForm_creates_multiple_interfaces(self):
        name = factory.make_name('name')
        uuid = factory.getRandomUUID()
        interface1 = make_interface_settings()
        # Only one interface at most can be 'managed'.
        interface2 = make_interface_settings()
        interface2['management'] = NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED
        interfaces = json.dumps([interface1, interface2])
        form = NodeGroupWithInterfacesForm(
            data={'name': name, 'uuid': uuid, 'interfaces': interfaces})
        self.assertTrue(form.is_valid(), form._errors)
        form.save()
        nodegroup = NodeGroup.objects.get(uuid=uuid)
        self.assertEqual(2,  nodegroup.nodegroupinterface_set.count())

    def test_NodeGroupWithInterfacesForm_creates_unmanaged_interfaces(self):
        name = factory.make_name('name')
        uuid = factory.getRandomUUID()
        interface = make_interface_settings()
        del interface['management']
        interfaces = json.dumps([interface])
        form = NodeGroupWithInterfacesForm(
            data={'name': name, 'uuid': uuid, 'interfaces': interfaces})
        self.assertTrue(form.is_valid(), form._errors)
        form.save()
        nodegroup = NodeGroup.objects.get(uuid=uuid)
        self.assertEqual(
            [NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED],
            [
                nodegroup.management for nodegroup in
                nodegroup.nodegroupinterface_set.all()
            ])
