# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

""":class:`PackageRepository` tests."""

__all__ = []

from maasserver.models import PackageRepository
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestPackageRepositoryManager(MAASServerTestCase):

    def test_get_default_archive(self):
        arch = 'amd64'
        main_url = 'http://us.archive.ubuntu.com/ubuntu'
        archive = factory.make_PackageRepository(
            url=main_url, default=True, arches=['i386', 'amd64'])
        self.assertEquals(
            archive,
            PackageRepository.objects.get_default_archive(arch))

    def test_get_additional_repositories(self):
        arch = 'amd64'
        main_url = 'http://additional.repository/ubuntu'
        archive = factory.make_PackageRepository(
            url=main_url, default=False, arches=['i386', 'amd64'])
        self.assertEquals(
            archive,
            PackageRepository.objects.get_additional_repositories(
                arch).first())
