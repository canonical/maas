# Copyright 2012-2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for creating disks for diskless booting."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import os
from textwrap import dedent

from maastesting.factory import factory
from maastesting.matchers import (
    MockCalledOnceWith,
    MockNotCalled,
)
from maastesting.testcase import MAASTestCase
from mock import sentinel
from provisioningserver import (
    config,
    diskless,
)
from provisioningserver.diskless import (
    compose_diskless_link_path,
    compose_diskless_tgt_config,
    compose_source_path,
    create_diskless_disk,
    create_diskless_link,
    delete_diskless_disk,
    delete_diskless_link,
    DisklessError,
    get_diskless_driver,
    get_diskless_store,
    get_diskless_target,
    get_diskless_tgt_path,
    read_diskless_link,
    reload_diskless_tgt,
    tgt_entry,
    update_diskless_tgt,
)
from provisioningserver.drivers.diskless import DisklessDriverRegistry
from provisioningserver.drivers.diskless.tests.test_base import (
    make_diskless_driver,
)
from provisioningserver.drivers.osystem import (
    BOOT_IMAGE_PURPOSE,
    OperatingSystemRegistry,
)
from provisioningserver.testing.os import FakeOS
from provisioningserver.utils.testing import RegistryFixture
from testtools.matchers import (
    FileExists,
    Not,
)


class DisklessTestMixin:
    """Helper mixin for diskless tests.

    Uses the RegistryFixture so the provisioningserver registry is
    empty.
    """

    def setUp(self):
        super(DisklessTestMixin, self).setUp()
        # Ensure the global registry is empty for each test run.
        self.useFixture(RegistryFixture())

    def configure_resource_storage(self):
        resource_dir = self.make_dir()
        os.mkdir(os.path.join(resource_dir, 'diskless'))
        self.patch(config, 'BOOT_RESOURCES_STORAGE', resource_dir)
        return resource_dir

    def configure_diskless_storage(self):
        storage_dir = self.make_dir()
        self.patch(diskless, 'get_diskless_store').return_value = storage_dir
        return storage_dir

    def configure_compose_source_path(self, path=None):
        if path is None:
            path = self.make_file()
        self.patch(diskless, 'compose_source_path').return_value = path
        return path

    def make_usable_osystem_with_release(self, purposes=None):
        os_name = factory.make_name('os')
        release_name = factory.make_name('release')
        if purposes is None:
            purposes = [BOOT_IMAGE_PURPOSE.DISKLESS]
        osystem = FakeOS(
            os_name, purposes, releases=[release_name])
        OperatingSystemRegistry.register_item(os_name, osystem)
        return os_name, release_name

    def make_usable_diskless_driver(self, name=None, description=None,
                                    settings=None):
        driver = make_diskless_driver(
            name=name, description=description, settings=settings)
        DisklessDriverRegistry.register_item(driver.name, driver)
        return driver

    def patch_reload_diskless_tgt(self):
        """Stops `reload_diskless_tgt` from running."""
        self.patch(diskless, 'reload_diskless_tgt')


class TestHelpers(MAASTestCase, DisklessTestMixin):

    def test_get_diskless_store(self):
        storage_dir = factory.make_name('storage')
        self.patch(config, 'BOOT_RESOURCES_STORAGE', storage_dir)
        self.assertEqual(
            os.path.join(storage_dir, 'diskless', 'store'),
            get_diskless_store())

    def test_compose_diskless_link_path(self):
        system_id = factory.make_name('system_id')
        storage_dir = self.configure_diskless_storage()
        self.assertEqual(
            os.path.join(storage_dir, system_id),
            compose_diskless_link_path(system_id))

    def test_create_diskless_link_creates_link(self):
        system_id = factory.make_name('system_id')
        storage_dir = self.configure_diskless_storage()
        link_path = factory.make_name('link_path')
        create_diskless_link(system_id, link_path)
        self.assertEqual(
            link_path, os.readlink(os.path.join(storage_dir, system_id)))

    def test_create_diskless_link_error_on_already_exists(self):
        system_id = factory.make_name('system_id')
        storage_dir = self.configure_diskless_storage()
        factory.make_file(storage_dir, system_id)
        self.assertRaises(
            DisklessError,
            create_diskless_link, system_id, 'link_path')

    def test_create_diskless_link_uses_lexists(self):
        system_id = factory.make_name('system_id')
        storage_dir = self.configure_diskless_storage()
        mock_lexists = self.patch(os.path, 'lexists')
        mock_lexists.return_value = False
        create_diskless_link(system_id, factory.make_name('link_path'))
        self.assertThat(
            mock_lexists,
            MockCalledOnceWith(os.path.join(storage_dir, system_id)))

    def test_delete_diskless_link_deletes_link(self):
        system_id = factory.make_name('system_id')
        storage_dir = self.configure_diskless_storage()
        factory.make_file(storage_dir, system_id)
        delete_diskless_link(system_id)
        self.assertThat(
            os.path.join(storage_dir, system_id), Not(FileExists()))

    def test_delete_diskless_link_uses_lexists(self):
        system_id = factory.make_name('system_id')
        storage_dir = self.configure_diskless_storage()
        mock_lexists = self.patch(os.path, 'lexists')
        mock_lexists.return_value = False
        delete_diskless_link(system_id)
        self.assertThat(
            mock_lexists,
            MockCalledOnceWith(os.path.join(storage_dir, system_id)))

    def test_read_diskless_link_returns_link_path(self):
        system_id = factory.make_name('system_id')
        self.configure_diskless_storage()
        link_path = factory.make_name('link_path')
        create_diskless_link(system_id, link_path)
        self.assertEqual(link_path, read_diskless_link(system_id))

    def test_read_diskless_link_uses_lexists(self):
        system_id = factory.make_name('system_id')
        storage_dir = self.configure_diskless_storage()
        mock_lexists = self.patch(os.path, 'lexists')
        mock_lexists.return_value = False
        read_diskless_link(system_id)
        self.assertThat(
            mock_lexists,
            MockCalledOnceWith(os.path.join(storage_dir, system_id)))

    def test_get_diskless_driver_returns_driver(self):
        driver = self.make_usable_diskless_driver()
        self.assertEqual(driver, get_diskless_driver(driver.name))

    def test_get_diskless_driver_errors_on_missing_driver(self):
        invalid_name = factory.make_name('invalid_driver')
        self.assertRaises(DisklessError, get_diskless_driver, invalid_name)


class TestTgtHelpers(MAASTestCase, DisklessTestMixin):

    def test_get_diskless_target(self):
        system_id = factory.make_name('system_id')
        self.assertEqual(
            'iqn.2004-05.com.ubuntu:maas:root-diskless-%s' % system_id,
            get_diskless_target(system_id))

    def test_get_diskless_tgt_path(self):
        storage_dir = self.configure_resource_storage()
        self.assertEqual(
            os.path.join(storage_dir, 'diskless', 'maas-diskless.tgt'),
            get_diskless_tgt_path())

    def test_tgt_entry(self):
        system_id = factory.make_name('system_id')
        image_path = factory.make_name('image_path')
        expected_entry = dedent("""\
            <target iqn.2004-05.com.ubuntu:maas:root-diskless-{system_id}>
                readonly 0
                backing-store "{image}"
                driver iscsi
            </target>
            """).format(system_id=system_id, image=image_path)
        self.assertEqual(
            expected_entry,
            tgt_entry(system_id, image_path))

    def test_compose_diskless_tgt_config(self):
        storage_dir = self.configure_diskless_storage()
        system_ids = [factory.make_name('system_id') for _ in range(3)]
        tgt_entries = []
        for system_id in system_ids:
            factory.make_file(storage_dir, system_id)
            tgt_entries.append(
                tgt_entry(system_id, os.path.join(storage_dir, system_id)))
        tgt_output = compose_diskless_tgt_config()
        self.assertItemsEqual(
            tgt_entries, [
                '%s</target>\n' % entry
                for entry in tgt_output.split('</target>\n')
                if entry != ""
                ])

    def test_reload_diskless_tgt(self):
        tgt_path = factory.make_name('tgt_path')
        self.patch(diskless, 'get_diskless_tgt_path').return_value = tgt_path
        mock_call = self.patch(diskless, 'call_and_check')
        reload_diskless_tgt()
        self.assertThat(
            mock_call,
            MockCalledOnceWith([
                'sudo',
                '/usr/sbin/tgt-admin',
                '--conf', tgt_path,
                '--update', 'ALL',
                ]))

    def test_update_diskless_tgt_calls_atomic_write(self):
        tgt_path = factory.make_name('tgt_path')
        self.patch(
            diskless, 'get_diskless_tgt_path').return_value = tgt_path
        tgt_config = factory.make_name('tgt_config')
        self.patch(
            diskless, 'compose_diskless_tgt_config').return_value = tgt_config
        mock_write = self.patch(diskless, 'atomic_write')
        self.patch_reload_diskless_tgt()
        update_diskless_tgt()
        self.assertThat(
            mock_write,
            MockCalledOnceWith(tgt_config, tgt_path, mode=0644))


class TestComposeSourcePath(MAASTestCase, DisklessTestMixin):

    def test__raises_error_on_missing_os_from_registry(self):
        self.assertRaises(
            DisklessError,
            compose_source_path, factory.make_name('osystem'), sentinel.arch,
            sentinel.subarch, sentinel.release, sentinel.label)

    def test__raises_error_when_os_doesnt_support_diskless(self):
        osystem, release = self.make_usable_osystem_with_release(
            purposes=[BOOT_IMAGE_PURPOSE.XINSTALL])
        self.assertRaises(
            DisklessError,
            compose_source_path, osystem, sentinel.arch, sentinel.subarch,
            release, sentinel.label)

    def test__returns_valid_path(self):
        os_name, release = self.make_usable_osystem_with_release()
        arch = factory.make_name('arch')
        subarch = factory.make_name('subarch')
        label = factory.make_name('label')
        root_path = factory.make_name('root_path')
        osystem = OperatingSystemRegistry[os_name]
        mock_xi_params = self.patch(osystem, 'get_xinstall_parameters')
        mock_xi_params.return_value = (root_path, 'tgz')
        self.assertEqual(
            os.path.join(
                config.BOOT_RESOURCES_STORAGE, 'current', os_name,
                arch, subarch, release, label, root_path),
            compose_source_path(os_name, arch, subarch, release, label))


class TestCreateDisklessDisk(MAASTestCase, DisklessTestMixin):

    def test__raises_error_on_doesnt_exist_source_path(self):
        self.configure_compose_source_path(factory.make_name('invalid_path'))
        self.assertRaises(
            DisklessError,
            create_diskless_disk, sentinel.driver, sentinel.driver_options,
            sentinel.system_id, sentinel.osystem, sentinel.arch,
            sentinel.subarch, sentinel.release, sentinel.label)

    def test__raises_error_on_link_already_exists(self):
        self.configure_diskless_storage()
        self.configure_compose_source_path()
        system_id = factory.make_name('system_id')
        create_diskless_link(system_id, factory.make_name('link_path'))
        self.assertRaises(
            DisklessError,
            create_diskless_disk, sentinel.driver, sentinel.driver_options,
            system_id, sentinel.osystem, sentinel.arch,
            sentinel.subarch, sentinel.release, sentinel.label)

    def test__calls_create_disk_on_driver(self):
        self.patch_reload_diskless_tgt()
        self.configure_resource_storage()
        self.configure_diskless_storage()
        source_path = self.configure_compose_source_path()
        driver = self.make_usable_diskless_driver()
        mock_create = self.patch(driver, 'create_disk')
        mock_create.return_value = self.make_file()
        system_id = factory.make_name('system_id')
        driver_options = {
            factory.make_name('arg'): factory.make_name('value')
            for _ in range(3)
            }
        create_diskless_disk(
            driver.name, driver_options,
            system_id, sentinel.osystem, sentinel.arch,
            sentinel.subarch, sentinel.release, sentinel.label)
        self.assertThat(
            mock_create,
            MockCalledOnceWith(system_id, source_path, **driver_options))

    def test__errors_when_driver_create_disk_returns_None(self):
        self.patch_reload_diskless_tgt()
        self.configure_resource_storage()
        self.configure_diskless_storage()
        self.configure_compose_source_path()
        driver = self.make_usable_diskless_driver()
        mock_create = self.patch(driver, 'create_disk')
        mock_create.return_value = None
        system_id = factory.make_name('system_id')
        self.assertRaises(
            DisklessError,
            create_diskless_disk, driver.name, {},
            system_id, sentinel.osystem, sentinel.arch,
            sentinel.subarch, sentinel.release, sentinel.label)

    def test__errors_when_driver_create_disk_returns_invalid_path(self):
        self.patch_reload_diskless_tgt()
        self.configure_resource_storage()
        self.configure_diskless_storage()
        self.configure_compose_source_path()
        driver = self.make_usable_diskless_driver()
        mock_create = self.patch(driver, 'create_disk')
        mock_create.return_value = factory.make_name('invalid_path')
        system_id = factory.make_name('system_id')
        self.assertRaises(
            DisklessError,
            create_diskless_disk, driver.name, {},
            system_id, sentinel.osystem, sentinel.arch,
            sentinel.subarch, sentinel.release, sentinel.label)

    def test__creates_diskless_link(self):
        self.patch_reload_diskless_tgt()
        self.configure_resource_storage()
        self.configure_diskless_storage()
        self.configure_compose_source_path()
        driver = self.make_usable_diskless_driver()
        create_file = self.make_file()
        mock_create = self.patch(driver, 'create_disk')
        mock_create.return_value = create_file
        system_id = factory.make_name('system_id')
        create_diskless_disk(
            driver.name, {},
            system_id, sentinel.osystem, sentinel.arch,
            sentinel.subarch, sentinel.release, sentinel.label)
        self.assertEqual(create_file, read_diskless_link(system_id))

    def test__calls_update_diskless_tgt(self):
        self.configure_resource_storage()
        self.configure_diskless_storage()
        self.configure_compose_source_path()
        driver = self.make_usable_diskless_driver()
        mock_create = self.patch(driver, 'create_disk')
        mock_create.return_value = self.make_file()
        system_id = factory.make_name('system_id')
        mock_update_tgt = self.patch(diskless, 'update_diskless_tgt')
        create_diskless_disk(
            driver.name, {},
            system_id, sentinel.osystem, sentinel.arch,
            sentinel.subarch, sentinel.release, sentinel.label)
        self.assertThat(mock_update_tgt, MockCalledOnceWith())


class TestDeleteDisklessDisk(MAASTestCase, DisklessTestMixin):

    def test__exits_early_on_missing_link(self):
        self.configure_diskless_storage()
        system_id = factory.make_name('system_id')
        # if read_diskless_link is called then, did not exit early
        mock_read_link = self.patch(diskless, 'read_diskless_link')
        delete_diskless_disk(
            sentinel.driver, sentinel.driver_options, system_id)
        self.assertThat(mock_read_link, MockNotCalled())

    def test__checks_for_link_using_lexists(self):
        self.configure_diskless_storage()
        system_id = factory.make_name('system_id')
        mock_lexists = self.patch(os.path, 'lexists')
        mock_lexists.return_value = False
        delete_diskless_disk(
            sentinel.driver, sentinel.driver_options, system_id)
        self.assertThat(
            mock_lexists,
            MockCalledOnceWith(compose_diskless_link_path(system_id)))

    def test__raises_error_if_read_diskless_link_returns_None(self):
        self.configure_diskless_storage()
        system_id = factory.make_name('system_id')
        create_diskless_link(system_id, factory.make_name('link'))
        self.patch(diskless, 'read_diskless_link').return_value = None
        self.assertRaises(
            DisklessError, delete_diskless_disk,
            sentinel.driver, sentinel.driver_options, system_id)

    def test__calls_delete_disk_on_driver_when_link_points_to_valid_path(self):
        self.patch_reload_diskless_tgt()
        self.configure_resource_storage()
        self.configure_diskless_storage()
        system_id = factory.make_name('system_id')
        link_path = self.make_file()
        create_diskless_link(system_id, link_path)
        driver = self.make_usable_diskless_driver()
        mock_delete = self.patch(driver, 'delete_disk')
        driver_options = {
            factory.make_name('arg'): factory.make_name('value')
            for _ in range(3)
            }
        delete_diskless_disk(driver.name, driver_options, system_id)
        self.assertThat(
            mock_delete,
            MockCalledOnceWith(system_id, link_path, **driver_options))

    def test__doenst_call_delete_disk_on_driver_when_link_is_invalid(self):
        self.patch_reload_diskless_tgt()
        self.configure_resource_storage()
        self.configure_diskless_storage()
        system_id = factory.make_name('system_id')
        create_diskless_link(system_id, factory.make_name('link'))
        driver = self.make_usable_diskless_driver()
        mock_delete = self.patch(driver, 'delete_disk')
        delete_diskless_disk(driver.name, {}, system_id)
        self.assertThat(mock_delete, MockNotCalled())

    def test__deletes_diskless_link(self):
        self.patch_reload_diskless_tgt()
        self.configure_resource_storage()
        storage_dir = self.configure_diskless_storage()
        system_id = factory.make_name('system_id')
        create_diskless_link(system_id, self.make_file())
        driver = self.make_usable_diskless_driver()
        self.patch(driver, 'delete_disk')
        delete_diskless_disk(driver.name, {}, system_id)
        self.assertThat(
            os.path.join(storage_dir, system_id), Not(FileExists()))

    def test__calls_update_diskless_tgt(self):
        self.configure_resource_storage()
        self.configure_diskless_storage()
        system_id = factory.make_name('system_id')
        create_diskless_link(system_id, self.make_file())
        driver = self.make_usable_diskless_driver()
        self.patch(driver, 'delete_disk')
        mock_update_tgt = self.patch(diskless, 'update_diskless_tgt')
        delete_diskless_disk(driver.name, {}, system_id)
        self.assertThat(mock_update_tgt, MockCalledOnceWith())
