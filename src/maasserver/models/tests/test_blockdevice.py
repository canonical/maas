# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `BlockDevice`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from maasserver.models import BlockDevice
from maasserver.testing.testcase import MAASServerTestCase
from testtools.matchers import Equals


class TestBlockDevice(MAASServerTestCase):
    """Tests for the `BlockDevice` model."""

    def test_display_size(self):
        sizes = (
            (45, '45.0 bytes'),
            (1000, '1.0 KB'),
            (1000 * 1000, '1.0 MB'),
            (1000 * 1000 * 500, '500.0 MB'),
            (1000 * 1000 * 1000, '1.0 GB'),
            (1000 * 1000 * 1000 * 1000, '1.0 TB'),
            )
        block_device = BlockDevice()
        for (size, display_size) in sizes:
            block_device.size = size
            self.expectThat(
                block_device.display_size(),
                Equals(display_size))
