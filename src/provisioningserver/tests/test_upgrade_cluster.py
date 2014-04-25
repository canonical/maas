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
from os import (
    listdir,
    makedirs,
    )
import os.path
from textwrap import dedent

from maastesting.factory import factory
from maastesting.matchers import (
    MockCalledOnceWith,
    MockNotCalled,
    )
from maastesting.testcase import MAASTestCase
from mock import Mock
from provisioningserver import upgrade_cluster
from provisioningserver.config import BootConfig
from provisioningserver.import_images import boot_resources
from provisioningserver.testing.config import (
    BootConfigFixture,
    ConfigFixture,
    )
from testtools.matchers import (
    DirExists,
    FileContains,
    StartsWith,
    )


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

    def patch_boot_config(self, config):
        """Replace the bootresources config with the given fake."""
        fixture = BootConfigFixture(config)
        self.useFixture(fixture)
        path = fixture.filename
        self.patch(upgrade_cluster, 'locate_config').return_value = path
        return path

    def test_hook_does_nothing_if_configure_me_is_False(self):
        self.patch_boot_config({'boot': {'configure_me': False}})
        rewrite_config = self.patch_rewrite_boot_resources_config()
        upgrade_cluster.generate_boot_resources_config()
        self.assertThat(rewrite_config, MockNotCalled())

    def test_hook_does_nothing_if_configure_me_is_missing(self):
        self.patch_boot_config({'boot': {}})
        rewrite_config = self.patch_rewrite_boot_resources_config()
        upgrade_cluster.generate_boot_resources_config()
        self.assertThat(rewrite_config, MockNotCalled())

    def test_hook_rewrites_if_configure_me_is_True(self):
        config_file = self.patch_boot_config({'boot': {'configure_me': True}})
        rewrite_config = self.patch_rewrite_boot_resources_config()
        upgrade_cluster.generate_boot_resources_config()
        self.assertThat(rewrite_config, MockCalledOnceWith(config_file))

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

    def test_generate_selections_returns_None_if_no_images_found(self):
        self.assertIsNone(upgrade_cluster.generate_selections([]))

    def test_generate_selections_matches_image(self):
        arch = factory.make_name('arch')
        subarch = factory.make_name('subarch')
        release = factory.make_name('release')
        self.assertEqual(
            [
                {
                    'release': release,
                    'arches': [arch],
                    'subarches': [subarch],
                },
            ],
            upgrade_cluster.generate_selections([(arch, subarch, release)]))

    def test_generate_selections_sorts_output(self):
        images = [
            (
                factory.make_name('arch'),
                factory.make_name('subarch'),
                factory.make_name('release'),
            )
            for _ in range(3)
            ]
        self.assertEqual(
            upgrade_cluster.generate_selections(sorted(images)),
            upgrade_cluster.generate_selections(sorted(images, reverse=True)))

    def test_generate_updated_config_clears_configure_me_if_no_images(self):
        config = {'boot': {'configure_me': True, 'sources': []}}
        self.assertNotIn(
            'configure_me',
            upgrade_cluster.generate_updated_config(config, None)['boot'])

    def test_generate_updated_config_clears_configure_me_if_has_images(self):
        image = (
            factory.make_name('arch'),
            factory.make_name('subarch'),
            factory.make_name('release'),
            )
        config = {'boot': {'configure_me': True, 'sources': []}}
        self.assertNotIn(
            'configure_me',
            upgrade_cluster.generate_updated_config(config, [image])['boot'])

    def test_generate_updated_config_leaves_static_entries_intact(self):
        storage = factory.make_name('storage')
        path = factory.make_name('path')
        keyring = factory.make_name('keyring')
        config = {
            'boot': {
                'configure_me': True,
                'storage': storage,
                'sources': [
                    {
                        'path': path,
                        'keyring': keyring,
                    },
                    ],
                },
            }
        # Set configure_me; generate_updated_config expects it.
        config['boot']['configure_me'] = True

        result = upgrade_cluster.generate_updated_config(config, [])
        self.assertEqual(storage, result['boot']['storage'])
        self.assertEqual(path, result['boot']['sources'][0]['path'])
        self.assertEqual(keyring, result['boot']['sources'][0]['keyring'])

    def test_generate_updated_config_updates_sources(self):
        arch = factory.make_name('arch')
        subarch = factory.make_name('subarch')
        release = factory.make_name('release')
        path1 = factory.make_name('path')
        path2 = factory.make_name('path')
        config = {
            'boot': {
                'configure_me': True,
                # There are two sources.  Both will have their selections set.
                'sources': [
                    {'path': path1},
                    {'path': path2}
                    ],
                },
            }
        result = upgrade_cluster.generate_updated_config(
            config, [(arch, subarch, release)])
        self.assertEqual(
            [
                {
                    'path': path1,
                    'selections': [
                        {
                            'release': release,
                            'arches': [arch],
                            'subarches': [subarch],
                        },
                        ],
                },
                {
                    'path': path2,
                    'selections': [
                        {
                            'release': release,
                            'arches': [arch],
                            'subarches': [subarch],
                        },
                        ],
                },
            ],
            result['boot']['sources'])

    def test_generate_updated_config_does_not_touch_sources_if_no_images(self):
        path = factory.make_name('path')
        arches = [factory.make_name('arch') for _ in range(2)]
        config = {
            'boot': {
                'configure_me': True,
                'sources': [
                    {
                        'path': path,
                        'selections': [{'arches': arches}],
                    },
                    ],
                },
            }
        no_images = set()
        result = upgrade_cluster.generate_updated_config(config, no_images)
        self.assertEqual(
            [
                {
                    'path': path,
                    'selections': [{'arches': arches}],
                },
            ],
            result['boot']['sources'])

    def test_extract_top_comment_reads_up_to_first_non_comment_text(self):
        header = dedent("""\
            # Comment.

            # Comment after blank line.
                  # Indented comment.
            """)
        filename = self.make_file(contents=(header + 'text#'))
        self.assertEqual(header, upgrade_cluster.extract_top_comment(filename))

    def test_update_config_file_rewrites_file_in_place(self):
        old_storage = factory.make_name('old')
        new_storage = factory.make_name('new')
        original_file = dedent("""\
            # Top comment.
            boot:
              configure_me: True
              storage: %s
            """) % old_storage
        expected_file = dedent("""\
            # Top comment.
            boot:
              storage: %s
            """) % new_storage
        config_file = self.make_file(contents=original_file)

        upgrade_cluster.update_config_file(
            config_file, {'boot': {'storage': new_storage}})

        self.assertThat(config_file, FileContains(expected_file))

    def test_update_config_file_flushes_config_cache(self):
        self.patch(BootConfig, 'flush_cache')
        config_file = self.make_file()
        upgrade_cluster.update_config_file(config_file, {})
        self.assertThat(
            BootConfig.flush_cache, MockCalledOnceWith(config_file))

    def test_rewrite_boot_resources_config_integrates(self):
        tftproot = self.make_dir()
        # Fake pre-existing images in a pre-Simplestreams TFTP directory tree.
        self.useFixture(ConfigFixture({'tftp': {'root': tftproot}}))
        arch = factory.make_name('arch')
        subarch = factory.make_name('subarch')
        release = factory.make_name('release')
        purpose = factory.make_name('purpose')
        makedirs(os.path.join(tftproot, arch, subarch, release, purpose))

        config_file = self.make_file(contents=dedent("""\
            # Boot resources configuration file.
            #
            # Configuration follows.

            boot:
              # This setting will be removed during rewrite.
              configure_me: True

              storage: "/var/lib/maas/boot-resources/"

              sources:
                - path: "http://maas.ubuntu.com/images/somewhere"
                  keyring: "/usr/share/keyrings/ubuntu-cloudimage-keyring.gpg"

                  selections:
                  - release: "trusty"
            """))

        upgrade_cluster.rewrite_boot_resources_config(config_file)

        self.assertThat(
            config_file,
            FileContains(matcher=StartsWith(dedent("""\
                # Boot resources configuration file.
                #
                # Configuration follows.

                boot:
                """))))


class TestMakeMAASOwnBootResources(MAASTestCase):
    """Tests for the `make_maas_own_boot_resources` upgrade."""

    def configure_storage(self, storage_dir):
        """Create a storage config."""
        self.patch(boot_resources, 'read_config').return_value = {
            'boot': {'storage': storage_dir},
            }

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
