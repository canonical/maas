# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for forms helpers."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from django.forms import CharField
from maasserver.enum import (
    BOOT_RESOURCE_TYPE,
    NODE_STATUS,
    )
from maasserver.forms import (
    AdminNodeForm,
    AdminNodeWithMACAddressesForm,
    get_node_create_form,
    get_node_edit_form,
    initialize_node_group,
    list_all_usable_architectures,
    MAASModelForm,
    NodeForm,
    NodeWithMACAddressesForm,
    pick_default_architecture,
    remove_None_values,
    )
from maasserver.models import (
    Node,
    NodeGroup,
    )
from maasserver.testing.architecture import make_usable_architecture
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.tests.models import GenericTestModel
from maastesting.djangotestcase import TestModelMixin
from testtools.matchers import Equals


class TestHelpers(MAASServerTestCase):

    def make_usable_boot_resource(self, arch=None, subarch=None):
        """Create a set of boot resources, so the architecture becomes usable.

        This will make the resources' architecture show up in the list of
        usable architectures.
        """
        if arch is None:
            arch = factory.make_name('arch')
        if subarch is None:
            subarch = factory.make_name('subarch')
        for purpose in ['install', 'commissioning']:
            architecture = '%s/%s' % (arch, subarch)
            factory.make_usable_boot_resource(
                rtype=BOOT_RESOURCE_TYPE.SYNCED, architecture=architecture)

    def test_initialize_node_group_leaves_nodegroup_reference_intact(self):
        preselected_nodegroup = factory.make_NodeGroup()
        node = factory.make_Node(nodegroup=preselected_nodegroup)
        initialize_node_group(node)
        self.assertEqual(preselected_nodegroup, node.nodegroup)

    def test_initialize_node_group_initializes_nodegroup_to_form_value(self):
        node = Node(
            NODE_STATUS.NEW, architecture=make_usable_architecture(self))
        nodegroup = factory.make_NodeGroup()
        initialize_node_group(node, nodegroup)
        self.assertEqual(nodegroup, node.nodegroup)

    def test_initialize_node_group_defaults_to_master(self):
        node = Node(
            NODE_STATUS.NEW,
            architecture=make_usable_architecture(self))
        initialize_node_group(node)
        self.assertEqual(NodeGroup.objects.ensure_master(), node.nodegroup)

    def test_list_all_usable_architectures_combines_nodegroups(self):
        arches = [
            (factory.make_name('arch'), factory.make_name('subarch'))
            for _ in range(3)]
        for arch, subarch in arches:
            self.make_usable_boot_resource(arch=arch, subarch=subarch)
        expected = [
            "%s/%s" % (arch, subarch) for arch, subarch in arches]
        self.assertItemsEqual(expected, list_all_usable_architectures())

    def test_list_all_usable_architectures_sorts_output(self):
        arches = [
            (factory.make_name('arch'), factory.make_name('subarch'))
            for _ in range(3)]
        for arch, subarch in arches:
            self.make_usable_boot_resource(arch=arch, subarch=subarch)
        expected = [
            "%s/%s" % (arch, subarch) for arch, subarch in arches]
        self.assertEqual(sorted(expected), list_all_usable_architectures())

    def test_list_all_usable_architectures_returns_no_duplicates(self):
        arch = factory.make_name('arch')
        subarch = factory.make_name('subarch')
        self.make_usable_boot_resource(arch=arch, subarch=subarch)
        self.make_usable_boot_resource(arch=arch, subarch=subarch)
        self.assertEqual(
            ["%s/%s" % (arch, subarch)], list_all_usable_architectures())

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
        random_input = factory.make_string()
        self.assertEqual(
            {random_input: random_input},
            remove_None_values({
                random_input: random_input,
                factory.make_string(): None,
                }))

    def test_remove_None_values_leaves_empty_dict_untouched(self):
        self.assertEqual({}, remove_None_values({}))

    def test_get_node_edit_form_returns_NodeForm_if_non_admin(self):
        user = factory.make_User()
        self.assertEqual(NodeForm, get_node_edit_form(user))

    def test_get_node_edit_form_returns_APIAdminNodeEdit_if_admin(self):
        admin = factory.make_admin()
        self.assertEqual(AdminNodeForm, get_node_edit_form(admin))

    def test_get_node_create_form_if_non_admin(self):
        user = factory.make_User()
        self.assertEqual(
            NodeWithMACAddressesForm, get_node_create_form(user))

    def test_get_node_create_form_if_admin(self):
        admin = factory.make_admin()
        self.assertEqual(
            AdminNodeWithMACAddressesForm, get_node_create_form(admin))


class TestMAASModelForm(TestModelMixin, MAASServerTestCase):

    app = 'maasserver.tests'

    def test_model_class_from_UI_has_hidden_field(self):
        class TestClass(MAASModelForm):
            class Meta:
                model = GenericTestModel

        form = TestClass(ui_submission=True)
        self.assertIn('ui_submission', form.fields)
        self.assertTrue(
            form.fields['ui_submission'].widget.is_hidden,
            "ui_submission field is not 'hidden'")

    def test_model_class_from_API_doesnt_have_hidden_field(self):
        class TestClass(MAASModelForm):
            class Meta:
                model = GenericTestModel

        form = TestClass()
        self.assertNotIn('ui_submission', form.fields)

    def test_hidden_field_is_available_to_all_field_cleaning_methods(self):

        class EarlyFieldMixin:
            """Mixin to sneak a field into our form early.

            Proves that the `ui_submission` field is present for all field
            validators, regardless of the order in which the fields were added
            to the form.
            """
            def __init__(self, *args, **kwargs):
                super(EarlyFieldMixin, self).__init__(*args, **kwargs)
                self.fields['early_field'] = CharField(required=False)

        class TestForm(EarlyFieldMixin, MAASModelForm):

            extra_field = CharField(required=False)

            def clean_early_field(self, *args, **kwargs):
                """Cleaner for `GenericTestModel.field`."""
                self.while_early_field = ('ui_submission' in self.cleaned_data)

            def clean_field(self, *args, **kwargs):
                """Cleaner for `GenericTestModel.field`."""
                self.while_field = ('ui_submission' in self.cleaned_data)

            def clean_extra_field(self, *args, **kwargs):
                """Cleaner for `TestForm.extra_field`."""
                self.while_extra_field = ('ui_submission' in self.cleaned_data)

            class Meta:
                model = GenericTestModel
                fields = ('field', )

        form = TestForm(ui_submission=True, data={})
        self.assertTrue(form.is_valid(), form._errors)
        self.expectThat(form.while_early_field, Equals(True))
        self.expectThat(form.while_field, Equals(True))
        self.expectThat(form.while_extra_field, Equals(True))
