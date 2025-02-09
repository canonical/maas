# Copyright 2016-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for DHCP snippets forms."""

import random

from django.core.exceptions import ValidationError
from django.http import HttpRequest

from maascommon.events import AUDIT
from maasserver.enum import ENDPOINT_CHOICES
from maasserver.forms.packagerepository import PackageRepositoryForm
from maasserver.models import Event, PackageRepository
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import reload_object


class TestPackageRepositoryForm(MAASServerTestCase):
    def make_valid_repo_params(self, repo=None):
        # Helper that creates a valid PackageRepository and parameters for a
        # PackageRepositoryForm that will validate.
        if repo is None:
            repo = factory.make_PackageRepository()
        name = factory.make_name("name")
        url = factory.make_url(scheme="http")
        arch1 = random.choice(PackageRepository.KNOWN_ARCHES)
        arch2 = random.choice(PackageRepository.KNOWN_ARCHES)
        dist1 = factory.make_name("dist")
        dist2 = factory.make_name("dist")
        pock1 = "updates"
        pock2 = "backports"
        comp1 = "universe"
        comp2 = "multiverse"
        disable_sources = factory.pick_bool()
        enabled = factory.pick_bool()
        params = {
            "name": name,
            "url": url,
            "distributions": [dist1, dist2],
            "disabled_pockets": [pock1, pock2],
            "components": [comp1, comp2],
            "arches": [arch1, arch2],
            "enabled": enabled,
            "disable_sources": disable_sources,
        }
        return params

    def test_creates_package_repository(self):
        repo = factory.make_PackageRepository()
        params = self.make_valid_repo_params(repo)
        form = PackageRepositoryForm(data=params)
        self.assertTrue(form.is_valid(), form.errors)
        request = HttpRequest()
        request.user = factory.make_User()
        endpoint = factory.pick_choice(ENDPOINT_CHOICES)
        package_repository = form.save(endpoint, request)
        for key, value in params.items():
            self.assertEqual(getattr(package_repository, key), value)
        event = Event.objects.get(type__level=AUDIT)
        self.assertIsNotNone(event)
        self.assertEqual(
            event.description,
            "Created package repository '%s'." % package_repository.name,
        )

    def test_create_package_repository_requires_name(self):
        form = PackageRepositoryForm(
            data={"url": factory.make_url(scheme="http")}
        )
        self.assertFalse(form.is_valid())

    def test_create_package_repository_requires_url(self):
        form = PackageRepositoryForm(data={"name": factory.make_name("name")})
        self.assertFalse(form.is_valid())

    def test_default_repository_cannot_be_disabled(self):
        repo = factory.make_PackageRepository(default=True)
        params = self.make_valid_repo_params(repo)
        params["enabled"] = False
        form = PackageRepositoryForm(data=params, instance=repo)
        self.assertFalse(form.is_valid())
        self.assertRaises(ValidationError, form.clean)

    def test_create_package_repository_defaults_to_enabled(self):
        repo = factory.make_PackageRepository()
        params = self.make_valid_repo_params(repo)
        del params["enabled"]
        form = PackageRepositoryForm(data=params)
        self.assertTrue(form.is_valid(), form.errors)
        request = HttpRequest()
        request.user = factory.make_User()
        endpoint = factory.pick_choice(ENDPOINT_CHOICES)
        package_repository = form.save(endpoint, request)
        for key, value in params.items():
            self.assertEqual(getattr(package_repository, key), value)
        self.assertTrue(package_repository.enabled)

    def test_fail_validation_on_create_cleans_url(self):
        PackageRepository.objects.all().delete()
        repo = factory.make_PackageRepository()
        params = self.make_valid_repo_params(repo)
        params["url"] = factory.make_string()
        repo.delete()
        form = PackageRepositoryForm(data=params)
        self.assertFalse(form.is_valid())
        self.assertCountEqual([], PackageRepository.objects.all())

    def test_updates_name(self):
        package_repository = factory.make_PackageRepository()
        name = factory.make_name("name")
        form = PackageRepositoryForm(
            instance=package_repository, data={"name": name}
        )
        self.assertTrue(form.is_valid(), form.errors)
        request = HttpRequest()
        request.user = factory.make_User()
        endpoint = factory.pick_choice(ENDPOINT_CHOICES)
        package_repository = form.save(endpoint, request)
        self.assertEqual(name, package_repository.name)
        event = Event.objects.get(type__level=AUDIT)
        self.assertIsNotNone(event)
        self.assertEqual(
            event.description,
            "Updated package repository '%s'." % (package_repository.name),
        )

    def test_updates_url(self):
        package_repository = factory.make_PackageRepository()
        url = factory.make_url(scheme="http")
        form = PackageRepositoryForm(
            instance=package_repository, data={"url": url}
        )
        self.assertTrue(form.is_valid(), form.errors)
        request = HttpRequest()
        request.user = factory.make_User()
        endpoint = factory.pick_choice(ENDPOINT_CHOICES)
        package_repository = form.save(endpoint, request)
        self.assertEqual(url, package_repository.url)

    def test_updates_enabled(self):
        package_repository = factory.make_PackageRepository()
        enabled = not package_repository.enabled
        form = PackageRepositoryForm(
            instance=package_repository, data={"enabled": enabled}
        )
        self.assertTrue(form.is_valid(), form.errors)
        request = HttpRequest()
        request.user = factory.make_User()
        endpoint = factory.pick_choice(ENDPOINT_CHOICES)
        package_repository = form.save(endpoint, request)
        self.assertEqual(enabled, package_repository.enabled)

    def test_updates_arches(self):
        package_repository = factory.make_PackageRepository()
        arch1 = random.choice(PackageRepository.KNOWN_ARCHES)
        arch2 = random.choice(PackageRepository.KNOWN_ARCHES)
        arch3 = random.choice(PackageRepository.KNOWN_ARCHES)
        form = PackageRepositoryForm(
            instance=package_repository, data={"arches": [arch1, arch2, arch3]}
        )
        self.assertTrue(form.is_valid(), form.errors)
        request = HttpRequest()
        request.user = factory.make_User()
        endpoint = factory.pick_choice(ENDPOINT_CHOICES)
        package_repository = form.save(endpoint, request)
        self.assertEqual([arch1, arch2, arch3], package_repository.arches)

    def test_update_failure_doesnt_delete_url(self):
        package_repository = factory.make_PackageRepository()
        url = package_repository.url
        form = PackageRepositoryForm(
            instance=package_repository,
            data={"url": factory.make_url(scheme="fake")},
        )
        self.assertFalse(form.is_valid())
        self.assertEqual(url, reload_object(package_repository).url)

    def test_creates_package_repository_defaults_main_arches(self):
        repo = factory.make_PackageRepository(arches=[])
        params = self.make_valid_repo_params(repo)
        del params["arches"]
        form = PackageRepositoryForm(data=params)
        self.assertTrue(form.is_valid(), form.errors)
        request = HttpRequest()
        request.user = factory.make_User()
        endpoint = factory.pick_choice(ENDPOINT_CHOICES)
        package_repository = form.save(endpoint, request)
        for key, value in params.items():
            self.assertEqual(getattr(package_repository, key), value)
        self.assertCountEqual(
            package_repository.arches, PackageRepository.MAIN_ARCHES
        )

    def test_default_ports_package_repository_arches(self):
        package_repository = PackageRepository.objects.get(
            name="ports_archive"
        )
        form = PackageRepositoryForm(
            instance=package_repository, data={"arches": []}
        )
        self.assertTrue(form.is_valid(), form.errors)
        request = HttpRequest()
        request.user = factory.make_User()
        endpoint = factory.pick_choice(ENDPOINT_CHOICES)
        package_repository = form.save(endpoint, request)
        self.assertCountEqual(
            package_repository.arches, PackageRepository.PORTS_ARCHES
        )

    def test_arches_validation(self):
        package_repository = factory.make_PackageRepository()
        form = PackageRepositoryForm(
            instance=package_repository, data={"arches": ["i286"]}
        )
        self.assertEqual(
            [
                "'i286' is not a valid architecture. Known architectures: "
                "amd64, arm64, armhf, i386, ppc64el, s390x"
            ],
            form.errors.get("arches"),
        )
        request = HttpRequest()
        request.user = factory.make_User()
        endpoint = factory.pick_choice(ENDPOINT_CHOICES)
        self.assertRaises(ValueError, form.save, endpoint, request)

    def test_arches_comma_cleaning(self):
        package_repository = factory.make_PackageRepository()
        form = PackageRepositoryForm(
            instance=package_repository, data={"arches": ["i386,armhf"]}
        )
        request = HttpRequest()
        request.user = factory.make_User()
        endpoint = factory.pick_choice(ENDPOINT_CHOICES)
        repo = form.save(endpoint, request)
        self.assertCountEqual(["i386", "armhf"], repo.arches)
        form = PackageRepositoryForm(
            instance=package_repository, data={"arches": ["i386, armhf"]}
        )
        repo = form.save(endpoint, request)
        self.assertCountEqual(["i386", "armhf"], repo.arches)
        form = PackageRepositoryForm(
            instance=package_repository, data={"arches": ["i386"]}
        )
        repo = form.save(endpoint, request)
        self.assertCountEqual(["i386"], repo.arches)

    def test_distribution_comma_cleaning(self):
        package_repository = factory.make_PackageRepository()
        form = PackageRepositoryForm(
            instance=package_repository, data={"distributions": ["val1,val2"]}
        )
        request = HttpRequest()
        request.user = factory.make_User()
        endpoint = factory.pick_choice(ENDPOINT_CHOICES)
        repo = form.save(endpoint, request)
        self.assertCountEqual(["val1", "val2"], repo.distributions)
        form = PackageRepositoryForm(
            instance=package_repository, data={"distributions": ["val1, val2"]}
        )
        repo = form.save(endpoint, request)
        self.assertCountEqual(["val1", "val2"], repo.distributions)
        form = PackageRepositoryForm(
            instance=package_repository, data={"distributions": ["val1"]}
        )
        repo = form.save(endpoint, request)
        self.assertEqual(["val1"], repo.distributions)

    def test_disabled_pocket_comma_cleaning(self):
        package_repository = factory.make_PackageRepository()
        form = PackageRepositoryForm(
            instance=package_repository,
            data={"disabled_pockets": ["updates,backports"]},
        )
        request = HttpRequest()
        request.user = factory.make_User()
        endpoint = factory.pick_choice(ENDPOINT_CHOICES)
        repo = form.save(endpoint, request)
        self.assertCountEqual(["updates", "backports"], repo.disabled_pockets)
        form = PackageRepositoryForm(
            instance=package_repository,
            data={"disabled_pockets": ["updates, backports"]},
        )
        repo = form.save(endpoint, request)
        self.assertCountEqual(["updates", "backports"], repo.disabled_pockets)
        form = PackageRepositoryForm(
            instance=package_repository, data={"disabled_pockets": ["updates"]}
        )
        repo = form.save(endpoint, request)
        self.assertEqual(["updates"], repo.disabled_pockets)

    def test_disabled_component_comma_cleaning(self):
        package_repository = factory.make_PackageRepository(
            default=True, components=[]
        )
        form = PackageRepositoryForm(
            instance=package_repository,
            data={"disabled_components": ["universe,multiverse"]},
        )
        request = HttpRequest()
        request.user = factory.make_User()
        endpoint = factory.pick_choice(ENDPOINT_CHOICES)
        repo = form.save(endpoint, request)
        self.assertEqual(["universe", "multiverse"], repo.disabled_components)
        form = PackageRepositoryForm(
            instance=package_repository,
            data={"disabled_components": ["universe, multiverse"]},
        )
        repo = form.save(endpoint, request)
        self.assertEqual(["universe", "multiverse"], repo.disabled_components)
        form = PackageRepositoryForm(
            instance=package_repository,
            data={"disabled_components": ["universe"]},
        )
        repo = form.save(endpoint, request)
        self.assertEqual(["universe"], repo.disabled_components)

    def test_component_comma_cleaning(self):
        package_repository = factory.make_PackageRepository()
        form = PackageRepositoryForm(
            instance=package_repository, data={"components": ["val1,val2"]}
        )
        request = HttpRequest()
        request.user = factory.make_User()
        endpoint = factory.pick_choice(ENDPOINT_CHOICES)
        repo = form.save(endpoint, request)
        self.assertCountEqual(["val1", "val2"], repo.components)
        form = PackageRepositoryForm(
            instance=package_repository, data={"components": ["val1, val2"]}
        )
        repo = form.save(endpoint, request)
        self.assertCountEqual(["val1", "val2"], repo.components)
        form = PackageRepositoryForm(
            instance=package_repository, data={"components": ["val1"]}
        )
        repo = form.save(endpoint, request)
        self.assertCountEqual(["val1"], repo.components)

    def test_updates_disable_sources(self):
        package_repository = factory.make_PackageRepository()
        form = PackageRepositoryForm(
            instance=package_repository, data={"disable_sources": True}
        )
        self.assertTrue(form.is_valid(), form.errors)
        request = HttpRequest()
        request.user = factory.make_User()
        endpoint = factory.pick_choice(ENDPOINT_CHOICES)
        package_repository = form.save(endpoint, request)
        self.assertTrue(package_repository.disable_sources)
        event = Event.objects.get(type__level=AUDIT)
        self.assertIsNotNone(event)
        self.assertEqual(
            event.description,
            "Updated package repository '%s'." % (package_repository.name),
        )
