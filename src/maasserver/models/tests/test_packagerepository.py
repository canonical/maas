# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

""":class:`PackageRepository` tests."""


from django.core.exceptions import ValidationError

from maasserver.models import PackageRepository
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestPackageRepositoryManager(MAASServerTestCase):
    def test_get_default_archive(self):
        PackageRepository.objects.all().delete()
        arch = "amd64"
        main_url = "http://us.archive.ubuntu.com/ubuntu"
        archive = factory.make_PackageRepository(
            url=main_url, default=True, arches=["i386", "amd64"]
        )
        self.assertEqual(
            archive, PackageRepository.objects.get_default_archive(arch)
        )

    def test_get_additional_repositories(self):
        arch = "amd64"
        main_url = "http://additional.repository/ubuntu"
        archive = factory.make_PackageRepository(
            url=main_url, default=False, arches=["i386", "amd64"]
        )
        self.assertEqual(
            archive,
            PackageRepository.objects.get_additional_repositories(
                arch
            ).first(),
        )

    def test_additional_repositories_can_be_deleted(self):
        main_url = "http://additional.repository/ubuntu"
        archive = factory.make_PackageRepository(
            url=main_url, default=False, arches=["i386", "amd64"]
        )
        archive.delete()
        gone = PackageRepository.objects.get_additional_repositories(
            "amd64"
        ).first()
        self.assertIsNone(gone)

    def test_default_repositories_cannot_be_deleted(self):
        self.assertRaises(
            ValidationError, PackageRepository.get_main_archive().delete
        )
        self.assertRaises(
            ValidationError, PackageRepository.get_ports_archive().delete
        )

    def test_get_multiple_with_a_ppa(self):
        ppa_arch = "armhf"
        ppa_url = "ppa:{}/{}".format(
            factory.make_hostname(),
            factory.make_hostname(),
        )
        ppa_archive = factory.make_PackageRepository(
            url=ppa_url, default=False, arches=[ppa_arch, factory.make_name()]
        )
        arch = "i386"
        url = factory.make_url(scheme="http")
        archive = factory.make_PackageRepository(
            url=url, default=False, arches=[arch, factory.make_name()]
        )
        self.assertEqual(
            ppa_archive,
            PackageRepository.objects.get_additional_repositories(
                ppa_arch
            ).first(),
        )
        self.assertEqual(
            archive,
            PackageRepository.objects.get_additional_repositories(
                arch
            ).first(),
        )

    def test_get_known_architectures(self):
        self.assertEqual(
            PackageRepository.objects.get_known_architectures(),
            PackageRepository.MAIN_ARCHES + PackageRepository.PORTS_ARCHES,
        )

    def test_get_pockets_to_disable(self):
        self.assertEqual(
            PackageRepository.objects.get_pockets_to_disable(),
            PackageRepository.POCKETS_TO_DISABLE,
        )

    def test_get_components_to_disable(self):
        self.assertEqual(
            PackageRepository.objects.get_components_to_disable(),
            PackageRepository.COMPONENTS_TO_DISABLE,
        )
