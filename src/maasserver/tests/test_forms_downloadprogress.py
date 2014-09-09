# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `DownloadProgressForm`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from maasserver.forms import DownloadProgressForm
from maasserver.testing.factory import factory
from maasserver.testing.orm import reload_object
from maasserver.testing.testcase import MAASServerTestCase


class TestDownloadProgressForm(MAASServerTestCase):

    def test_updates_instance(self):
        progress = factory.make_DownloadProgress_incomplete(size=None)
        new_bytes_downloaded = progress.bytes_downloaded + 1
        size = progress.bytes_downloaded + 2
        error = factory.make_string()

        form = DownloadProgressForm(
            data={
                'size': size,
                'bytes_downloaded': new_bytes_downloaded,
                'error': error,
            },
            instance=progress)
        new_progress = form.save()

        progress = reload_object(progress)
        self.assertEqual(progress, new_progress)
        self.assertEqual(size, progress.size)
        self.assertEqual(new_bytes_downloaded, progress.bytes_downloaded)
        self.assertEqual(error, progress.error)

    def test_rejects_unknown_ongoing_download(self):
        form = DownloadProgressForm(
            data={'bytes_downloaded': 1}, instance=None)

        self.assertFalse(form.is_valid())

    def test_get_download_returns_ongoing_download(self):
        progress = factory.make_DownloadProgress_incomplete()

        self.assertEqual(
            progress,
            DownloadProgressForm.get_download(
                progress.nodegroup, progress.filename,
                progress.bytes_downloaded + 1))

    def test_get_download_recognises_start_of_new_download(self):
        nodegroup = factory.make_NodeGroup()
        filename = factory.make_string()
        progress = DownloadProgressForm.get_download(nodegroup, filename, None)
        self.assertIsNotNone(progress)
        self.assertEqual(nodegroup, progress.nodegroup)
        self.assertEqual(filename, progress.filename)
        self.assertIsNone(progress.bytes_downloaded)

    def test_get_download_returns_none_for_unknown_ongoing_download(self):
        self.assertIsNone(
            DownloadProgressForm.get_download(
                factory.make_NodeGroup(), factory.make_string(), 1))
