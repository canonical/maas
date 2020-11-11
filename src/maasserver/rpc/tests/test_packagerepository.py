# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for :py:module:`~maasserver.rpc.configuration`."""


from urllib.parse import urlparse

from maasserver.models import PackageRepository
from maasserver.rpc.packagerepository import get_archive_mirrors
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestGetArchiveMirrors(MAASServerTestCase):
    def test_returns_populated_dict_when_main_and_port_is_set(self):
        PackageRepository.objects.all().delete()
        main_url = factory.make_url(scheme="http")
        ports_url = factory.make_url(scheme="http")
        factory.make_PackageRepository(
            url=main_url, default=True, arches=["i386", "amd64"]
        )
        factory.make_PackageRepository(
            url=ports_url, default=True, arches=["arm64", "armhf", "powerpc"]
        )
        self.assertEqual(
            {"main": urlparse(main_url), "ports": urlparse(ports_url)},
            get_archive_mirrors(),
        )
