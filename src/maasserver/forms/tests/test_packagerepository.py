# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for DHCP snippets forms."""

__all__ = []
import random

from django.core.exceptions import ValidationError
from maasserver.forms.packagerepository import PackageRepositoryForm
from maasserver.models import PackageRepository
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import reload_object


class TestPackageRepositoryForm(MAASServerTestCase):

    def make_valid_repo_params(self, repo=None):
        # Helper that creates a valid PackageRepository and parameters for a
        # PackageRepositoryForm that will validate.
        if repo is None:
            repo = factory.make_PackageRepository()
        name = factory.make_name('name')
        url = factory.make_url(scheme='http')
        arch1 = random.choice(PackageRepository.KNOWN_ARCHES)
        arch2 = random.choice(PackageRepository.KNOWN_ARCHES)
        dist1 = factory.make_name('dist')
        dist2 = factory.make_name('dist')
        pock1 = factory.make_name('pock')
        pock2 = factory.make_name('pock')
        comp1 = factory.make_name('comp')
        comp2 = factory.make_name('comp')
        enabled = factory.pick_bool()
        params = {
            'name': name,
            'url': url,
            'distributions': [dist1, dist2],
            'disabled_pockets': [pock1, pock2],
            'components': [comp1, comp2],
            'arches': [arch1, arch2],
            'enabled': enabled,
        }
        return params

    def test__creates_package_repository(self):
        repo = factory.make_PackageRepository()
        params = self.make_valid_repo_params(repo)
        form = PackageRepositoryForm(data=params)
        self.assertTrue(form.is_valid(), form.errors)
        package_repository = form.save()
        self.assertAttributes(package_repository, params)

    def test__create_package_repository_requires_name(self):
        form = PackageRepositoryForm(
            data={'url': factory.make_url(scheme='http')})
        self.assertFalse(form.is_valid())

    def test__create_package_repository_requires_url(self):
        form = PackageRepositoryForm(data={'name': factory.make_name('name')})
        self.assertFalse(form.is_valid())

    def test__default_repository_cannot_be_disabled(self):
        repo = factory.make_PackageRepository(default=True)
        params = self.make_valid_repo_params(repo)
        params['enabled'] = False
        form = PackageRepositoryForm(data=params, instance=repo)
        self.assertFalse(form.is_valid())
        self.assertRaises(ValidationError, form.clean)

    def test__create_package_repository_defaults_to_enabled(self):
        repo = factory.make_PackageRepository()
        params = self.make_valid_repo_params(repo)
        del params['enabled']
        form = PackageRepositoryForm(data=params)
        self.assertTrue(form.is_valid(), form.errors)
        package_repository = form.save()
        self.assertAttributes(package_repository, params)
        self.assertTrue(package_repository.enabled)

    def test__fail_validation_on_create_cleans_url(self):
        PackageRepository.objects.all().delete()
        repo = factory.make_PackageRepository()
        params = self.make_valid_repo_params(repo)
        params['url'] = factory.make_string()
        repo.delete()
        form = PackageRepositoryForm(data=params)
        self.assertFalse(form.is_valid())
        self.assertItemsEqual([], PackageRepository.objects.all())

    def test__updates_name(self):
        package_repository = factory.make_PackageRepository()
        name = factory.make_name('name')
        form = PackageRepositoryForm(
            instance=package_repository, data={'name': name})
        self.assertTrue(form.is_valid(), form.errors)
        package_repository = form.save()
        self.assertEqual(name, package_repository.name)

    def test__updates_url(self):
        package_repository = factory.make_PackageRepository()
        url = factory.make_url(scheme='http')
        form = PackageRepositoryForm(
            instance=package_repository, data={'url': url})
        self.assertTrue(form.is_valid(), form.errors)
        package_repository = form.save()
        self.assertEqual(url, package_repository.url)

    def test__updates_enabled(self):
        package_repository = factory.make_PackageRepository()
        enabled = not package_repository.enabled
        form = PackageRepositoryForm(
            instance=package_repository, data={'enabled': enabled})
        self.assertTrue(form.is_valid(), form.errors)
        package_repository = form.save()
        self.assertEqual(enabled, package_repository.enabled)

    def test__updates_arches(self):
        package_repository = factory.make_PackageRepository()
        arch1 = random.choice(PackageRepository.KNOWN_ARCHES)
        arch2 = random.choice(PackageRepository.KNOWN_ARCHES)
        arch3 = random.choice(PackageRepository.KNOWN_ARCHES)
        form = PackageRepositoryForm(
            instance=package_repository,
            data={'arches': [arch1, arch2, arch3]})
        self.assertTrue(form.is_valid(), form.errors)
        package_repository = form.save()
        self.assertEqual([arch1, arch2, arch3], package_repository.arches)

    def test__update_failure_doesnt_delete_url(self):
        package_repository = factory.make_PackageRepository()
        url = package_repository.url
        form = PackageRepositoryForm(
            instance=package_repository,
            data={
                'url': factory.make_url(scheme='fake'),
            })
        self.assertFalse(form.is_valid())
        self.assertEquals(url, reload_object(package_repository).url)

    def test__creates_package_repository_defaults_main_arches(self):
        repo = factory.make_PackageRepository(arches=[])
        params = self.make_valid_repo_params(repo)
        del params['arches']
        form = PackageRepositoryForm(data=params)
        self.assertTrue(form.is_valid(), form.errors)
        package_repository = form.save()
        self.assertAttributes(package_repository, params)
        self.assertItemsEqual(
            package_repository.arches, PackageRepository.MAIN_ARCHES)

    def test__arches_validation(self):
        package_repository = factory.make_PackageRepository()
        form = PackageRepositoryForm(
            instance=package_repository, data={'arches': ['i286']})
        self.assertEqual(
            ["'i286' is not a valid architecture. Known architectures: "
                'amd64, arm64, armhf, i386, ppc64el'],
            form.errors.get('arches'))
        self.assertRaises(ValueError, form.save)

    def test__arches_comma_cleaning(self):
        package_repository = factory.make_PackageRepository()
        form = PackageRepositoryForm(
            instance=package_repository, data={'arches': ['i386,armhf']})
        repo = form.save()
        self.assertItemsEqual(['i386', 'armhf'], repo.arches)
        form = PackageRepositoryForm(
            instance=package_repository,
            data={'arches': ['i386, armhf']})
        repo = form.save()
        self.assertItemsEqual(['i386', 'armhf'], repo.arches)
        form = PackageRepositoryForm(
            instance=package_repository, data={'arches': ['i386']})
        repo = form.save()
        self.assertItemsEqual(['i386'], repo.arches)

    def test__distribution_comma_cleaning(self):
        package_repository = factory.make_PackageRepository()
        form = PackageRepositoryForm(
            instance=package_repository, data={'distributions': ['val1,val2']})
        repo = form.save()
        self.assertItemsEqual(['val1', 'val2'], repo.distributions)
        form = PackageRepositoryForm(
            instance=package_repository,
            data={'distributions': ['val1, val2']})
        repo = form.save()
        self.assertItemsEqual(['val1', 'val2'], repo.distributions)
        form = PackageRepositoryForm(
            instance=package_repository, data={'distributions': ['val1']})
        repo = form.save()
        self.assertItemsEqual(['val1'], repo.distributions)

    def test__disabled_pocket_comma_cleaning(self):
        package_repository = factory.make_PackageRepository()
        form = PackageRepositoryForm(
            instance=package_repository,
            data={'disabled_pockets': ['val1,val2']})
        repo = form.save()
        self.assertItemsEqual(['val1', 'val2'], repo.disabled_pockets)
        form = PackageRepositoryForm(
            instance=package_repository,
            data={'disabled_pockets': ['val1, val2']})
        repo = form.save()
        self.assertItemsEqual(['val1', 'val2'], repo.disabled_pockets)
        form = PackageRepositoryForm(
            instance=package_repository, data={'disabled_pockets': ['val1']})
        repo = form.save()
        self.assertItemsEqual(['val1'], repo.disabled_pockets)

    def test__component_comma_cleaning(self):
        package_repository = factory.make_PackageRepository()
        form = PackageRepositoryForm(
            instance=package_repository, data={'components': ['val1,val2']})
        repo = form.save()
        self.assertItemsEqual(['val1', 'val2'], repo.components)
        form = PackageRepositoryForm(
            instance=package_repository, data={'components': ['val1, val2']})
        repo = form.save()
        self.assertItemsEqual(['val1', 'val2'], repo.components)
        form = PackageRepositoryForm(
            instance=package_repository, data={'components': ['val1']})
        repo = form.save()
        self.assertItemsEqual(['val1'], repo.components)
