# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test the behaviour of bootsource signals."""

from django.db import connection
from twisted.internet import reactor

from maasserver import bootsources as bootsources_module
from maasserver.bootsources import cache_boot_sources
from maasserver.models import BootSource
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestBootSourceSignals(MAASServerTestCase):
    """Tests for the `BootSource` model's signals."""

    def test_doesnt_update_on_initial_BootSource_create(self):
        # The way MAAS detects if the BootSource is the initial creation is by
        # looking at its id. Since Postgres always increments the id only the
        # initial BootSource create(default) will have id=1. When running
        # multiple tests the database may be rolled back but Postgres still
        # increments ids as normal. This resets the sequence to 1.
        with connection.cursor() as cursor:
            cursor.execute(
                "ALTER SEQUENCE %s_id_seq RESTART WITH 1"
                % BootSource._meta.db_table
            )
        post_commit_do = self.patch(bootsources_module, "post_commit_do")
        factory.make_BootSource(keyring_data=factory.make_bytes())
        post_commit_do.assert_not_called()

    def test_arranges_for_update_on_BootSource_create(self):
        post_commit_do = self.patch(bootsources_module, "post_commit_do")
        factory.make_BootSource(keyring_data=factory.make_bytes())
        factory.make_BootSource(keyring_data=factory.make_bytes())
        post_commit_do.assert_called_with(
            reactor.callLater, 0, cache_boot_sources
        )

    def test_arranges_for_update_always_when_empty(self):
        # Create then delete a boot source cache to get over initial ignore
        # on create.
        boot_source = factory.make_BootSource(
            keyring_data=factory.make_bytes()
        )
        boot_source.delete()
        post_commit_do = self.patch(bootsources_module, "post_commit_do")
        factory.make_BootSource(keyring_data=factory.make_bytes())
        post_commit_do.assert_called_once_with(
            reactor.callLater, 0, cache_boot_sources
        )

    def test_arranges_for_update_on_BootSource_update(self):
        factory.make_BootSource(keyring_data=factory.make_bytes())
        boot_source = factory.make_BootSource(
            keyring_data=factory.make_bytes()
        )
        post_commit_do = self.patch(bootsources_module, "post_commit_do")
        boot_source.keyring_data = factory.make_bytes()
        boot_source.save()
        post_commit_do.assert_called_once_with(
            reactor.callLater, 0, cache_boot_sources
        )

    def test_arranges_for_update_on_BootSource_delete(self):
        factory.make_BootSource(keyring_data=factory.make_bytes())
        boot_source = factory.make_BootSource(
            keyring_data=factory.make_bytes()
        )
        post_commit_do = self.patch(bootsources_module, "post_commit_do")
        boot_source.delete()
        post_commit_do.assert_called_once_with(
            reactor.callLater, 0, cache_boot_sources
        )
