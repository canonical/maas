# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for Curtin-related utilities."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver.utils.curtin import (
    compose_mv_command,
    compose_recursive_copy,
    compose_write_text_file,
    )
from testtools.matchers import (
    AllMatch,
    ContainsAll,
    IsInstance,
    )


class TestComposeMvCommand(MAASTestCase):

    def test__returns_command_list(self):
        command = compose_mv_command(
            factory.make_name('source'), factory.make_name('dest'))
        self.expectThat(command, IsInstance(list))
        self.expectThat(command, AllMatch(IsInstance(unicode)))

    def test__runs_command_in_target(self):
        command = compose_mv_command(
            factory.make_name('source'), factory.make_name('dest'))
        curtin_prefix = ['curtin', 'in-target', '--']
        self.assertEqual(curtin_prefix, command[:len(curtin_prefix)])

    def test__moves_file(self):
        source = factory.make_name('source')
        dest = factory.make_name('dest')
        command = compose_mv_command(source, dest)
        mv_suffix = ['mv', '--', source, dest]
        self.assertEqual(mv_suffix, command[-len(mv_suffix):])


class TestComposeRecursiveCopy(MAASTestCase):

    def test__returns_command_list(self):
        command = compose_recursive_copy(
            factory.make_name('source'), factory.make_name('dest'))
        self.expectThat(command, IsInstance(list))
        self.expectThat(command, AllMatch(IsInstance(unicode)))

    def test__runs_command_in_target(self):
        command = compose_recursive_copy(
            factory.make_name('source'), factory.make_name('dest'))
        curtin_prefix = ['curtin', 'in-target', '--']
        self.assertEqual(curtin_prefix, command[:len(curtin_prefix)])

    def test__copies(self):
        source = factory.make_name('source')
        dest = factory.make_name('dest')
        command = compose_recursive_copy(source, dest)
        cp_suffix = ['cp', '-r', '-p', '--', source, dest]
        self.assertEqual(cp_suffix, command[-len(cp_suffix):])


class TestComposeWriteTextFile(MAASTestCase):

    def test__returns_complete_write_file_dict(self):
        preseed = compose_write_text_file(
            factory.make_name('file'), factory.make_name('content'))
        self.expectThat(preseed, IsInstance(dict))
        self.expectThat(
            preseed.keys(),
            ContainsAll(['path', 'content', 'owner', 'permissions']))

    def test__obeys_path_param(self):
        path = factory.make_name('path')
        preseed = compose_write_text_file(path, factory.make_name('content'))
        self.assertEqual(path, preseed['path'])

    def test__obeys_content_param(self):
        content = factory.make_name('content')
        preseed = compose_write_text_file(factory.make_name('path'), content)
        self.assertEqual(content, preseed['content'])

    def test__defaults_owner_to_root(self):
        preseed = compose_write_text_file(
            factory.make_name('file'), factory.make_name('content'))
        self.assertEqual('root:root', preseed['owner'])

    def test__obeys_owner_param(self):
        owner = '%s:%s' % (
            factory.make_name('user'),
            factory.make_name('group'),
            )
        preseed = compose_write_text_file(
            factory.make_name('file'), factory.make_name('content'),
            owner=owner)
        self.assertEqual(owner, preseed['owner'])

    def test__defaults_permissions_to_0600(self):
        preseed = compose_write_text_file(
            factory.make_name('file'), factory.make_name('content'))
        self.assertEqual('0600', preseed['permissions'])

    def test__obeys_permissions_param(self):
        permissions = 0123
        preseed = compose_write_text_file(
            factory.make_name('file'), factory.make_name('content'),
            permissions=permissions)
        self.assertEqual('0123', preseed['permissions'])
