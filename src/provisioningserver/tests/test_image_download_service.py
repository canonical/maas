# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for src/provisioningserver/image_download_service.py"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from datetime import timedelta

from maastesting.matchers import (
    get_mock_calls,
    MockCalledOnceWith,
    MockNotCalled,
    )
from maastesting.testcase import MAASTestCase
from mock import (
    Mock,
    sentinel,
    )
from provisioningserver import image_download_service
from provisioningserver.image_download_service import (
    PeriodicImageDownloadService,
    )
from provisioningserver.rpc.exceptions import NoConnectionsAvailable
from provisioningserver.tasks import import_boot_images
from twisted.application.internet import TimerService
from twisted.internet import defer
from twisted.internet.task import Clock


class TestPeriodicImageDownloadService(MAASTestCase):

    def test_init(self):
        service = PeriodicImageDownloadService(
            sentinel.service, sentinel.clock, sentinel.uuid)
        self.assertIsInstance(service, TimerService)
        self.assertIs(service.clock, sentinel.clock)
        self.assertIs(service.uuid, sentinel.uuid)
        self.assertIs(service.client_service, sentinel.service)

    def patch_download(self, service, return_value):
        patched = self.patch(service, '_start_download')
        patched.return_value = defer.succeed(return_value)
        return patched

    def test_is_called_every_interval(self):
        clock = Clock()
        service = PeriodicImageDownloadService(
            sentinel.service, clock, sentinel.uuid)
        # Avoid actual downloads:
        self.patch_download(service, None)
        maas_meta_last_modified = self.patch(
            image_download_service, 'maas_meta_last_modified')
        maas_meta_last_modified.return_value = None
        service.startService()

        # The first call is issued at startup.
        self.assertEqual(1, len(get_mock_calls(maas_meta_last_modified)))

        # Wind clock forward one second less than the desired interval.
        clock.advance(service.check_interval - 1)
        # No more periodic calls made.
        self.assertEqual(1, len(get_mock_calls(maas_meta_last_modified)))

        # Wind clock forward one second, past the interval.
        clock.advance(1)

        # Now there were two calls.
        self.assertEqual(2, len(get_mock_calls(maas_meta_last_modified)))

        # Forward another interval, should be three calls.
        clock.advance(service.check_interval)
        self.assertEqual(3, len(get_mock_calls(maas_meta_last_modified)))

    def test_no_download_if_no_meta_file(self):
        clock = Clock()
        service = PeriodicImageDownloadService(
            sentinel.service, clock, sentinel.uuid)
        _start_download = self.patch_download(service, None)
        self.patch(
            image_download_service,
            'maas_meta_last_modified').return_value = None
        service.startService()
        self.assertThat(_start_download, MockNotCalled())

    def test_initiates_download_if_one_week_has_passed(self):
        clock = Clock()
        service = PeriodicImageDownloadService(
            sentinel.service, clock, sentinel.uuid)
        _start_download = self.patch_download(service, None)
        one_week_ago = clock.seconds() - timedelta(weeks=1).total_seconds()
        self.patch(
            image_download_service,
            'maas_meta_last_modified').return_value = one_week_ago
        service.startService()
        self.assertThat(_start_download, MockCalledOnceWith())

    def test_no_download_if_one_week_has_not_passed(self):
        clock = Clock()
        service = PeriodicImageDownloadService(
            sentinel.service, clock, sentinel.uuid)
        _start_download = self.patch_download(service, None)
        one_week = timedelta(weeks=1).total_seconds()
        self.patch(
            image_download_service,
            'maas_meta_last_modified').return_value = clock.seconds()
        clock.advance(one_week - 1)
        service.startService()
        self.assertThat(_start_download, MockNotCalled())

    def test_download_is_initiated_in_new_thread(self):
        clock = Clock()
        maas_meta_last_modified = self.patch(
            image_download_service, 'maas_meta_last_modified')
        one_week = timedelta(weeks=1).total_seconds()
        maas_meta_last_modified.return_value = clock.seconds() - one_week
        rpc_client = Mock()
        client_call = Mock()
        client_call.side_effect = [
            defer.succeed(sentinel.sources),
            defer.succeed(dict(http_proxy=sentinel.http_proxy)),
            ]
        rpc_client.getClient.return_value = client_call

        # We could patch out 'import_boot_images' instead here but I
        # don't do that for 2 reasons:
        # 1. It requires spinning the reactor again before being able to
        # test the result.
        # 2. It means there's no thread to clean up after the test.
        deferToThread = self.patch(image_download_service, 'deferToThread')
        deferToThread.return_value = defer.succeed(None)
        service = PeriodicImageDownloadService(
            rpc_client, clock, sentinel.uuid)
        service.startService()
        self.assertThat(
            deferToThread, MockCalledOnceWith(
                import_boot_images, sentinel.sources, sentinel.http_proxy))

    def test_no_download_if_no_rpc_connections(self):
        rpc_client = Mock()
        failure = NoConnectionsAvailable()
        rpc_client.getClient.return_value.side_effect = failure

        deferToThread = self.patch(image_download_service, 'deferToThread')
        service = PeriodicImageDownloadService(
            rpc_client, Clock(), sentinel.uuid)
        service.startService()
        self.assertThat(deferToThread, MockNotCalled())
