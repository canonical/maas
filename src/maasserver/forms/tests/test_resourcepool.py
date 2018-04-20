# Copyright 2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `ResourcePoolForm`."""

__all__ = []

from maasserver.forms import ResourcePoolForm
from maasserver.models import ResourcePool
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import reload_object


class TestResourcePost(MAASServerTestCase):
    """Tests for `ResourcePoolForm`."""

    def test_creates_pool(self):
        name = factory.make_name('pool')
        description = factory.make_string()
        form = ResourcePoolForm(
            data={'name': name, 'description': description})
        form.save()
        pool = ResourcePool.objects.get(name=name)
        self.assertIsNotNone(pool)
        self.assertEqual(pool.description, description)

    def test_creates_pool_users_groups(self):
        user1 = factory.make_User()
        user2 = factory.make_User()
        group1 = factory.make_UserGroup()
        group2 = factory.make_UserGroup()
        data = {
            'name': factory.make_name('pool'),
            'users': [user1.id, user2.id],
            'groups': [group1.id, group2.id]}
        form = ResourcePoolForm(data=data)
        pool = form.save()
        self.assertCountEqual(pool.users, [user1, user2])
        self.assertCountEqual(pool.groups, [group1, group2])

    def test_updates_pool(self):
        pool = factory.make_ResourcePool()
        new_description = factory.make_string()
        form = ResourcePoolForm(
            data={'description': new_description}, instance=pool)
        form.save()
        pool = reload_object(pool)
        self.assertEqual(pool.description, new_description)

    def test_updates_pool_users_groups(self):
        user1 = factory.make_User()
        user2 = factory.make_User()
        user3 = factory.make_User()
        group1 = factory.make_UserGroup()
        group2 = factory.make_UserGroup()
        group3 = factory.make_UserGroup()
        pool = factory.make_ResourcePool(
            users=[user1, user2], groups=[group1, group2])
        data = {
            'users': [user1.id, user3.id],
            'groups': [group1.id, group3.id]}
        form = ResourcePoolForm(data=data, instance=pool)
        pool = form.save()
        self.assertCountEqual(pool.users, [user1, user3])
        self.assertCountEqual(pool.groups, [group1, group3])

    def test_renames_pool(self):
        pool = factory.make_ResourcePool()
        new_name = factory.make_name('pool')
        form = ResourcePoolForm(data={'name': new_name}, instance=pool)
        form.save()
        pool = reload_object(pool)
        self.assertEqual(pool.name, new_name)
