# Copyright 2014-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the `upgrade-cluster` command."""


from argparse import ArgumentParser
from itertools import product
import os
import os.path
from unittest.mock import Mock

from testtools.matchers import DirExists, FileExists, Not

from maastesting.factory import factory
from maastesting.matchers import (
    FileContains,
    MockCalledOnceWith,
    MockNotCalled,
)
from maastesting.testcase import MAASTestCase
from maastesting.utils import sample_binary_data
from provisioningserver import upgrade_cluster
from provisioningserver.boot import BootMethodRegistry
from provisioningserver.boot.tftppath import list_subdirs
from provisioningserver.config import ClusterConfiguration
from provisioningserver.testing.config import ClusterConfigurationFixture
from provisioningserver.utils import snappy
from provisioningserver.utils.fs import read_text_file


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
        self.patch(upgrade_cluster, "UPGRADE_HOOKS", hooks)

    def test_calls_hooks(self):
        upgrade_hook = Mock()
        upgrade_hook.__name__ = "upgrade_hook"
        self.patch_upgrade_hooks([upgrade_hook])
        self.run_command()
        with ClusterConfiguration.open() as config:
            self.assertThat(upgrade_hook, MockCalledOnceWith(config.tftp_root))

    def test_calls_hooks_in_order(self):
        calls = []

        # Define some hooks.  They will be run in the order in which they are
        # listed (not in the order in which they are defined, or alphabetical
        # order, or any other order).

        def last_hook(tftp_root=None):
            calls.append("last")

        def first_hook(tftp_root=None):
            calls.append("first")

        def middle_hook(tftp_root=None):
            calls.append("middle")

        self.patch_upgrade_hooks([first_hook, middle_hook, last_hook])
        self.run_command()
        self.assertEqual(["first", "middle", "last"], calls)


class TestMakeMAASOwnBootResources(MAASTestCase):
    """Tests for the `make_maas_own_boot_resources` upgrade."""

    def configure_storage(self, storage_dir):
        """Create a storage config."""
        self.useFixture(ClusterConfigurationFixture(tftp_root=storage_dir))

    def test_calls_chown_if_boot_resources_dir_exists(self):
        self.patch(upgrade_cluster, "check_call")
        storage_dir = self.make_dir()
        self.configure_storage(storage_dir)
        upgrade_cluster.make_maas_own_boot_resources(storage_dir)
        self.assertThat(
            upgrade_cluster.check_call,
            MockCalledOnceWith(["chown", "-R", "maas", storage_dir]),
        )

    def test_skips_chown_if_boot_resources_dir_does_not_exist(self):
        self.patch(upgrade_cluster, "check_call")
        storage_dir = os.path.join(self.make_dir(), factory.make_name("none"))
        os.mkdir(storage_dir)
        self.configure_storage(storage_dir)
        os.rmdir(storage_dir)
        upgrade_cluster.make_maas_own_boot_resources(storage_dir)
        self.assertThat(upgrade_cluster.check_call, MockNotCalled())


class TestCreateGNUPGHome(MAASTestCase):
    """Tests for `create_gnupg_home`."""

    def make_nonexistent_path(self, parent_dir):
        """Return an as-yet nonexistent path, inside `parent_dir`."""
        return os.path.join(parent_dir, factory.make_name("gpghome"))

    def patch_gnupg_home(self, gpghome):
        self.patch(
            upgrade_cluster, "get_maas_user_gpghome"
        ).return_value = gpghome

    def patch_call(self):
        return self.patch(upgrade_cluster, "check_call")

    def test_succeeds_if_directory_exists(self):
        existing_home = self.make_dir()
        self.patch_gnupg_home(existing_home)
        self.patch_call()
        upgrade_cluster.create_gnupg_home()
        self.assertEqual([], os.listdir(existing_home))

    def test_creates_directory(self):
        parent = self.make_dir()
        new_home = self.make_nonexistent_path(parent)
        self.patch_gnupg_home(new_home)
        self.patch_call()
        upgrade_cluster.create_gnupg_home()
        self.assertThat(new_home, DirExists())

    def test_sets_ownership_to_maas_if_running_as_root(self):
        parent = self.make_dir()
        new_home = self.make_nonexistent_path(parent)
        self.patch_gnupg_home(new_home)
        call = self.patch_call()
        self.patch(os, "geteuid").return_value = 0
        upgrade_cluster.create_gnupg_home()
        self.assertThat(
            call, MockCalledOnceWith(["chown", "maas:maas", new_home])
        )

    def test_doesnt_set_ownership_to_maas_when_in_snap(self):
        parent = self.make_dir()
        new_home = self.make_nonexistent_path(parent)
        self.patch_gnupg_home(new_home)
        call = self.patch_call()
        self.patch(os, "geteuid").return_value = 0
        self.patch(snappy, "running_in_snap").return_value = True
        upgrade_cluster.create_gnupg_home()
        self.assertThat(call, MockNotCalled())

    def test_does_not_set_ownership_if_not_running_as_root(self):
        parent = self.make_dir()
        new_home = self.make_nonexistent_path(parent)
        self.patch_gnupg_home(new_home)
        call = self.patch_call()
        self.patch(os, "geteuid").return_value = 101
        upgrade_cluster.create_gnupg_home()
        self.assertThat(call, MockNotCalled())


class TestRetireBootResourcesYAML(MAASTestCase):
    """Tests for `retire_bootresources_yaml`."""

    def set_bootresources_yaml(self, contents):
        """Write a fake `bootresources.yaml`, and return its path."""
        path = self.make_file("bootresources.yaml", contents=contents)
        self.patch(upgrade_cluster, "BOOTRESOURCES_FILE", path)
        return path

    def test_does_nothing_if_file_not_present(self):
        path = self.set_bootresources_yaml("")
        os.remove(path)
        upgrade_cluster.retire_bootresources_yaml()
        self.assertThat(path, Not(FileExists()))

    def test_prefixes_header_to_file_if_present(self):
        content = factory.make_string()
        path = self.set_bootresources_yaml(content)
        upgrade_cluster.retire_bootresources_yaml()
        self.assertThat(
            path,
            FileContains(
                upgrade_cluster.BOOTRESOURCES_WARNING + content,
                encoding="utf-8",
            ),
        )

    def test_is_idempotent(self):
        path = self.set_bootresources_yaml(factory.make_string())
        upgrade_cluster.retire_bootresources_yaml()
        content_after_upgrade = read_text_file(path)
        upgrade_cluster.retire_bootresources_yaml()
        self.assertThat(
            path, FileContains(content_after_upgrade, encoding="utf-8")
        )

    def test_survives_encoding_problems(self):
        path = os.path.join(self.make_dir(), "bootresources.yaml")
        content = b"[[%s]]" % sample_binary_data
        with open(path, "wb") as config:
            config.write(content)
        self.patch(upgrade_cluster, "BOOTRESOURCES_FILE", path)
        upgrade_cluster.retire_bootresources_yaml()
        self.assertThat(
            path,
            FileContains(
                upgrade_cluster.BOOTRESOURCES_WARNING.encode("ascii") + content
            ),
        )


class TestMigrateArchitecturesIntoUbuntuDirectory(MAASTestCase):
    """Tests for the `migrate_architectures_into_ubuntu_directory` upgrade."""

    def configure_storage(self, storage_dir, make_current_dir=True):
        """Create a storage config."""
        self.current_dir = os.path.join(storage_dir, "current")
        os.makedirs(self.current_dir)
        self.useFixture(
            ClusterConfigurationFixture(tftp_root=self.current_dir)
        )
        if not make_current_dir:
            os.rmdir(self.current_dir)

    def test_list_subdirs_under_current_directory(self):
        self.patch(upgrade_cluster, "list_subdirs").return_value = ["ubuntu"]
        storage_dir = self.make_dir()
        self.configure_storage(storage_dir)
        upgrade_cluster.migrate_architectures_into_ubuntu_directory(
            self.current_dir
        )
        self.assertThat(
            upgrade_cluster.list_subdirs,
            MockCalledOnceWith(os.path.join(storage_dir, "current")),
        )

    def test_exits_early_if_boot_resources_dir_does_not_exist(self):
        # Patch list_subdirs, if it gets called then the method did not
        # exit early.
        self.patch(upgrade_cluster, "list_subdirs")
        storage_dir = os.path.join(self.make_dir(), factory.make_name("none"))
        self.configure_storage(storage_dir, make_current_dir=False)
        upgrade_cluster.migrate_architectures_into_ubuntu_directory(
            self.current_dir
        )
        self.assertThat(upgrade_cluster.list_subdirs, MockNotCalled())

    def test_exits_early_if_current_dir_does_not_exist(self):
        # Patch list_subdirs, if it gets called then the method did not
        # exit early.
        self.patch(upgrade_cluster, "list_subdirs")
        storage_dir = self.make_dir()
        self.configure_storage(storage_dir, make_current_dir=False)
        upgrade_cluster.migrate_architectures_into_ubuntu_directory(
            self.current_dir
        )
        self.assertThat(upgrade_cluster.list_subdirs, MockNotCalled())

    def test_exits_early_if_ubuntu_dir_exist(self):
        # Patch drill_down, if it gets called then the method did not
        # exit early.
        self.patch(upgrade_cluster, "drill_down")
        storage_dir = self.make_dir()
        self.configure_storage(storage_dir)
        os.makedirs(os.path.join(storage_dir, "current", "ubuntu"))
        upgrade_cluster.migrate_architectures_into_ubuntu_directory(
            self.current_dir
        )
        self.assertThat(upgrade_cluster.drill_down, MockNotCalled())

    def test_doesnt_create_ubuntu_dir_when_no_valid_directories(self):
        storage_dir = self.make_dir()
        self.configure_storage(storage_dir)
        upgrade_cluster.migrate_architectures_into_ubuntu_directory(
            self.current_dir
        )
        self.assertFalse(
            os.path.exists(os.path.join(storage_dir, "current", "ubuntu"))
        )

    def test_moves_paths_with_correct_levels_into_ubuntu_dir(self):
        storage_dir = self.make_dir()
        self.configure_storage(storage_dir)
        arches = [factory.make_name("arch") for _ in range(3)]
        subarches = [factory.make_name("subarch") for _ in range(3)]
        releases = [factory.make_name("release") for _ in range(3)]
        labels = [factory.make_name("label") for _ in range(3)]
        for arch, subarch, release, label in product(
            arches, subarches, releases, labels
        ):
            os.makedirs(
                os.path.join(
                    storage_dir, "current", arch, subarch, release, label
                )
            )
        self.patch(upgrade_cluster, "update_targets_conf")
        upgrade_cluster.migrate_architectures_into_ubuntu_directory(
            self.current_dir
        )
        self.assertItemsEqual(
            arches,
            list_subdirs(os.path.join(storage_dir, "current", "ubuntu")),
        )

    def test_doesnt_move_paths_with_fewer_levels_into_ubuntu_dir(self):
        storage_dir = self.make_dir()
        self.configure_storage(storage_dir)
        arches = [factory.make_name("arch") for _ in range(3)]
        subarches = [factory.make_name("subarch") for _ in range(3)]
        releases = [factory.make_name("release") for _ in range(3)]
        # Labels directory is missing, causing none of the folders to move
        for arch, subarch, release in product(arches, subarches, releases):
            os.makedirs(
                os.path.join(storage_dir, "current", arch, subarch, release)
            )
        move_arch = factory.make_name("arch")
        os.makedirs(
            os.path.join(
                storage_dir,
                "current",
                move_arch,
                factory.make_name("subarch"),
                factory.make_name("release"),
                factory.make_name("label"),
            )
        )
        self.patch(upgrade_cluster, "update_targets_conf")
        upgrade_cluster.migrate_architectures_into_ubuntu_directory(
            self.current_dir
        )
        self.assertItemsEqual(
            [move_arch],
            list_subdirs(os.path.join(storage_dir, "current", "ubuntu")),
        )

    def test_doesnt_move_paths_with_more_levels_into_ubuntu_dir(self):
        storage_dir = self.make_dir()
        self.configure_storage(storage_dir)
        # Extra directory level, this is what it looks like after upgrade.
        osystems = [factory.make_name("arch") for _ in range(3)]
        arches = [factory.make_name("arch") for _ in range(3)]
        subarches = [factory.make_name("subarch") for _ in range(3)]
        releases = [factory.make_name("release") for _ in range(3)]
        labels = [factory.make_name("label") for _ in range(3)]
        for osystem, arch, subarch, release, label in product(
            osystems, arches, subarches, releases, labels
        ):
            os.makedirs(
                os.path.join(
                    storage_dir,
                    "current",
                    osystem,
                    arch,
                    subarch,
                    release,
                    label,
                )
            )
        move_arch = factory.make_name("arch")
        os.makedirs(
            os.path.join(
                storage_dir,
                "current",
                move_arch,
                factory.make_name("subarch"),
                factory.make_name("release"),
                factory.make_name("label"),
            )
        )
        self.patch(upgrade_cluster, "update_targets_conf")
        upgrade_cluster.migrate_architectures_into_ubuntu_directory(
            self.current_dir
        )
        self.assertItemsEqual(
            [move_arch],
            list_subdirs(os.path.join(storage_dir, "current", "ubuntu")),
        )

    def setup_working_migration_scenario(self):
        storage_dir = self.make_dir()
        self.configure_storage(storage_dir)
        arches = [factory.make_name("arch") for _ in range(3)]
        subarches = [factory.make_name("subarch") for _ in range(3)]
        releases = [factory.make_name("release") for _ in range(3)]
        labels = [factory.make_name("label") for _ in range(3)]
        for arch, subarch, release, label in product(
            arches, subarches, releases, labels
        ):
            os.makedirs(
                os.path.join(
                    storage_dir, "current", arch, subarch, release, label
                )
            )
        return storage_dir


class TestCreateBootloaderSymLinks(MAASTestCase):
    """Tests for the `create_bootloader_sym_links` upgrade."""

    def test_does_nothing_if_no_tftp_root(self):
        non_existing_path = os.path.join("/tmp", factory.make_name())
        mocks = [
            self.patch(bootloader, "link_bootloader")
            for _, bootloader in BootMethodRegistry
        ]
        upgrade_cluster.create_bootloader_sym_links(non_existing_path)
        for mock in mocks:
            self.assertThat(mock, MockNotCalled())

    def test_links_bootloaders(self):
        path = self.make_dir()
        mocks = [
            self.patch(bootloader, "link_bootloader")
            for _, bootloader in BootMethodRegistry
        ]
        upgrade_cluster.create_bootloader_sym_links(path)
        for mock in mocks:
            self.assertThat(mock, MockCalledOnceWith(path))
