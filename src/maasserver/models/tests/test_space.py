
# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the Space model."""

__all__ = []


from django.core.exceptions import (
    PermissionDenied,
    ValidationError,
)
from django.db.models import ProtectedError
from django.db.utils import IntegrityError
from maasserver.enum import NODE_PERMISSION
from maasserver.models.space import (
    DEFAULT_SPACE_NAME,
    Space,
)
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maastesting.matchers import MockCalledOnce
from testtools.matchers import MatchesStructure
from testtools.testcase import ExpectedException


class TestSpaceManagerGetSpaceOr404(MAASServerTestCase):

    def test__user_view_returns_space(self):
        user = factory.make_User()
        space = factory.make_Space()
        self.assertEqual(
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
        self.assertEqual(
            space,
            Space.objects.get_space_or_404(
                space.id, admin, NODE_PERMISSION.VIEW))

    def test__admin_edit_returns_space(self):
        admin = factory.make_admin()
        space = factory.make_Space()
        self.assertEqual(
            space,
            Space.objects.get_space_or_404(
                space.id, admin, NODE_PERMISSION.EDIT))

    def test__admin_admin_returns_space(self):
        admin = factory.make_admin()
        space = factory.make_Space()
        self.assertEqual(
            space,
            Space.objects.get_space_or_404(
                space.id, admin, NODE_PERMISSION.ADMIN))


class TestSpaceManager(MAASServerTestCase):

    def test__default_specifier_matches_id(self):
        factory.make_Space()
        space = factory.make_Space()
        factory.make_Space()
        id = space.id
        self.assertItemsEqual(
            Space.objects.filter_by_specifiers('%s' % id),
            [space]
        )

    def test__default_specifier_matches_name_with_id(self):
        factory.make_Space()
        space = factory.make_Space()
        factory.make_Space()
        id = space.id
        self.assertItemsEqual(
            Space.objects.filter_by_specifiers('space-%s' % id),
            [space]
        )

    def test__default_specifier_matches_name(self):
        factory.make_Space()
        space = factory.make_Space(name='infinite-improbability')
        factory.make_Space()
        self.assertItemsEqual(
            Space.objects.filter_by_specifiers('infinite-improbability'),
            [space]
        )

    def test__name_specifier_matches_name(self):
        factory.make_Space()
        space = factory.make_Space(name='infinite-improbability')
        factory.make_Space()
        self.assertItemsEqual(
            Space.objects.filter_by_specifiers('name:infinite-improbability'),
            [space]
        )

    def test__class_specifier_matches_attached_subnet(self):
        factory.make_Space()
        space = factory.make_Space()
        subnet = factory.make_Subnet(space=space)
        factory.make_Space()
        self.assertItemsEqual(
            Space.objects.filter_by_specifiers('subnet:%s' % subnet.id),
            [space]
        )


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
        self.assertEqual(0, default_space.id)
        self.assertEqual(DEFAULT_SPACE_NAME, default_space.get_name())
        self.assertEqual(DEFAULT_SPACE_NAME, default_space.name)

    def test_get_default_space_handles_exception(self):
        default_space = Space.objects.get_default_space()
        func = self.patch(Space.objects, "get_or_create")
        func.side_effect = IntegrityError(
            'duplicate key value violates unique constraint '
            '"maasserver_space_pkey"')
        space = Space.objects.get_default_space()
        self.assertThat(func, MockCalledOnce())
        self.assertEqual(default_space.id, space.id)

    def test_invalid_name_raises_exception(self):
        self.assertRaises(
            ValidationError,
            factory.make_Space,
            name='invalid*name')

    def test_reserved_name_raises_exception(self):
        self.assertRaises(
            ValidationError,
            factory.make_Space,
            name='space-1999')

    def test_create_sets_name(self):
        space = Space.objects.create(name=None)
        self.assertEqual("space-%d" % space.id, space.name)

    def test_create_does_not_override_name(self):
        name = factory.make_name()
        space = factory.make_Space(name=name)
        self.assertEqual(name, space.name)

    def test_nonreserved_name_does_not_raise_exception(self):
        space = factory.make_Space(name='myspace-1999')
        self.assertEqual("myspace-1999", space.name)

    def test_rejects_names_with_blanks(self):
        self.assertRaises(
            ValidationError,
            factory.make_Space,
            name=factory.make_name("Space "))

    def test_rejects_duplicate_names(self):
        space1 = factory.make_Space()
        self.assertRaises(
            ValidationError,
            factory.make_Space,
            name=space1.name)

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
