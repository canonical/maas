# Copyright 2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.websockets.handlers.resourcepool`"""


from django.core.exceptions import ValidationError
from maasserver.enum import NODE_STATUS
from maasserver.models.resourcepool import ResourcePool
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import reload_object
from maasserver.websockets.base import dehydrate_datetime
from maasserver.websockets.handlers.resourcepool import ResourcePoolHandler


class TestResourcePoolHandler(MAASServerTestCase):

    def test_get(self):
        user = factory.make_User()
        handler = ResourcePoolHandler(user, {})
        pool = factory.make_ResourcePool()
        result = handler.get({"id": pool.id})
        self.assertEqual(
            {'id': pool.id,
             'name': pool.name,
             'description': pool.description,
             'created': dehydrate_datetime(pool.created),
             'updated': dehydrate_datetime(pool.updated),
             'machine_total_count': 0,
             'machine_ready_count': 0},
            result)

    def test_get_machine_count(self):
        user = factory.make_User()
        handler = ResourcePoolHandler(user, {})
        pool = factory.make_ResourcePool()
        factory.make_Machine(pool=pool)
        result = handler.get({"id": pool.id})
        self.assertEqual(1, result['machine_total_count'])

    def test_get_machine_ready_count(self):
        user = factory.make_User()
        handler = ResourcePoolHandler(user, {})
        pool = factory.make_ResourcePool()
        factory.make_Machine(pool=pool, status=NODE_STATUS.NEW)
        factory.make_Machine(pool=pool, status=NODE_STATUS.READY)
        result = handler.get({"id": pool.id})
        self.assertEqual(2, result['machine_total_count'])
        self.assertEqual(1, result['machine_ready_count'])

    def test_list(self):
        user = factory.make_User()
        handler = ResourcePoolHandler(user, {})
        pool = factory.make_ResourcePool()
        returned_pool_names = [
            data['name'] for data in handler.list({})]
        self.assertEqual(['default', pool.name], returned_pool_names)

    def test_create(self):
        handler = ResourcePoolHandler(factory.make_admin(), {})
        user1 = factory.make_User()
        user2 = factory.make_User()
        group1 = factory.make_UserGroup()
        group2 = factory.make_UserGroup()
        result = handler.create(
            {'name': factory.make_name('pool'),
             'description': factory.make_name('description'),
             'users': [{'id': user1.id}, {'id': user2.id}],
             'groups': [{'id': group1.id}, {'id': group2.id}]})
        pool = ResourcePool.objects.get(id=result['id'])
        self.assertCountEqual(pool.users, [user1, user2])
        self.assertCountEqual(pool.groups, [group1, group2])

    def test_create_annotations(self):
        handler = ResourcePoolHandler(factory.make_admin(), {})
        user1 = factory.make_User()
        user2 = factory.make_User()
        group1 = factory.make_UserGroup()
        group2 = factory.make_UserGroup()
        result = handler.create(
            {'name': factory.make_name('pool'),
             'description': factory.make_name('description'),
             'users': [{'id': user1.id}, {'id': user2.id}],
             'groups': [{'id': group1.id}, {'id': group2.id}]})
        self.assertEqual(0, result['machine_total_count'])
        self.assertEqual(0, result['machine_ready_count'])

    def test_delete(self):
        handler = ResourcePoolHandler(factory.make_admin(), {})
        pool = factory.make_ResourcePool()
        handler.delete({"id": pool.id})
        self.assertIsNone(reload_object(pool))

    def test_delete_not_admin(self):
        handler = ResourcePoolHandler(factory.make_User(), {})
        pool = factory.make_ResourcePool()
        self.assertRaises(AssertionError, handler.delete, {"id": pool.id})

    def test_delete_default_fails(self):
        pool = ResourcePool.objects.get_default_resource_pool()
        handler = ResourcePoolHandler(factory.make_admin(), {})
        self.assertRaises(ValidationError, handler.delete, {"id": pool.id})
