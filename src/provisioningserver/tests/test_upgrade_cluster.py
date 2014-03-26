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
from os import makedirs
import os.path

from maastesting.factory import factory
from maastesting.matchers import (
    MockCalledOnceWith,
    MockNotCalled,
    )
from maastesting.testcase import MAASTestCase
from mock import (
    ANY,
    Mock,
    )
from provisioningserver import upgrade_cluster
from provisioningserver.config import Config


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


class TestGenerateBootResourcesConfig(MAASTestCase):
    """Tests for the `generate_boot_resources_config` upgrade."""

    def patch_rewrite_boot_resources_config(self):
        """Patch `rewrite_boot_resources_config` with a mock."""
        return self.patch(upgrade_cluster, 'rewrite_boot_resources_config')

    def patch_config(self, config):
        """Patch the `bootresources.yaml` config with a given dict."""
        original_load = Config.load_from_cache

        @classmethod
        def fake_config_load(cls, filename=None):
            """Fake `Config.load_from_cache`.

            Returns a susbtitute for `bootresources.yaml`, but defers to the
            original implementation for other files.  This means we can still
            patch the original, and it means we'll probably get a tell-tale
            error if any code underneath the tests accidentally tries to
            load pserv.yaml.
            """
            if os.path.basename(filename) == 'bootresources.yaml':
                return config
            else:
                return original_load(Config, filename=filename)

        self.patch(Config, 'load_from_cache', fake_config_load)

    def test_hook_does_nothing_if_configure_me_is_False(self):
        self.patch_config({'boot': {'configure_me': False}})
        rewrite_config = self.patch_rewrite_boot_resources_config()
        upgrade_cluster.generate_boot_resources_config()
        self.assertThat(rewrite_config, MockNotCalled())

    def test_hook_does_nothing_if_configure_me_is_missing(self):
        self.patch_config({'boot': {}})
        rewrite_config = self.patch_rewrite_boot_resources_config()
        upgrade_cluster.generate_boot_resources_config()
        self.assertThat(rewrite_config, MockNotCalled())

    def test_hook_rewrites_if_configure_me_is_True(self):
        self.patch_config({'boot': {'configure_me': True}})
        rewrite_config = self.patch_rewrite_boot_resources_config()
        upgrade_cluster.generate_boot_resources_config()
        self.assertThat(rewrite_config, MockCalledOnceWith(ANY))

    def test_find_old_imports_returns_empty_if_no_tftproot(self):
        non_dir = os.path.join(self.make_dir(), factory.make_name('nonesuch'))
        self.assertEqual(set(), upgrade_cluster.find_old_imports(non_dir))

    def test_find_old_imports_returns_empty_if_tftproot_is_empty(self):
        self.assertEqual(
            set(),
            upgrade_cluster.find_old_imports(self.make_dir()))

    def test_find_old_imports_finds_image(self):
        tftproot = self.make_dir()
        arch = factory.make_name('arch')
        subarch = factory.make_name('subarch')
        release = factory.make_name('release')
        purpose = factory.make_name('purpose')
        makedirs(os.path.join(tftproot, arch, subarch, release, purpose))
        self.assertEqual(
            {(arch, subarch, release)},
            upgrade_cluster.find_old_imports(tftproot))
