# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the Package Repositories API."""

__all__ = []

import http.client
import json
import random

from django.core.urlresolvers import reverse
from maasserver.api.packagerepositories import (
    DISPLAYED_PACKAGE_REPOSITORY_FIELDS,
)
from maasserver.models import PackageRepository
from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory
from maasserver.utils.orm import reload_object


class TestPackageRepositoryAPI(APITestCase.ForUser):
    """Tests for /api/2.0/package-repositories/<package-repository>/."""

    @staticmethod
    def get_package_repository_uri(package_repository):
        """Return the Package Repository's URI on the API."""
        return reverse(
            'package_repository_handler', args=[package_repository.id])

    def test_handler_path(self):
        package_repository = factory.make_PackageRepository()
        self.assertEqual(
            '/api/2.0/package-repositories/%s/' % package_repository.id,
            self.get_package_repository_uri(package_repository))

    def test_read_by_id(self):
        package_repository = factory.make_PackageRepository()
        response = self.client.get(
            self.get_package_repository_uri(package_repository))
        self.assertEqual(
            http.client.OK, response.status_code, response.content)
        parsed_package_repository = json.loads(response.content.decode())
        self.assertEqual(
            parsed_package_repository['resource_uri'],
            self.get_package_repository_uri(package_repository))
        del parsed_package_repository['resource_uri']
        self.assertItemsEqual(
            DISPLAYED_PACKAGE_REPOSITORY_FIELDS,
            parsed_package_repository)

    def test_read_by_name(self):
        package_repository = factory.make_PackageRepository()
        uri = '/api/2.0/package-repositories/%s/' % package_repository.name
        response = self.client.get(uri)
        self.assertEqual(
            http.client.OK, response.status_code, response.content)
        parsed_package_repository = json.loads(response.content.decode())
        self.assertEqual(
            parsed_package_repository['resource_uri'],
            self.get_package_repository_uri(package_repository))
        del parsed_package_repository['resource_uri']
        self.assertItemsEqual(
            DISPLAYED_PACKAGE_REPOSITORY_FIELDS,
            parsed_package_repository)

    def test_read_404_when_bad_id(self):
        response = self.client.get(
            reverse(
                'package_repository_handler', args=[random.randint(0, 100)]))
        self.assertEqual(
            http.client.NOT_FOUND, response.status_code, response.content)

    def test_update(self):
        self.become_admin()
        package_repository = factory.make_PackageRepository()
        new_values = {
            'url': factory.make_url(scheme='http'),
            'distributions': [
                factory.make_name("distribution%d" % i) for i in range(3)],
            'disabled_pockets': [
                factory.make_name("disabled_pocket%d" % i) for i in range(1)],
            'components': [factory.make_name("comp%d" % i) for i in range(4)],
            'arches': [
                random.choice(PackageRepository.KNOWN_ARCHES),
                random.choice(PackageRepository.KNOWN_ARCHES),
            ]
        }
        response = self.client.put(
            self.get_package_repository_uri(package_repository), new_values)
        self.assertEqual(
            http.client.OK, response.status_code, response.content)
        package_repository = reload_object(package_repository)
        self.assertAttributes(package_repository, new_values)

    def test_update_admin_only(self):
        package_repository = factory.make_PackageRepository()
        response = self.client.put(
            self.get_package_repository_uri(package_repository),
            {'url': factory.make_url(scheme='http')}
        )
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content)

    def test_delete_deletes_package_repository(self):
        self.become_admin()
        package_repository = factory.make_PackageRepository()
        response = self.client.delete(
            self.get_package_repository_uri(package_repository))
        self.assertEqual(
            http.client.NO_CONTENT, response.status_code, response.content)
        self.assertIsNone(reload_object(package_repository))

    def test_delete_admin_only(self):
        package_repository = factory.make_PackageRepository()
        response = self.client.delete(
            self.get_package_repository_uri(package_repository))
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content)
        self.assertIsNotNone(reload_object(package_repository))

    def test_delete_404_when_invalid_id(self):
        self.become_admin()
        response = self.client.delete(
            reverse(
                'package_repository_handler', args=[random.randint(0, 100)]))
        self.assertEqual(
            http.client.NOT_FOUND, response.status_code, response.content)


class TestPackageRepositoriesAPI(APITestCase.ForUser):
    """Tests for /api/2.0/package-repositories."""

    @staticmethod
    def get_package_repositories_uri():
        """Return the Package Repositories URI on the API."""
        return reverse('package_repositories_handler', args=[])

    def test_handler_path(self):
        self.assertEqual(
            '/api/2.0/package-repositories/',
            self.get_package_repositories_uri())

    def test_read(self):
        for _ in range(3):
            factory.make_PackageRepository()
        response = self.client.get(self.get_package_repositories_uri())

        self.assertEqual(
            http.client.OK, response.status_code, response.content)
        expected_ids = [
            package_repository.id
            for package_repository in PackageRepository.objects.all()
        ]
        result_ids = [
            package_repository['id']
            for package_repository in json.loads(response.content.decode())
        ]
        self.assertItemsEqual(expected_ids, result_ids)

    def test_create(self):
        self.become_admin()
        name = factory.make_name('name')
        url = factory.make_url(scheme='http')
        enabled = factory.pick_bool()
        params = {
            'name': name,
            'url': url,
            'enabled': enabled,
        }
        response = self.client.post(
            self.get_package_repositories_uri(), params)
        parsed_result = json.loads(response.content.decode())
        package_repository = PackageRepository.objects.get(
            id=parsed_result['id'])
        self.assertAttributes(package_repository, params)

    def test_create_admin_only(self):
        response = self.client.post(
            self.get_package_repositories_uri(),
            {'url': factory.make_string()}
        )
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content)
