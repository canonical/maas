
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


from django.db.models import ProtectedError
from maasserver.models.space import (
    DEFAULT_SPACE_NAME,
    Space,
)
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from testtools.matchers import MatchesStructure
from testtools.testcase import ExpectedException


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
