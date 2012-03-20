# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the Avahi export of MAAS."""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from collections import defaultdict

from maastesting.testcase import TestCase

import maasserver.maasavahi
from maasserver.maasavahi import (
    MAASAvahiService,
    setup_maas_avahi_service,
    )
from maasserver.models import (
    Config,
    config_manager,
    )


class MockZeroconfServiceFactory:
    """Factory used to track usage of the zeroconfservice module.

    An instance is meant to be patched as
    maasserver.maasavahi.ZeroconfService. It will register instances
    created, as well as the parameters and methods called on each instance.
    """

    def __init__(self):
        self.instances = []

    def __call__(self, *args, **kwargs):
        mock = MockZeroconfService(*args, **kwargs)
        self.instances.append(mock)
        return mock


class MockZeroconfService:

    def __init__(self, name, port, stype):
        self.name = name
        self.port = port
        self.stype = stype
        self.calls = []

    def publish(self):
        self.calls.append('publish')

    def unpublish(self):
        self.calls.append('unpublish')


class TestMAASAvahiService(TestCase):

    def setup_mock_avahi(self):
        # Unregister other signals from Config, otherwise
        # the one registered in urls.py, will interfere with these tests
        self.patch(
            config_manager, '_config_changed_connections', defaultdict(set))

        mock_avahi = MockZeroconfServiceFactory()
        self.patch(
            maasserver.maasavahi, 'ZeroconfService', mock_avahi)
        return mock_avahi

    def test_publish_exports_name_over_avahi(self):
        mock_avahi = self.setup_mock_avahi()
        service = MAASAvahiService()
        Config.objects.set_config('maas_name', 'My Test')
        service.publish()
        # One ZeroconfService should have been created
        self.assertEquals(1, len(mock_avahi.instances))
        zeroconf = mock_avahi.instances[0]
        self.assertEquals('My Test MAAS Server', zeroconf.name)
        self.assertEquals(80, zeroconf.port)
        self.assertEquals('_maas._tcp', zeroconf.stype)

        # And published.
        self.assertEquals(['publish'], zeroconf.calls)

    def test_publish_twice_unpublishes_first(self):
        mock_avahi = self.setup_mock_avahi()
        service = MAASAvahiService()
        Config.objects.set_config('maas_name', 'My Test')
        service.publish()
        service.publish()

        # Two ZeroconfService should have been created. The first
        # should have been published, and unpublished,
        # while the second one should have one publish call.
        self.assertEquals(2, len(mock_avahi.instances))
        self.assertEquals(
            ['publish', 'unpublish'], mock_avahi.instances[0].calls)
        self.assertEquals(
            ['publish'], mock_avahi.instances[1].calls)

    def test_setup_maas_avahi_service(self):
        mock_avahi = self.setup_mock_avahi()
        Config.objects.set_config('maas_name', 'First Name')
        setup_maas_avahi_service()

        # Name should have been published.
        self.assertEquals(1, len(mock_avahi.instances))
        self.assertEquals(
            'First Name MAAS Server', mock_avahi.instances[0].name)

        Config.objects.set_config('maas_name', 'Second Name')

        # A new publication should have occured.
        self.assertEquals(2, len(mock_avahi.instances))
        self.assertEquals(
            'Second Name MAAS Server', mock_avahi.instances[1].name)
