# Copyright 2016-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.websockets.handlers.packagerepository`"""


from maascommon.events import AUDIT
from maasserver.models import Event, PackageRepository
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

    def dehydrate(self, package_repository):
        return {
            "id": package_repository.id,
            "name": package_repository.name,
            "url": package_repository.url,
            "distributions": package_repository.distributions,
            "disabled_pockets": package_repository.disabled_pockets,
            "disabled_components": package_repository.disabled_components,
            "disable_sources": package_repository.disable_sources,
            "components": package_repository.components,
            "arches": package_repository.arches,
            "key": package_repository.key,
            "default": package_repository.default,
            "enabled": package_repository.enabled,
            "updated": dehydrate_datetime(package_repository.updated),
            "created": dehydrate_datetime(package_repository.created),
        }

    def test_list(self):
        PackageRepository.objects.all().delete()
        user = factory.make_User()
        handler = PackageRepositoryHandler(user, {}, None)
        expected_package_repositories = [
            self.dehydrate(factory.make_PackageRepository()) for _ in range(3)
        ]
        self.assertCountEqual(expected_package_repositories, handler.list({}))

    def test_create_is_admin_only(self):
        user = factory.make_User()
        handler = PackageRepositoryHandler(user, {}, None)
        self.assertRaises(HandlerPermissionError, handler.create, {})

    def test_create(self):
        user = factory.make_admin()
        handler = PackageRepositoryHandler(user, {}, None)
        package_repository_name = factory.make_name("package_repository_name")
        handler.create(
            {
                "name": package_repository_name,
                "url": factory.make_url(scheme="http"),
            }
        )
        self.assertIsNotNone(
            PackageRepository.objects.get(name=package_repository_name)
        )
        event = Event.objects.get(type__level=AUDIT)
        self.assertIsNotNone(event)
        self.assertEqual(
            event.description,
            "Created package repository '%s'." % package_repository_name,
        )

    def test_update_is_admin_only(self):
        user = factory.make_User()
        handler = PackageRepositoryHandler(user, {}, None)
        self.assertRaises(HandlerPermissionError, handler.update, {})

    def test_update(self):
        user = factory.make_admin()
        handler = PackageRepositoryHandler(user, {}, None)
        package_repository = factory.make_PackageRepository()
        url = factory.make_url(scheme="http")
        handler.update({"id": package_repository.id, "url": url})
        package_repository = reload_object(package_repository)
        self.assertEqual(url, package_repository.url)
        event = Event.objects.get(type__level=AUDIT)
        self.assertIsNotNone(event)
        self.assertEqual(
            event.description,
            "Updated package repository '%s'." % package_repository.name,
        )

    def test_delete_is_admin_only(self):
        user = factory.make_User()
        handler = PackageRepositoryHandler(user, {}, None)
        self.assertRaises(HandlerPermissionError, handler.delete, {})

    def test_delete(self):
        user = factory.make_admin()
        handler = PackageRepositoryHandler(user, {}, None)
        package_repository = factory.make_PackageRepository()
        handler.delete({"id": package_repository.id})
        self.assertRaises(
            PackageRepository.DoesNotExist,
            PackageRepository.objects.get,
            id=package_repository.id,
        )
