# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the `upgrade-cluster` command."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from argparse import ArgumentParser
from os import listdir
import os.path

from maastesting.factory import factory
from maastesting.matchers import (
    MockCalledOnceWith,
    MockNotCalled,
    )
from maastesting.testcase import MAASTestCase
from mock import Mock
from provisioningserver import (
    config,
    upgrade_cluster,
    )
from testtools.matchers import DirExists


class TestUpgradeCluster(MAASTestCase):
    """Tests for the `upgrade-cluster` command itself."""

    def run_command(self):
        parser = ArgumentParser()
        upgrade_cluster.add_arguments(parser)
        upgrade_cluster.run(parser.parse_args(()))

    def patch_upgrade_hooks(self, hooks=None):
        """Temporarily replace the upgrade hooks."""
        if hooks is None:
            hooks = []
        self.patch(upgrade_cluster, 'UPGRADE_HOOKS', hooks)

    def test_calls_hooks(self):
        upgrade_hook = Mock()
        self.patch_upgrade_hooks([upgrade_hook])
        self.run_command()
        self.assertThat(upgrade_hook, MockCalledOnceWith())

    def test_calls_hooks_in_order(self):
        calls = []

        # Define some hooks.  They will be run in the order in which they are
        # listed (not in the order in which they are defined, or alphabetical
        # order, or any other order).

        def last_hook():
            calls.append('last')

        def first_hook():
            calls.append('first')

        def middle_hook():
            calls.append('middle')

        self.patch_upgrade_hooks([first_hook, middle_hook, last_hook])
        self.run_command()
        self.assertEqual(['first', 'middle', 'last'], calls)


class TestMakeMAASOwnBootResources(MAASTestCase):
    """Tests for the `make_maas_own_boot_resources` upgrade."""

    def configure_storage(self, storage_dir):
        """Create a storage config."""
        self.patch(config, 'BOOT_RESOURCES_STORAGE', storage_dir)

    def test__calls_chown_if_boot_resources_dir_exists(self):
        self.patch(upgrade_cluster, 'check_call')
        storage_dir = self.make_dir()
        self.configure_storage(storage_dir)
        upgrade_cluster.make_maas_own_boot_resources()
        self.assertThat(
            upgrade_cluster.check_call,
            MockCalledOnceWith(['chown', '-R', 'maas', storage_dir]))

    def test__skips_chown_if_boot_resources_dir_does_not_exist(self):
        self.patch(upgrade_cluster, 'check_call')
        storage_dir = os.path.join(self.make_dir(), factory.make_name('none'))
        self.configure_storage(storage_dir)
        upgrade_cluster.make_maas_own_boot_resources()
        self.assertThat(upgrade_cluster.check_call, MockNotCalled())


class TestCreateGNUPGHome(MAASTestCase):
    """Tests for `create_gnupg_home`."""

    def make_nonexistent_path(self, parent_dir):
        """Return an as-yet nonexistent path, inside `parent_dir`."""
        return os.path.join(parent_dir, factory.make_name('gpghome'))

    def patch_gnupg_home(self, gpghome):
        self.patch(upgrade_cluster, 'MAAS_USER_GPGHOME', gpghome)

    def patch_call(self):
        return self.patch(upgrade_cluster, 'check_call')

    def test__succeeds_if_directory_exists(self):
        existing_home = self.make_dir()
        self.patch_gnupg_home(existing_home)
        self.patch_call()
        upgrade_cluster.create_gnupg_home()
        self.assertEqual([], listdir(existing_home))

    def test__creates_directory(self):
        parent = self.make_dir()
        new_home = self.make_nonexistent_path(parent)
        self.patch_gnupg_home(new_home)
        self.patch_call()
        upgrade_cluster.create_gnupg_home()
        self.assertThat(new_home, DirExists())

    def test__sets_ownership_to_maas(self):
        parent = self.make_dir()
        new_home = self.make_nonexistent_path(parent)
        self.patch_gnupg_home(new_home)
        call = self.patch_call()
        upgrade_cluster.create_gnupg_home()
        self.assertThat(
            call, MockCalledOnceWith(['chown', 'maas:maas', new_home]))
