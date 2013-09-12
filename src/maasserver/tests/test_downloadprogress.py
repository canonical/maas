# Copyright 2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `DownloadProgress`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from random import randint

from django.core.exceptions import ValidationError
from maasserver.models import DownloadProgress
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestDownloadProgress(MAASServerTestCase):

    def test_save_download_progress(self):
        nodegroup = factory.make_node_group()
        filename = factory.make_name('download')
        size = randint(0, 100)
        bytes_downloaded = randint(0, size)
        progress = DownloadProgress(
            nodegroup=nodegroup, filename=filename, size=size,
            bytes_downloaded=bytes_downloaded)

        progress.save()

        reloaded = DownloadProgress.objects.get(nodegroup=nodegroup)
        self.assertEqual(filename, reloaded.filename)
        self.assertEqual(size, reloaded.size)
        self.assertEqual(bytes_downloaded, bytes_downloaded)

    def test_rejects_negative_size(self):
        self.assertRaises(
            ValidationError,
            factory.make_download_progress, size=-1, bytes_downloaded=0)

    def test_rejects_negative_bytes_downloaded(self):
        self.assertRaises(
            ValidationError,
            factory.make_download_progress, bytes_downloaded=-1)

    def test_accepts_zero_bytes_downloaded(self):
        progress = factory.make_download_progress(bytes_downloaded=0)
        self.assertEqual(0, progress.bytes_downloaded)

    def test_accepts_completion(self):
        progress = factory.make_download_progress(
            size=1000, bytes_downloaded=1000)
        self.assertEqual(1000, progress.size)
        self.assertEqual(progress.size, progress.bytes_downloaded)

    def test_rejects_bytes_downloaded_in_excess_of_size(self):
        self.assertRaises(
            ValidationError,
            factory.make_download_progress, size=1000, bytes_downloaded=1001)

    def test_accepts_any_bytes_downloaded_if_size_unknown(self):
        progress = factory.make_download_progress_incomplete(size=None)
        self.assertIsNone(progress.size)
        self.assertGreater(progress.bytes_downloaded, 0)
