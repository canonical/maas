
# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the Space model."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []


from django.core.exceptions import PermissionDenied
from django.db.models import ProtectedError
from maasserver.enum import NODE_PERMISSION
from maasserver.models.space import (
    DEFAULT_SPACE_NAME,
    Space,
)
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from testtools.matchers import MatchesStructure
from testtools.testcase import ExpectedException


class TestSpaceManagerGetSpaceOr404(MAASServerTestCase):

    def test__user_view_returns_space(self):
        user = factory.make_User()
        space = factory.make_Space()
        self.assertEquals(
            space,
            Space.objects.get_space_or_404(
                space.id, user, NODE_PERMISSION.VIEW))

    def test__user_edit_raises_PermissionError(self):
        user = factory.make_User()
        space = factory.make_Space()
        self.assertRaises(
            PermissionDenied,
            Space.objects.get_space_or_404,
            space.id, user, NODE_PERMISSION.EDIT)

    def test__user_admin_raises_PermissionError(self):
        user = factory.make_User()
        space = factory.make_Space()
        self.assertRaises(
            PermissionDenied,
            Space.objects.get_space_or_404,
            space.id, user, NODE_PERMISSION.ADMIN)

    def test__admin_view_returns_space(self):
        admin = factory.make_admin()
        space = factory.make_Space()
        self.assertEquals(
            space,
            Space.objects.get_space_or_404(
                space.id, admin, NODE_PERMISSION.VIEW))

    def test__admin_edit_returns_space(self):
        admin = factory.make_admin()
        space = factory.make_Space()
        self.assertEquals(
            space,
            Space.objects.get_space_or_404(
                space.id, admin, NODE_PERMISSION.EDIT))

    def test__admin_admin_returns_space(self):
        admin = factory.make_admin()
        space = factory.make_Space()
        self.assertEquals(
            space,
            Space.objects.get_space_or_404(
                space.id, admin, NODE_PERMISSION.ADMIN))


class SpaceTest(MAASServerTestCase):

    def test_creates_space(self):
        name = factory.make_name('name')
        space = Space(name=name)
        space.save()
        space_from_db = Space.objects.get(name=name)
        self.assertThat(space_from_db, MatchesStructure.byEquality(
            name=name))

    def test_get_default_space_creates_default_space(self):
        default_space = Space.objects.get_default_space()
        self.assertThat(default_space, MatchesStructure.byEquality(
            id=0, name=DEFAULT_SPACE_NAME))

    def test_get_default_space_is_idempotent(self):
        default_space = Space.objects.get_default_space()
        default_space2 = Space.objects.get_default_space()
        self.assertEqual(default_space.id, default_space2.id)

    def test_is_default_detects_default_space(self):
        default_space = Space.objects.get_default_space()
        self.assertTrue(default_space.is_default())

    def test_is_default_detects_non_default_space(self):
        name = factory.make_name('name')
        space = factory.make_Space(name=name)
        self.assertFalse(space.is_default())

    def test_can_be_deleted_if_does_not_contain_subnets(self):
        name = factory.make_name('name')
        space = factory.make_Space(name=name)
        space.delete()
        self.assertItemsEqual([], Space.objects.filter(name=name))

    def test_cant_be_deleted_if_contains_subnet(self):
        space = factory.make_Space()
        factory.make_Subnet(space=space)
        with ExpectedException(ProtectedError):
            space.delete()
