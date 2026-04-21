# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test the behaviour of bootsource signals."""

from unittest.mock import call

from twisted.internet import reactor

from maasserver import bootsources as bootsources_module
from maasserver.bootsources import cache_boot_sources
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestBootSourceSignals(MAASServerTestCase):
    """Tests for the `BootSource` model's signals."""

    def test_arranges_for_update_on_BootSource_create(self):
        post_commit_do = self.patch(bootsources_module, "post_commit_do")
        boot_source1 = factory.make_BootSource(
            keyring_data=factory.make_bytes()
        )
        boot_source2 = factory.make_BootSource(
            keyring_data=factory.make_bytes()
        )
        post_commit_do.assert_has_calls(
            [
                call(
                    reactor.callLater, 0, cache_boot_sources, boot_source1.id
                ),
                call(
                    reactor.callLater, 0, cache_boot_sources, boot_source2.id
                ),
            ]
        )

    def test_arranges_for_update_always_when_empty(self):
        post_commit_do = self.patch(bootsources_module, "post_commit_do")
        boot_source = factory.make_BootSource(
            keyring_data=factory.make_bytes()
        )
        post_commit_do.assert_called_once_with(
            reactor.callLater, 0, cache_boot_sources, boot_source.id
        )

    def test_arranges_for_update_on_BootSource_update(self):
        boot_source = factory.make_BootSource(
            keyring_data=factory.make_bytes()
        )
        post_commit_do = self.patch(bootsources_module, "post_commit_do")
        boot_source.keyring_data = factory.make_bytes()
        boot_source.save()
        post_commit_do.assert_called_once_with(
            reactor.callLater, 0, cache_boot_sources, boot_source.id
        )
