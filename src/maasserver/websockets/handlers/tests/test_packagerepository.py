# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.websockets.handlers.packagerepository`"""

__all__ = []

import maasserver.forms.packagerepository as forms_packagerepository_module
from maasserver.models import PackageRepository
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import reload_object
from maasserver.websockets.base import (
    dehydrate_datetime,
    HandlerPermissionError,
)
from maasserver.websockets.handlers.packagerepository import (
    PackageRepositoryHandler,
)


class TestPackageRepositoryHandler(MAASServerTestCase):

    def setUp(self):
        super().setUp()
        self.patch(
            forms_packagerepository_module,
            'validate_dhcp_config').return_value = []

    def dehydrate(self, package_repository):
        return {
            'id': package_repository.id,
            'name': package_repository.name,
            'url': package_repository.url,
            'distributions': package_repository.distributions,
            'disabled_pockets': package_repository.disabled_pockets,
            'disabled_components': package_repository.disabled_components,
            'components': package_repository.components,
            'arches': package_repository.arches,
            'key': package_repository.key,
            'default': package_repository.default,
            'enabled': package_repository.enabled,
            'updated': dehydrate_datetime(package_repository.updated),
            'created': dehydrate_datetime(package_repository.created),
        }

    def test_list(self):
        PackageRepository.objects.all().delete()
        user = factory.make_User()
        handler = PackageRepositoryHandler(user, {})
        expected_package_repositories = [
            self.dehydrate(factory.make_PackageRepository())
            for _ in range(3)
        ]
        self.assertItemsEqual(expected_package_repositories, handler.list({}))

    def test_create_is_admin_only(self):
        user = factory.make_User()
        handler = PackageRepositoryHandler(user, {})
        self.assertRaises(
            HandlerPermissionError,
            handler.create, {})

    def test_create(self):
        user = factory.make_admin()
        handler = PackageRepositoryHandler(user, {})
        package_repository_name = factory.make_name('package_repository_name')
        handler.create({
            'name': package_repository_name,
            'url': factory.make_url(scheme='http'),
        })
        self.assertIsNotNone(
            PackageRepository.objects.get(name=package_repository_name))

    def test_update_is_admin_only(self):
        user = factory.make_User()
        handler = PackageRepositoryHandler(user, {})
        self.assertRaises(
            HandlerPermissionError,
            handler.update, {})

    def test_update(self):
        user = factory.make_admin()
        handler = PackageRepositoryHandler(user, {})
        package_repository = factory.make_PackageRepository()
        url = factory.make_url(scheme='http')
        handler.update({
            'id': package_repository.id,
            'url': url
        })
        package_repository = reload_object(package_repository)
        self.assertEquals(url, package_repository.url)

    def test_delete_is_admin_only(self):
        user = factory.make_User()
        handler = PackageRepositoryHandler(user, {})
        self.assertRaises(
            HandlerPermissionError,
            handler.delete, {})

    def test_delete(self):
        user = factory.make_admin()
        handler = PackageRepositoryHandler(user, {})
        package_repository = factory.make_PackageRepository()
        handler.delete({'id': package_repository.id})
        self.assertRaises(
            PackageRepository.DoesNotExist,
            PackageRepository.objects.get, id=package_repository.id)
