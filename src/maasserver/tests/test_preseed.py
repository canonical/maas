# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test preseed module."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from maasserver.preseed import (
    get_preseed_filenames,
    split_subarch,
    )
from maasserver.testing.factory import factory
from maasserver.testing.testcase import TestCase


class TestPreseedUtilities(TestCase):

    def test_split_subarch_returns_list(self):
        self.assertEqual(['amd64'], split_subarch('amd64'))

    def test_split_subarch_splits_sub_architecture(self):
        self.assertEqual(['amd64', 'test'], split_subarch('amd64/test'))

    def test_get_preseed_filenames_returns_filenames(self):
        hostname = factory.getRandomString()
        type = factory.getRandomString()
        release = factory.getRandomString()
        node = factory.make_node(hostname=hostname)
        self.assertSequenceEqual(
            [
                '%s_%s_%s_%s' % (type, node.architecture, release, hostname),
                '%s_%s_%s' % (type, node.architecture, release),
                '%s_%s' % (type, node.architecture),
                '%s' % type,
                'generic',
            ],
            list(get_preseed_filenames(node, type, release)))

    def test_get_preseed_filenames_returns_filenames_with_subarch(self):
        arch = factory.getRandomString()
        subarch = factory.getRandomString()
        fake_arch = '%s/%s' % (arch, subarch)
        hostname = factory.getRandomString()
        type = factory.getRandomString()
        release = factory.getRandomString()
        node = factory.make_node(hostname=hostname)
        # Set an architecture of the form '%s/%s' i.e. with a
        # sub-architecture.
        node.architecture = fake_arch
        self.assertSequenceEqual(
            [
                '%s_%s_%s_%s_%s' % (type, arch, subarch, release, hostname),
                '%s_%s_%s_%s' % (type, arch, subarch, release),
                '%s_%s_%s' % (type, arch, subarch),
                '%s_%s' % (type, arch),
                '%s' % type,
                'generic',
            ],
            list(get_preseed_filenames(node, type, release)))
