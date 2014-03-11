# Copyright 2012-2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test forms."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import json

from django import forms
from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.validators import validate_email
from django.http import QueryDict
from maasserver.clusterrpc.power_parameters import get_power_type_choices
from maasserver.enum import (
    NODE_STATUS,
    NODEGROUP_STATUS,
    NODEGROUPINTERFACE_MANAGEMENT,
    )
from maasserver.forms import (
    AdminNodeForm,
    AdminNodeWithMACAddressesForm,
    BulkNodeActionForm,
    CommissioningScriptForm,
    ConfigForm,
    DownloadProgressForm,
    EditUserForm,
    get_action_form,
    get_node_create_form,
    get_node_edit_form,
    initialize_node_group,
    InstanceListField,
    INTERFACES_VALIDATION_ERROR_MESSAGE,
    list_all_usable_architectures,
    MACAddressForm,
    NetworkForm,
    NewUserCreationForm,
    NodeActionForm,
    NodeForm,
    NodeGroupEdit,
    NodeGroupInterfaceForeignDHCPForm,
    NodeGroupInterfaceForm,
    NodeGroupWithInterfacesForm,
    NodeWithMACAddressesForm,
    pick_default_architecture,
    ProfileForm,
    remove_None_values,
    SetZoneBulkAction,
    UnconstrainedMultipleChoiceField,
    validate_nonoverlapping_networks,
    ValidatorMultipleChoiceField,
    ZoneForm,
    )
from maasserver.models import (
    Config,
    MACAddress,
    Network,
    Node,
    NodeGroup,
    NodeGroupInterface,
    Zone,
    )
from maasserver.models.config import DEFAULT_CONFIG
from maasserver.node_action import (
    Commission,
    Delete,
    StartNode,
    StopNode,
    UseCurtin,
    )
from maasserver.testing import reload_object
from maasserver.testing.architecture import (
    make_usable_architecture,
    patch_usable_architectures,
    )
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils import map_enum
from metadataserver.models import CommissioningScript
from netaddr import IPNetwork
from provisioningserver import tasks
from testtools import TestCase
from testtools.matchers import (
    AllMatch,
    Contains,
    Equals,
    MatchesAll,
    MatchesRegex,
    MatchesStructure,
    StartsWith,
    )


class TestHelpers(MAASServerTestCase):

    def make_usable_boot_images(self, nodegroup=None, arch=None,
                                subarchitecture=None):
        """Create a set of boot images, so the architecture becomes "usable".

        This will make the images' architecture show up in the list of usable
        architecture.

        Nothing is returned.
        """
        if nodegroup is None:
            nodegroup = factory.make_node_group()
        if arch is None:
            arch = factory.make_name('arch')
        if subarchitecture is None:
            subarchitecture = factory.make_name('subarch')
        for purpose in ['install', 'commissioning']:
            factory.make_boot_image(
                nodegroup=nodegroup, architecture=arch,
                subarchitecture=subarchitecture, purpose=purpose)

    def test_initialize_node_group_leaves_nodegroup_reference_intact(self):
        preselected_nodegroup = factory.make_node_group()
        node = factory.make_node(nodegroup=preselected_nodegroup)
        initialize_node_group(node)
        self.assertEqual(preselected_nodegroup, node.nodegroup)

    def test_initialize_node_group_initializes_nodegroup_to_form_value(self):
        node = Node(
            NODE_STATUS.DECLARED, architecture=make_usable_architecture(self))
        nodegroup = factory.make_node_group()
        initialize_node_group(node, nodegroup)
        self.assertEqual(nodegroup, node.nodegroup)

    def test_initialize_node_group_defaults_to_master(self):
        node = Node(
            NODE_STATUS.DECLARED,
            architecture=make_usable_architecture(self))
        initialize_node_group(node)
        self.assertEqual(NodeGroup.objects.ensure_master(), node.nodegroup)

    def test_list_all_usable_architectures_combines_nodegroups(self):
        arches = [
            (factory.make_name('arch'), factory.make_name('subarch'))
            for _ in range(3)]
        for arch, subarch in arches:
            self.make_usable_boot_images(arch=arch, subarchitecture=subarch)
        expected = [
            "%s/%s" % (arch, subarch) for arch, subarch in arches]
        self.assertItemsEqual(expected, list_all_usable_architectures())

    def test_list_all_usable_architectures_sorts_output(self):
        arches = [
            (factory.make_name('arch'), factory.make_name('subarch'))
            for _ in range(3)]
        for arch, subarch in arches:
            self.make_usable_boot_images(arch=arch, subarchitecture=subarch)
        expected = [
            "%s/%s" % (arch, subarch) for arch, subarch in arches]
        self.assertEqual(sorted(expected), list_all_usable_architectures())

    def test_list_all_usable_architectures_returns_no_duplicates(self):
        arch = factory.make_name('arch')
        subarch = factory.make_name('subarch')
        self.make_usable_boot_images(arch=arch, subarchitecture=subarch)
        self.make_usable_boot_images(arch=arch, subarchitecture=subarch)
        self.assertEqual(
            ["%s/%s" %(arch, subarch)], list_all_usable_architectures())

    def test_pick_default_architecture_returns_empty_if_no_options(self):
        self.assertEqual('', pick_default_architecture([]))

    def test_pick_default_architecture_prefers_i386_generic_if_usable(self):
        self.assertEqual(
            'i386/generic',
            pick_default_architecture(
                ['amd64/generic', 'i386/generic', 'mips/generic']))

    def test_pick_default_architecture_falls_back_to_first_option(self):
        arches = [factory.make_name('arch') for _ in range(5)]
        self.assertEqual(arches[0], pick_default_architecture(arches))

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


class NodeWithMACAddressesFormTest(MAASServerTestCase):

    def get_QueryDict(self, params):
        query_dict = QueryDict('', mutable=True)
        for k, v in params.items():
            if isinstance(v, list):
                query_dict.setlist(k, v)
            else:
                query_dict[k] = v
        return query_dict

    def make_params(self, mac_addresses=None, architecture=None,
                    hostname=None, nodegroup=None):
        if mac_addresses is None:
            mac_addresses = [factory.getRandomMACAddress()]
        if architecture is None:
            architecture = factory.make_name('arch')
        if hostname is None:
            hostname = factory.make_name('hostname')
        params = {
            'mac_addresses': mac_addresses,
            'architecture': architecture,
            'hostname': hostname,
        }
        if nodegroup is not None:
            params['nodegroup'] = nodegroup
        # Make sure that the architecture parameter is acceptable.
        patch_usable_architectures(self, [architecture])
        return self.get_QueryDict(params)

    def test_NodeWithMACAddressesForm_valid(self):
        architecture = make_usable_architecture(self)
        form = NodeWithMACAddressesForm(
            data=self.make_params(
                mac_addresses=['aa:bb:cc:dd:ee:ff', '9a:bb:c3:33:e5:7f'],
                architecture=architecture))

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(
            ['aa:bb:cc:dd:ee:ff', '9a:bb:c3:33:e5:7f'],
            form.cleaned_data['mac_addresses'])
        self.assertEqual(architecture, form.cleaned_data['architecture'])

    def test_NodeWithMACAddressesForm_simple_invalid(self):
        # If the form only has one (invalid) MAC address field to validate,
        # the error message in form.errors['mac_addresses'] is the
        # message from the field's validation error.
        form = NodeWithMACAddressesForm(
            data=self.make_params(mac_addresses=['invalid']))

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
            data=self.make_params(mac_addresses=['invalid_1', 'invalid_2']))

        self.assertFalse(form.is_valid())
        self.assertEqual(['mac_addresses'], list(form.errors))
        self.assertEqual(
            ['One or more MAC addresses is invalid.'],
            form.errors['mac_addresses'])

    def test_NodeWithMACAddressesForm_empty(self):
        # Empty values in the list of MAC addresses are simply ignored.
        form = NodeWithMACAddressesForm(
            data=self.make_params(
                mac_addresses=[factory.getRandomMACAddress(), '']))

        self.assertTrue(form.is_valid())

    def test_NodeWithMACAddressesForm_save(self):
        macs = ['aa:bb:cc:dd:ee:ff', '9a:bb:c3:33:e5:7f']
        form = NodeWithMACAddressesForm(
            data=self.make_params(mac_addresses=macs))
        node = form.save()

        self.assertIsNotNone(node.id)  # The node is persisted.
        self.assertSequenceEqual(
            macs,
            [mac.mac_address for mac in node.macaddress_set.all()])

    def test_includes_nodegroup_field_for_new_node(self):
        self.assertIn(
            'nodegroup',
            NodeWithMACAddressesForm(data=self.make_params()).fields)

    def test_does_not_include_nodegroup_field_for_existing_node(self):
        params = self.make_params()
        node = factory.make_node()
        self.assertNotIn(
            'nodegroup',
            NodeWithMACAddressesForm(data=params, instance=node).fields)

    def test_sets_nodegroup_to_master_by_default(self):
        self.assertEqual(
            NodeGroup.objects.ensure_master(),
            NodeWithMACAddressesForm(data=self.make_params()).save().nodegroup)

    def test_leaves_nodegroup_alone_if_unset_on_existing_node(self):
        # Selecting a node group for a node is only supported on new
        # nodes.  You can't change it later.
        original_nodegroup = factory.make_node_group()
        node = factory.make_node(nodegroup=original_nodegroup)
        factory.make_node_group(network=IPNetwork("192.168.1.0/24"))
        form = NodeWithMACAddressesForm(
            data=self.make_params(nodegroup='192.168.1.0'), instance=node)
        form.save()
        self.assertEqual(original_nodegroup, reload_object(node).nodegroup)

    def test_form_without_hostname_generates_hostname(self):
        form = NodeWithMACAddressesForm(data=self.make_params(hostname=''))
        node = form.save()
        self.assertTrue(len(node.hostname) > 0)

    def test_form_with_ip_based_hostname_generates_hostname(self):
        ip_based_hostname = '192-168-12-10.domain'
        form = NodeWithMACAddressesForm(
            data=self.make_params(hostname=ip_based_hostname))
        node = form.save()
        self.assertNotEqual(ip_based_hostname, node.hostname)


class TestOptionForm(ConfigForm):
    field1 = forms.CharField(label="Field 1", max_length=10)
    field2 = forms.BooleanField(label="Field 2", required=False)


class TestValidOptionForm(ConfigForm):
    maas_name = forms.CharField(label="Field 1", max_length=10)


class ConfigFormTest(MAASServerTestCase):

    def test_form_valid_saves_into_db(self):
        value = factory.getRandomString(10)
        form = TestValidOptionForm({'maas_name': value})
        result = form.save()

        self.assertTrue(result)
        self.assertEqual(value, Config.objects.get_config('maas_name'))

    def test_form_rejects_unknown_settings(self):
        value = factory.getRandomString(10)
        value2 = factory.getRandomString(10)
        form = TestOptionForm({'field1': value, 'field2': value2})
        valid = form.is_valid()

        self.assertFalse(valid)
        self.assertIn('field1', form._errors)
        self.assertIn('field2', form._errors)

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


class TestNodeForm(MAASServerTestCase):

    def test_contains_limited_set_of_fields(self):
        form = NodeForm()

        self.assertEqual(
            [
                'hostname',
                'architecture',
                'distro_series',
                'nodegroup',
            ], list(form.fields))

    def test_changes_node(self):
        node = factory.make_node()
        hostname = factory.getRandomString()
        patch_usable_architectures(self, [node.architecture])

        form = NodeForm(
            data={
                'hostname': hostname,
                'architecture': make_usable_architecture(self),
                },
            instance=node)
        form.save()

        self.assertEqual(hostname, node.hostname)

    def test_accepts_usable_architecture(self):
        arch = make_usable_architecture(self)
        form = NodeForm(data={
            'hostname': factory.make_name('host'),
            'architecture': arch,
            })
        self.assertTrue(form.is_valid(), form._errors)

    def test_rejects_unusable_architecture(self):
        patch_usable_architectures(self)
        form = NodeForm(data={
            'hostname': factory.make_name('host'),
            'architecture': factory.make_name('arch'),
            })
        self.assertFalse(form.is_valid())
        self.assertItemsEqual(['architecture'], form._errors.keys())

    def test_starts_with_default_architecture(self):
        arches = sorted([factory.make_name('arch') for _ in range(5)])
        patch_usable_architectures(self, arches)
        form = NodeForm()
        self.assertEqual(
            pick_default_architecture(arches),
            form.fields['architecture'].initial)


class TestAdminNodeForm(MAASServerTestCase):

    def test_AdminNodeForm_contains_limited_set_of_fields(self):
        node = factory.make_node()
        form = AdminNodeForm(instance=node)

        self.assertEqual(
            [
                'hostname',
                'architecture',
                'distro_series',
                'power_type',
                'power_parameters',
                'cpu_count',
                'memory',
                'storage',
                'zone',
            ],
            list(form.fields))

    def test_AdminNodeForm_initialises_zone(self):
        # The zone field uses "to_field_name", so that it can refer to a zone
        # by name instead of by ID.  A bug in Django breaks initialisation
        # from an instance: the field tries to initialise the field using a
        # zone's ID instead of its name, and ends up reverting to the default.
        # The code must work around this bug.
        zone = factory.make_zone()
        node = factory.make_node(zone=zone)
        # We'll create a form that makes a change, but not to the zone.
        data = {'hostname': factory.make_name('host')}
        form = AdminNodeForm(instance=node, data=data)
        # The Django bug would stop the initial field value from being set,
        # but the workaround ensures that it is initialised.
        self.assertEqual(zone.name, form.initial['zone'])

    def test_AdminNodeForm_changes_node(self):
        node = factory.make_node()
        zone = factory.make_zone()
        hostname = factory.getRandomString()
        power_type = factory.getRandomPowerType()
        form = AdminNodeForm(
            data={
                'hostname': hostname,
                'power_type': power_type,
                'architecture': make_usable_architecture(self),
                'zone': zone.name,
            },
            instance=node)
        form.save()

        node = reload_object(node)
        self.assertEqual(
            (node.hostname, node.power_type, node.zone),
            (hostname, power_type, zone))

    def test_AdminNodeForm_refuses_to_update_hostname_on_allocated_node(self):
        old_name = factory.make_name('old-hostname')
        new_name = factory.make_name('new-hostname')
        node = factory.make_node(
            hostname=old_name, status=NODE_STATUS.ALLOCATED)
        form = AdminNodeForm(
            data={
                'hostname': new_name,
                'architecture': node.architecture,
                },
            instance=node)
        self.assertFalse(form.is_valid())
        self.assertEqual(
            ["Can't change hostname to %s: node is in use." % new_name],
            form._errors['hostname'])

    def test_AdminNodeForm_accepts_unchanged_hostname_on_allocated_node(self):
        old_name = factory.make_name('old-hostname')
        node = factory.make_node(
            hostname=old_name, status=NODE_STATUS.ALLOCATED)
        patch_usable_architectures(self, [node.architecture])
        form = AdminNodeForm(
            data={
                'hostname': old_name,
                'architecture': node.architecture,
            },
            instance=node)
        self.assertTrue(form.is_valid(), form._errors)
        form.save()
        self.assertEqual(old_name, reload_object(node).hostname)

    def test_AdminNodeForm_populates_power_type_choices(self):
        form = AdminNodeForm()
        self.assertEqual(
            [''] + [choice[0] for choice in get_power_type_choices()],
            [choice[0] for choice in form.fields['power_type'].choices])

    def test_AdminNodeForm_populates_power_type_initial(self):
        node = factory.make_node()
        form = AdminNodeForm(instance=node)
        self.assertEqual(node.power_type, form.fields['power_type'].initial)

    def test_AdminNodeForm_changes_node_with_skip_check(self):
        node = factory.make_node()
        hostname = factory.getRandomString()
        power_type = factory.getRandomPowerType()
        power_parameters_field = factory.getRandomString()
        arch = make_usable_architecture(self)
        form = AdminNodeForm(
            data={
                'hostname': hostname,
                'architecture': arch,
                'power_type': power_type,
                'power_parameters_field': power_parameters_field,
                'power_parameters_skip_check': True,
                },
            instance=node)
        form.save()

        self.assertEqual(
            (hostname, power_type, {'field': power_parameters_field}),
            (node.hostname, node.power_type, node.power_parameters))

    def test_AdminForm_does_not_permit_nodegroup_change(self):
        # We had to make Node.nodegroup editable to get Django to
        # validate it as non-blankable, but that doesn't mean that we
        # actually want to allow people to edit it through API or UI.
        old_nodegroup = factory.make_node_group()
        node = factory.make_node(
            nodegroup=old_nodegroup,
            architecture=make_usable_architecture(self))
        new_nodegroup = factory.make_node_group()
        AdminNodeForm(data={'nodegroup': new_nodegroup}, instance=node).save()
        # The form saved without error, but the nodegroup change was ignored.
        self.assertEqual(old_nodegroup, node.nodegroup)


class TestNodeActionForm(MAASServerTestCase):

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
        node.use_traditional_installer()
        form = get_action_form(admin)(node)

        self.assertItemsEqual(
            [Commission.name, Delete.name, UseCurtin.name],
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
            node, {NodeActionForm.input_name: Commission.name})
        self.assertTrue(form.is_valid())
        form.save()
        self.assertEqual(NODE_STATUS.COMMISSIONING, node.status)

    def test_rejects_disallowed_action(self):
        user = factory.make_user()
        node = factory.make_node(status=NODE_STATUS.DECLARED)
        form = get_action_form(user)(
            node, {NodeActionForm.input_name: Commission.name})
        self.assertFalse(form.is_valid())
        self.assertEquals(
            {'action': ['Not a permitted action: %s.' % Commission.name]},
            form._errors)

    def test_rejects_unknown_action(self):
        user = factory.make_user()
        node = factory.make_node(status=NODE_STATUS.DECLARED)
        action = factory.getRandomString()
        form = get_action_form(user)(
            node, {NodeActionForm.input_name: action})
        self.assertFalse(form.is_valid())
        self.assertIn(
            "is not one of the available choices.", form._errors['action'][0])


class TestUniqueEmailForms(MAASServerTestCase):

    def assertFormFailsValidationBecauseEmailNotUnique(self, form):
        self.assertFalse(form.is_valid())
        self.assertIn('email', form._errors)
        self.assertEquals(1, len(form._errors['email']))
        # Cope with 'Email' and 'E-mail' in error message.
        self.assertThat(
            form._errors['email'][0],
            MatchesRegex(
                r'User with this E-{0,1}mail address already exists.'))

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


class TestNewUserCreationForm(MAASServerTestCase):

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

    def test_email_is_required(self):
        password = factory.make_name('password')
        params = {
            'email': '',
            'username': factory.make_name('user'),
            'password1': password,
            'password2': password,
        }
        form = NewUserCreationForm(params)
        self.assertFalse(form.is_valid())
        self.assertEquals(
            {'email': ['This field is required.']},
            form._errors)

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


class TestMACAddressForm(MAASServerTestCase):

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


def make_interface_settings(network=None, management=None):
    """Create a dict of arbitrary interface configuration parameters."""
    if network is None:
        network = factory.getRandomNetwork()
    if management is None:
        management = factory.getRandomEnum(NODEGROUPINTERFACE_MANAGEMENT)
    # Pick upper and lower boundaries of IP range, with upper > lower.
    ip_range_low, ip_range_high = factory.make_ip_range(network)
    return {
        'ip': factory.getRandomIPInNetwork(network),
        'interface': factory.make_name('interface'),
        'subnet_mask': unicode(network.netmask),
        'broadcast_ip': unicode(network.broadcast),
        'router_ip': factory.getRandomIPInNetwork(network),
        'ip_range_low': unicode(ip_range_low),
        'ip_range_high': unicode(ip_range_high),
        'management': management,
    }


nullable_fields = [
    'subnet_mask', 'broadcast_ip', 'router_ip', 'ip_range_low',
    'ip_range_high']


class TestNodeGroupInterfaceForm(MAASServerTestCase):

    def test_NodeGroupInterfaceForm_validates_parameters(self):
        form = NodeGroupInterfaceForm(data={'ip': factory.getRandomString()})
        self.assertFalse(form.is_valid())
        self.assertEquals(
            {'ip': ['Enter a valid IPv4 or IPv6 address.']}, form._errors)

    def test_NodeGroupInterfaceForm_can_save_fields_being_None(self):
        int_settings = make_interface_settings()
        int_settings['management'] = NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED
        for field_name in nullable_fields:
            del int_settings[field_name]
        nodegroup = factory.make_node_group()
        form = NodeGroupInterfaceForm(
            data=int_settings,
            instance=NodeGroupInterface(nodegroup=nodegroup))
        interface = form.save()
        field_values = [
            getattr(interface, field_name) for field_name in nullable_fields]
        self.assertThat(field_values, AllMatch(Equals('')))


class TestNodeGroupInterfaceForeignDHCPForm(MAASServerTestCase):

    def test_forms_saves_foreign_dhcp_ip(self):
        nodegroup = factory.make_node_group()
        [interface] = nodegroup.get_managed_interfaces()
        foreign_dhcp_ip = factory.getRandomIPAddress()
        form = NodeGroupInterfaceForeignDHCPForm(
            data={'foreign_dhcp_ip': foreign_dhcp_ip},
            instance=interface)
        self.assertTrue(form.is_valid())
        form.save()
        self.assertEqual(
            foreign_dhcp_ip, reload_object(interface).foreign_dhcp_ip)

    def test_forms_validates_foreign_dhcp_ip(self):
        nodegroup = factory.make_node_group()
        [interface] = nodegroup.get_managed_interfaces()
        form = NodeGroupInterfaceForeignDHCPForm(
            data={'foreign_dhcp_ip': 'invalid-ip'}, instance=interface)
        self.assertFalse(form.is_valid())

    def test_report_foreign_dhcp_does_not_trigger_update_signal(self):
        self.patch(settings, "DHCP_CONNECT", False)
        nodegroup = factory.make_node_group(status=NODEGROUP_STATUS.ACCEPTED)
        [interface] = nodegroup.get_managed_interfaces()

        self.patch(settings, "DHCP_CONNECT", True)
        self.patch(tasks, 'write_dhcp_config')

        foreign_dhcp_ip = factory.getRandomIPAddress()
        form = NodeGroupInterfaceForeignDHCPForm(
            data={'foreign_dhcp_ip': foreign_dhcp_ip},
            instance=interface)

        self.assertTrue(form.is_valid())
        form.save()
        self.assertEqual(
            foreign_dhcp_ip, reload_object(interface).foreign_dhcp_ip)
        tasks.write_dhcp_config.apply_async.assert_has_calls([])


class TestValidateNonoverlappingNetworks(TestCase):
    """Tests for `validate_nonoverlapping_networks`."""

    def make_interface_definition(self, ip, netmask, name=None):
        """Return a minimal imitation of an interface definition."""
        if name is None:
            name = factory.make_name('itf')
        return {
            'interface': name,
            'ip': ip,
            'subnet_mask': netmask,
            'management': NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS,
        }

    def test_accepts_zero_interfaces(self):
        validate_nonoverlapping_networks([])
        # Success is getting here without error.
        pass

    def test_accepts_single_interface(self):
        validate_nonoverlapping_networks(
            [self.make_interface_definition('10.1.1.1', '255.255.0.0')])
        # Success is getting here without error.
        pass

    def test_accepts_disparate_ranges(self):
        validate_nonoverlapping_networks([
            self.make_interface_definition('10.1.0.0', '255.255.0.0'),
            self.make_interface_definition('192.168.0.0', '255.255.255.0'),
            ])
        # Success is getting here without error.
        pass

    def test_accepts_near_neighbours(self):
        validate_nonoverlapping_networks([
            self.make_interface_definition('10.1.0.0', '255.255.0.0'),
            self.make_interface_definition('10.2.0.0', '255.255.0.0'),
            ])
        # Success is getting here without error.
        pass

    def test_rejects_identical_ranges(self):
        definitions = [
            self.make_interface_definition('192.168.0.0', '255.255.255.0'),
            self.make_interface_definition('192.168.0.0', '255.255.255.0'),
            ]
        error = self.assertRaises(
            ValidationError,
            validate_nonoverlapping_networks, definitions)
        error_text = error.messages[0]
        self.assertThat(
            error_text, MatchesRegex(
                "Conflicting networks on [^\\s]+ and [^\\s]+: "
                "address ranges overlap."))
        self.assertThat(
            error_text,
            MatchesAll(
                *(
                    Contains(definition['interface'])
                    for definition in definitions
                )))

    def test_rejects_nested_ranges(self):
        definitions = [
            self.make_interface_definition('192.168.0.0', '255.255.0.0'),
            self.make_interface_definition('192.168.100.0', '255.255.255.0'),
            ]
        error = self.assertRaises(
            ValidationError,
            validate_nonoverlapping_networks, definitions)
        self.assertIn("Conflicting networks", unicode(error))

    def test_detects_conflict_regardless_of_order(self):
        definitions = [
            self.make_interface_definition('192.168.100.0', '255.255.255.0'),
            self.make_interface_definition('192.168.1.0', '255.255.255.0'),
            self.make_interface_definition('192.168.64.0', '255.255.192.0'),
            ]
        error = self.assertRaises(
            ValidationError,
            validate_nonoverlapping_networks, definitions)
        self.assertThat(error.messages[0], StartsWith("Conflicting networks"))


class TestNodeGroupWithInterfacesForm(MAASServerTestCase):

    def test_creates_pending_nodegroup(self):
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

    def test_creates_nodegroup_with_status(self):
        name = factory.make_name('name')
        uuid = factory.getRandomUUID()
        form = NodeGroupWithInterfacesForm(
            status=NODEGROUP_STATUS.ACCEPTED,
            data={'name': name, 'uuid': uuid})
        self.assertTrue(form.is_valid(), form._errors)
        nodegroup = form.save()
        self.assertEqual(NODEGROUP_STATUS.ACCEPTED, nodegroup.status)

    def test_validates_parameters(self):
        name = factory.make_name('name')
        too_long_uuid = 'test' * 30
        form = NodeGroupWithInterfacesForm(
            data={'name': name, 'uuid': too_long_uuid})
        self.assertFalse(form.is_valid())
        self.assertEquals(
            {'uuid':
                ['Ensure this value has at most 36 characters (it has 120).']},
            form._errors)

    def test_rejects_invalid_json_interfaces(self):
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

    def test_rejects_invalid_list_interfaces(self):
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

    def test_rejects_invalid_interface(self):
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
            "Enter a valid IPv4 or IPv6 address",
            form._errors['interfaces'][0])

    def test_creates_interface_from_params(self):
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

    def test_checks_against_conflicting_managed_networks(self):
        big_network = IPNetwork('10.0.0.0/255.255.0.0')
        nested_network = IPNetwork('10.0.100.0/255.255.255.0')
        managed = NODEGROUPINTERFACE_MANAGEMENT.DHCP
        form = NodeGroupWithInterfacesForm(
            data={
                'name': factory.make_name('cluster'),
                'uuid': factory.getRandomUUID(),
                'interfaces': json.dumps([
                    make_interface_settings(
                        network=big_network, management=managed),
                    make_interface_settings(
                        network=nested_network, management=managed),
                    ]),
            })
        self.assertFalse(form.is_valid())
        self.assertNotEqual([], form._errors['interfaces'])
        self.assertThat(
            form._errors['interfaces'][0],
            StartsWith("Conflicting networks"))

    def test_ignores_conflicts_on_unmanaged_interfaces(self):
        big_network = IPNetwork('10.0.0.0/255.255.0.0')
        nested_network = IPNetwork('10.100.100.0/255.255.255.0')
        managed = NODEGROUPINTERFACE_MANAGEMENT.DHCP
        unmanaged = NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED
        form = NodeGroupWithInterfacesForm(
            data={
                'name': factory.make_name('cluster'),
                'uuid': factory.getRandomUUID(),
                'interfaces': json.dumps([
                    make_interface_settings(
                        network=big_network, management=managed),
                    make_interface_settings(
                        network=nested_network, management=unmanaged),
                    ]),
            })
        is_valid = form.is_valid()
        self.assertEqual(
            (True, None),
            (is_valid, form._errors.get('interfaces')))

    def test_creates_multiple_interfaces(self):
        name = factory.make_name('name')
        uuid = factory.getRandomUUID()
        interfaces = [
            make_interface_settings(management=management)
            for management in map_enum(NODEGROUPINTERFACE_MANAGEMENT).values()
            ]
        form = NodeGroupWithInterfacesForm(
            data={
                'name': name,
                'uuid': uuid,
                'interfaces': json.dumps(interfaces),
                })
        self.assertTrue(form.is_valid(), form._errors)
        form.save()
        nodegroup = NodeGroup.objects.get(uuid=uuid)
        self.assertEqual(
            len(interfaces), nodegroup.nodegroupinterface_set.count())

    def test_populates_cluster_name_default(self):
        name = factory.make_name('name')
        uuid = factory.getRandomUUID()
        form = NodeGroupWithInterfacesForm(
            status=NODEGROUP_STATUS.ACCEPTED,
            data={'name': name, 'uuid': uuid})
        self.assertTrue(form.is_valid(), form._errors)
        nodegroup = form.save()
        self.assertIn(uuid, nodegroup.cluster_name)

    def test_populates_cluster_name(self):
        cluster_name = factory.make_name('cluster_name')
        uuid = factory.getRandomUUID()
        form = NodeGroupWithInterfacesForm(
            status=NODEGROUP_STATUS.ACCEPTED,
            data={'cluster_name': cluster_name, 'uuid': uuid})
        self.assertTrue(form.is_valid(), form._errors)
        nodegroup = form.save()
        self.assertEqual(cluster_name, nodegroup.cluster_name)

    def test_creates_unmanaged_interfaces(self):
        name = factory.make_name('name')
        uuid = factory.getRandomUUID()
        interface = make_interface_settings()
        del interface['management']
        interfaces = json.dumps([interface])
        form = NodeGroupWithInterfacesForm(
            data={'name': name, 'uuid': uuid, 'interfaces': interfaces})
        self.assertTrue(form.is_valid(), form._errors)
        form.save()
        uuid_nodegroup = NodeGroup.objects.get(uuid=uuid)
        self.assertEqual(
            [NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED],
            [
                nodegroup.management for nodegroup in
                uuid_nodegroup.nodegroupinterface_set.all()
            ])


class TestNodeGroupEdit(MAASServerTestCase):

    def make_form_data(self, nodegroup):
        """Create `NodeGroupEdit` form data based on `nodegroup`."""
        return {
            'name': nodegroup.name,
            'cluster_name': nodegroup.cluster_name,
            'status': nodegroup.status,
        }

    def test_changes_name(self):
        nodegroup = factory.make_node_group(name=factory.make_name('old-name'))
        new_name = factory.make_name('new-name')
        data = self.make_form_data(nodegroup)
        data['name'] = new_name
        form = NodeGroupEdit(instance=nodegroup, data=data)
        self.assertTrue(form.is_valid())
        form.save()
        self.assertEqual(new_name, reload_object(nodegroup).name)

    def test_refuses_name_change_if_dns_managed_and_nodes_in_use(self):
        nodegroup, node = factory.make_unrenamable_nodegroup_with_node()
        data = self.make_form_data(nodegroup)
        data['name'] = factory.make_name('new-name')
        form = NodeGroupEdit(instance=nodegroup, data=data)
        self.assertFalse(form.is_valid())

    def test_accepts_unchanged_name(self):
        nodegroup, node = factory.make_unrenamable_nodegroup_with_node()
        original_name = nodegroup.name
        form = NodeGroupEdit(
            instance=nodegroup, data=self.make_form_data(nodegroup))
        self.assertTrue(form.is_valid())
        form.save()
        self.assertEqual(original_name, reload_object(nodegroup).name)

    def test_accepts_omitted_name(self):
        nodegroup, node = factory.make_unrenamable_nodegroup_with_node()
        original_name = nodegroup.name
        data = self.make_form_data(nodegroup)
        del data['name']
        form = NodeGroupEdit(instance=nodegroup, data=data)
        self.assertTrue(form.is_valid())
        form.save()
        self.assertEqual(original_name, reload_object(nodegroup).name)

    def test_accepts_name_change_if_nodegroup_not_accepted(self):
        nodegroup, node = factory.make_unrenamable_nodegroup_with_node()
        nodegroup.status = NODEGROUP_STATUS.PENDING
        data = self.make_form_data(nodegroup)
        data['name'] = factory.make_name('new-name')
        form = NodeGroupEdit(instance=nodegroup, data=data)
        self.assertTrue(form.is_valid())

    def test_accepts_name_change_if_dns_managed_but_no_nodes_in_use(self):
        nodegroup, node = factory.make_unrenamable_nodegroup_with_node()
        node.status = NODE_STATUS.READY
        node.save()
        data = self.make_form_data(nodegroup)
        data['name'] = factory.make_name('new-name')
        form = NodeGroupEdit(instance=nodegroup, data=data)
        self.assertTrue(form.is_valid())
        form.save()
        self.assertEqual(data['name'], reload_object(nodegroup).name)

    def test_accepts_name_change_if_nodes_in_use_but_dns_not_managed(self):
        nodegroup, node = factory.make_unrenamable_nodegroup_with_node()
        [interface] = nodegroup.get_managed_interfaces()
        interface.management = NODEGROUPINTERFACE_MANAGEMENT.DHCP
        interface.save()
        data = self.make_form_data(nodegroup)
        data['name'] = factory.make_name('new-name')
        form = NodeGroupEdit(instance=nodegroup, data=data)
        self.assertTrue(form.is_valid())
        form.save()
        self.assertEqual(data['name'], reload_object(nodegroup).name)

    def test_accepts_name_change_if_nodegroup_has_no_interface(self):
        nodegroup, node = factory.make_unrenamable_nodegroup_with_node()
        NodeGroupInterface.objects.filter(nodegroup=nodegroup).delete()
        data = self.make_form_data(nodegroup)
        data['name'] = factory.make_name('new-name')
        form = NodeGroupEdit(instance=nodegroup, data=data)
        self.assertTrue(form.is_valid())
        form.save()
        self.assertEqual(data['name'], reload_object(nodegroup).name)


class TestCommissioningScriptForm(MAASServerTestCase):

    def test_creates_commissioning_script(self):
        content = factory.getRandomString().encode('ascii')
        name = factory.make_name('filename')
        uploaded_file = SimpleUploadedFile(content=content, name=name)
        form = CommissioningScriptForm(files={'content': uploaded_file})
        self.assertTrue(form.is_valid(), form._errors)
        form.save()
        new_script = CommissioningScript.objects.get(name=name)
        self.assertThat(
            new_script,
            MatchesStructure.byEquality(name=name, content=content))

    def test_raises_if_duplicated_name(self):
        content = factory.getRandomString().encode('ascii')
        name = factory.make_name('filename')
        factory.make_commissioning_script(name=name)
        uploaded_file = SimpleUploadedFile(content=content, name=name)
        form = CommissioningScriptForm(files={'content': uploaded_file})
        self.assertEqual(
            (False, {'content': ["A script with that name already exists."]}),
            (form.is_valid(), form._errors))

    def test_rejects_whitespace_in_name(self):
        name = factory.make_name('with space')
        content = factory.getRandomString().encode('ascii')
        uploaded_file = SimpleUploadedFile(content=content, name=name)
        form = CommissioningScriptForm(files={'content': uploaded_file})
        self.assertFalse(form.is_valid())
        self.assertEqual(
            ["Name contains disallowed characters (e.g. space or quotes)."],
            form._errors['content'])

    def test_rejects_quotes_in_name(self):
        name = factory.make_name("l'horreur")
        content = factory.getRandomString().encode('ascii')
        uploaded_file = SimpleUploadedFile(content=content, name=name)
        form = CommissioningScriptForm(files={'content': uploaded_file})
        self.assertFalse(form.is_valid())
        self.assertEqual(
            ["Name contains disallowed characters (e.g. space or quotes)."],
            form._errors['content'])


class TestUnconstrainedMultipleChoiceField(MAASServerTestCase):

    def test_accepts_list(self):
        value = ['a', 'b']
        instance = UnconstrainedMultipleChoiceField()
        self.assertEqual(value, instance.clean(value))


class TestValidatorMultipleChoiceField(MAASServerTestCase):

    def test_field_validates_valid_data(self):
        value = ['test@example.com', 'me@example.com']
        field = ValidatorMultipleChoiceField(validator=validate_email)
        self.assertEqual(value, field.clean(value))

    def test_field_uses_validator(self):
        value = ['test@example.com', 'invalid-email']
        field = ValidatorMultipleChoiceField(validator=validate_email)
        error = self.assertRaises(ValidationError, field.clean, value)
        self.assertEquals(['Enter a valid email address.'], error.messages)


class TestBulkNodeActionForm(MAASServerTestCase):

    def test_performs_action(self):
        node1 = factory.make_node()
        node2 = factory.make_node()
        node3 = factory.make_node()
        system_id_to_delete = [node1.system_id, node2.system_id]
        form = BulkNodeActionForm(
            user=factory.make_admin(),
            data=dict(
                action=Delete.name,
                system_id=system_id_to_delete))
        self.assertTrue(form.is_valid(), form._errors)
        done, not_actionable, not_permitted = form.save()
        existing_nodes = list(Node.objects.filter(
            system_id__in=system_id_to_delete))
        node3_system_id = reload_object(node3).system_id
        self.assertEqual(
            [2, 0, 0],
            [done, not_actionable, not_permitted])
        self.assertEqual(
            [[], node3.system_id],
            [existing_nodes, node3_system_id])

    def test_first_action_is_empty(self):
        form = BulkNodeActionForm(user=factory.make_admin())
        action = form.fields['action']
        default_action = action.choices[0][0]
        required = action.required
        # The default action is the empty string (i.e. no action)
        # and it's a required field.
        self.assertEqual(('', True), (default_action, required))

    def test_admin_is_offered_bulk_node_change(self):
        form = BulkNodeActionForm(user=factory.make_admin())
        choices = form.fields['action'].choices
        self.assertNotEqual(
            [],
            [choice for choice in choices if choice[0] == 'set_zone'])

    def test_nonadmin_is_not_offered_bulk_node_change(self):
        form = BulkNodeActionForm(user=factory.make_user())
        choices = form.fields['action'].choices
        self.assertEqual(
            [],
            [choice for choice in choices if choice[0] == 'set_zone'])

    def test_gives_stat_when_not_applicable(self):
        node1 = factory.make_node(status=NODE_STATUS.DECLARED)
        node2 = factory.make_node(status=NODE_STATUS.FAILED_TESTS)
        system_id_for_action = [node1.system_id, node2.system_id]
        form = BulkNodeActionForm(
            user=factory.make_admin(),
            data=dict(
                action=StartNode.name,
                system_id=system_id_for_action))
        self.assertTrue(form.is_valid(), form._errors)
        done, not_actionable, not_permitted = form.save()
        self.assertEqual(
            [0, 2, 0],
            [done, not_actionable, not_permitted])

    def test_gives_stat_when_no_permission(self):
        user = factory.make_user()
        node = factory.make_node(
            status=NODE_STATUS.ALLOCATED, owner=factory.make_user())
        system_id_for_action = [node.system_id]
        form = BulkNodeActionForm(
            user=user,
            data=dict(
                action=StopNode.name,
                system_id=system_id_for_action))
        self.assertTrue(form.is_valid(), form._errors)
        done, not_actionable, not_permitted = form.save()
        self.assertEqual(
            [0, 0, 1],
            [done, not_actionable, not_permitted])

    def test_gives_stat_when_action_is_inhibited(self):
        node = factory.make_node(
            status=NODE_STATUS.ALLOCATED, owner=factory.make_user())
        form = BulkNodeActionForm(
            user=factory.make_admin(),
            data=dict(
                action=Delete.name,
                system_id=[node.system_id]))
        self.assertTrue(form.is_valid(), form._errors)
        done, not_actionable, not_permitted = form.save()
        self.assertEqual(
            [0, 1, 0],
            [done, not_actionable, not_permitted])

    def test_rejects_empty_system_ids(self):
        form = BulkNodeActionForm(
            user=factory.make_admin(),
            data=dict(action=Delete.name, system_id=[]))
        self.assertFalse(form.is_valid(), form._errors)
        self.assertEqual(
            ["No node selected."],
            form._errors['system_id'])

    def test_rejects_invalid_system_ids(self):
        node = factory.make_node()
        system_id_to_delete = [node.system_id, "wrong-system_id"]
        form = BulkNodeActionForm(
            user=factory.make_admin(),
            data=dict(
                action=Delete.name,
                system_id=system_id_to_delete))
        self.assertFalse(form.is_valid(), form._errors)
        self.assertEqual(
            ["Some of the given system ids are invalid system ids."],
            form._errors['system_id'])

    def test_rejects_if_no_action(self):
        form = BulkNodeActionForm(
            user=factory.make_admin(),
            data=dict(system_id=[factory.make_node().system_id]))
        self.assertFalse(form.is_valid(), form._errors)

    def test_rejects_if_invalid_action(self):
        form = BulkNodeActionForm(
            user=factory.make_admin(),
            data=dict(
                action="invalid-action",
                system_id=[factory.make_node().system_id]))
        self.assertFalse(form.is_valid(), form._errors)

    def test_set_zone_sets_zone_on_node(self):
        node = factory.make_node()
        zone = factory.make_zone()
        form = BulkNodeActionForm(
            user=factory.make_admin(),
            data={
                'action': 'set_zone',
                'zone': zone.name,
                'system_id': [node.system_id],
            })
        self.assertTrue(form.is_valid(), form._errors)
        self.assertEqual((1, 0, 0), form.save())
        node = reload_object(node)
        self.assertEqual(zone, node.zone)

    def test_set_zone_does_not_work_if_not_admin(self):
        node = factory.make_node()
        form = BulkNodeActionForm(
            user=factory.make_user(),
            data={
                'action': SetZoneBulkAction.name,
                'zone': factory.make_zone().name,
                'system_id': [node.system_id],
            })
        self.assertFalse(form.is_valid())
        self.assertIn(
            "Select a valid choice. "
            "set_zone is not one of the available choices.",
            form._errors['action'])

    def test_zone_field_rejects_empty_zone(self):
        # If the field is present, the zone name has to be valid
        # and the empty string is not a valid zone name.
        form = BulkNodeActionForm(
            user=factory.make_admin(),
            data={
                'action': SetZoneBulkAction.name,
                'zone': '',
            })
        self.assertFalse(form.is_valid(), form._errors)
        self.assertEqual(
            ["This field is required."],
            form._errors['zone'])

    def test_zone_field_present_if_data_is_empty(self):
        form = BulkNodeActionForm(
            user=factory.make_admin(),
            data={})
        self.assertIn('zone', form.fields)

    def test_zone_field_not_present_action_is_not_SetZoneBulkAction(self):
        form = BulkNodeActionForm(
            user=factory.make_admin(),
            data={'action': factory.make_name('action')})
        self.assertNotIn('zone', form.fields)

    def test_set_zone_leaves_unselected_nodes_alone(self):
        unselected_node = factory.make_node()
        original_zone = unselected_node.zone
        form = BulkNodeActionForm(
            user=factory.make_admin(),
            data={
                'action': SetZoneBulkAction.name,
                'zone': factory.make_zone().name,
                'system_id': [factory.make_node().system_id],
            })
        self.assertTrue(form.is_valid(), form._errors)
        self.assertEqual((1, 0, 0), form.save())
        unselected_node = reload_object(unselected_node)
        self.assertEqual(original_zone, unselected_node.zone)


class TestDownloadProgressForm(MAASServerTestCase):

    def test_updates_instance(self):
        progress = factory.make_download_progress_incomplete(size=None)
        new_bytes_downloaded = progress.bytes_downloaded + 1
        size = progress.bytes_downloaded + 2
        error = factory.getRandomString()

        form = DownloadProgressForm(
            data={
                'size': size,
                'bytes_downloaded': new_bytes_downloaded,
                'error': error,
            },
            instance=progress)
        new_progress = form.save()

        progress = reload_object(progress)
        self.assertEqual(progress, new_progress)
        self.assertEqual(size, progress.size)
        self.assertEqual(new_bytes_downloaded, progress.bytes_downloaded)
        self.assertEqual(error, progress.error)

    def test_rejects_unknown_ongoing_download(self):
        form = DownloadProgressForm(
            data={'bytes_downloaded': 1}, instance=None)

        self.assertFalse(form.is_valid())

    def test_get_download_returns_ongoing_download(self):
        progress = factory.make_download_progress_incomplete()

        self.assertEqual(
            progress,
            DownloadProgressForm.get_download(
                progress.nodegroup, progress.filename,
                progress.bytes_downloaded + 1))

    def test_get_download_recognises_start_of_new_download(self):
        nodegroup = factory.make_node_group()
        filename = factory.getRandomString()
        progress = DownloadProgressForm.get_download(nodegroup, filename, None)
        self.assertIsNotNone(progress)
        self.assertEqual(nodegroup, progress.nodegroup)
        self.assertEqual(filename, progress.filename)
        self.assertIsNone(progress.bytes_downloaded)

    def test_get_download_returns_none_for_unknown_ongoing_download(self):
        self.assertIsNone(
            DownloadProgressForm.get_download(
                factory.make_node_group(), factory.getRandomString(), 1))


class TestZoneForm(MAASServerTestCase):
    """Tests for `ZoneForm`."""

    def test_creates_zone(self):
        name = factory.make_name('zone')
        description = factory.getRandomString()
        form = ZoneForm(data={'name': name, 'description': description})
        form.save()
        zone = Zone.objects.get(name=name)
        self.assertIsNotNone(zone)
        self.assertEqual(description, zone.description)

    def test_updates_zone(self):
        zone = factory.make_zone()
        new_description = factory.getRandomString()
        form = ZoneForm(data={'description': new_description}, instance=zone)
        form.save()
        zone = reload_object(zone)
        self.assertEqual(new_description, zone.description)

    def test_renames_zone(self):
        zone = factory.make_zone()
        new_name = factory.make_name('zone')
        form = ZoneForm(data={'name': new_name}, instance=zone)
        form.save()
        zone = reload_object(zone)
        self.assertEqual(new_name, zone.name)
        self.assertEqual(zone, Zone.objects.get(name=new_name))

    def test_update_default_zone_description_works(self):
        zone = Zone.objects.get_default_zone()
        new_description = factory.getRandomString()
        form = ZoneForm(data={'description': new_description}, instance=zone)
        self.assertTrue(form.is_valid(), form._errors)
        form.save()
        zone = reload_object(zone)
        self.assertEqual(new_description, zone.description)

    def test_disallows_renaming_default_zone(self):
        zone = Zone.objects.get_default_zone()
        form = ZoneForm(
            data={'name': factory.make_name('zone')},
            instance=zone)
        self.assertFalse(form.is_valid())
        self.assertEqual(
            {'name': ["This zone is the default zone, it cannot be renamed."]},
            form.errors)


class TestNetworkForm(MAASServerTestCase):
    """Tests for `NetworkForm`."""

    def test_creates_network(self):
        network = factory.getRandomNetwork()
        name = factory.make_name('network')
        definition = {
            'name': name,
            'description': factory.getRandomString(),
            'ip': "%s" % network.cidr.ip,
            'netmask': "%s" % network.netmask,
            'vlan_tag': factory.make_vlan_tag(),
        }
        form = NetworkForm(data=definition)
        form.save()
        network_obj = Network.objects.get(name=name)
        self.assertAttributes(network_obj, definition)

    def test_updates_network(self):
        network = factory.make_network()
        new_description = factory.getRandomString()
        form = NetworkForm(
            data={'description': new_description}, instance=network)
        form.save()
        network = reload_object(network)
        self.assertEqual(new_description, network.description)

    def test_populates_initial_macaddresses(self):
        network = factory.make_network()
        macs = [
            factory.make_mac_address(networks=[network])
            for _ in range(3)]
        # Create other MAC addresses.
        for _ in range(2):
            factory.make_mac_address(networks=[factory.make_network()])
        new_description = factory.getRandomString()
        form = NetworkForm(
            data={'description': new_description}, instance=network)
        self.assertItemsEqual(
            [mac.mac_address.get_raw() for mac in macs],
            form.initial['mac_addresses'])

    def test_macaddresses_are_sorted(self):
        network1, network2 = factory.make_networks(2)
        macs = [
            factory.make_mac_address(networks=[network1])
            for _ in range(3)]
        # Create macs connected to the same node.
        macs = macs + [
            factory.make_mac_address(networks=[network1], node=macs[0].node)
            for _ in range(3)]
        # Create other MAC addresses.
        for _ in range(2):
            factory.make_mac_address(networks=[network2])
        form = NetworkForm(data={}, instance=network1)
        self.assertEqual(
            list(MACAddress.objects.all().order_by(
                'node__hostname', 'mac_address')),
            list(form.fields['mac_addresses'].queryset))

    def test_macaddresses_widget_displays_MAC_and_node_hostname(self):
        network = factory.make_network()
        [
            factory.make_mac_address(networks=[network])
            for _ in range(3)]
        # Create other MAC addresses.
        for _ in range(2):
            factory.make_mac_address(networks=[factory.make_network()])
        form = NetworkForm(data={}, instance=network)
        self.assertItemsEqual(
            [(mac.mac_address, "%s (%s)" % (
                mac.mac_address, mac.node.hostname))
             for mac in MACAddress.objects.all()],
            form.fields['mac_addresses'].widget.choices)

    def test_updates_macaddresses(self):
        network = factory.make_network()
        # Attach a couple of MAC addresses to the network.
        [factory.make_mac_address(networks=[network]) for _ in range(3)]
        new_macs = [
            factory.make_mac_address()
            for _ in range(3)]
        form = NetworkForm(
            data={
                'mac_addresses': [
                    mac.mac_address.get_raw() for mac in new_macs],
            },
            instance=network)
        form.save()
        network = reload_object(network)
        self.assertItemsEqual(new_macs, network.macaddress_set.all())


class TestInstanceListField(MAASServerTestCase):
    """Tests for `InstanceListingField`."""

    def test_field_validates_valid_data(self):
        nodes = [factory.make_node() for i in range(3)]
        # Create other nodes.
        [factory.make_node() for i in range(3)]
        field = InstanceListField(model_class=Node, field_name='system_id')
        input_data = [node.system_id for node in nodes]
        self.assertItemsEqual(
            input_data,
            [node.system_id for node in field.clean(input_data)])

    def test_field_ignores_duplicates(self):
        nodes = [factory.make_node() for i in range(2)]
        # Create other nodes.
        [factory.make_node() for i in range(3)]
        field = InstanceListField(model_class=Node, field_name='system_id')
        input_data = [node.system_id for node in nodes] * 2
        self.assertItemsEqual(
            set(input_data),
            [node.system_id for node in field.clean(input_data)])

    def test_field_rejects_invalid_data(self):
        nodes = [factory.make_node() for i in range(3)]
        field = InstanceListField(model_class=Node, field_name='system_id')
        error = self.assertRaises(
            ValidationError,
            field.clean, [node.system_id for node in nodes] + ['unknown'])
        self.assertEquals(['Unknown node(s): unknown.'], error.messages)
