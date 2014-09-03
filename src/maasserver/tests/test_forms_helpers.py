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

from maasserver.enum import NODE_STATUS
from maasserver.forms import (
    AdminNodeForm,
    AdminNodeWithMACAddressesForm,
    get_node_create_form,
    get_node_edit_form,
    initialize_node_group,
    list_all_usable_architectures,
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


class TestHelpers(MAASServerTestCase):

    def make_usable_boot_images(self, nodegroup=None, osystem=None,
                                arch=None, subarchitecture=None, release=None):
        """Create a set of boot images, so the architecture becomes "usable".

        This will make the images' architecture show up in the list of usable
        architecture.

        Nothing is returned.
        """
        if nodegroup is None:
            nodegroup = factory.make_node_group()
        if osystem is None:
            osystem = factory.make_name('os')
        if arch is None:
            arch = factory.make_name('arch')
        if subarchitecture is None:
            subarchitecture = factory.make_name('subarch')
        if release is None:
            release = factory.make_name('release')
        for purpose in ['install', 'commissioning']:
            factory.make_boot_image(
                nodegroup=nodegroup, osystem=osystem, architecture=arch,
                subarchitecture=subarchitecture, release=release,
                purpose=purpose)

    def test_initialize_node_group_leaves_nodegroup_reference_intact(self):
        preselected_nodegroup = factory.make_node_group()
        node = factory.make_node(nodegroup=preselected_nodegroup)
        initialize_node_group(node)
        self.assertEqual(preselected_nodegroup, node.nodegroup)

    def test_initialize_node_group_initializes_nodegroup_to_form_value(self):
        node = Node(
            NODE_STATUS.NEW, architecture=make_usable_architecture(self))
        nodegroup = factory.make_node_group()
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
