# Copyright 2013-2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test Role objects."""

from maasserver.models.role import Role
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestRole(MAASServerTestCase):
    """Tests for :class:`Role`."""

    def test_init(self):
        name = factory.make_name('name')
        description = factory.make_name('description')
        role = factory.make_Role(name=name, description=description)
        self.assertEqual(role.name, name)
        self.assertEqual(role.description, description)

    def test_related_users(self):
        user1 = factory.make_User()
        user2 = factory.make_User()
        role = factory.make_Role()
        role.users.add(user1)
        role.users.add(user2)
        self.assertCountEqual(role.users.all(), [user1, user2])

    def test_related_resource_pools(self):
        pool1 = factory.make_ResourcePool()
        pool2 = factory.make_ResourcePool()
        role = factory.make_Role()
        role.resource_pools.add(pool1)
        role.resource_pools.add(pool2)
        self.assertCountEqual(role.resource_pools.all(), [pool1, pool2])

    def test_create_user_adds_it_to_default_role(self):
        user1 = factory.make_User()
        user2 = factory.make_User()
        default_role = Role.objects.get(name='role-default')
        self.assertCountEqual(default_role.users.all(), [user1, user2])
