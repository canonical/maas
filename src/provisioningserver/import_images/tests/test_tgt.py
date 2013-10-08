# Copyright 2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for import script's iSCSI code."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import os.path
from random import randint
import subprocess
from textwrap import dedent

from maastesting.factory import factory
from maastesting.matchers import ContainsAll
from maastesting.testcase import MAASTestCase
from provisioningserver.import_images import tgt as tgt_module
from provisioningserver.import_images.tgt import (
    clean_up_info_file,
    get_conf_path,
    get_target_name,
    prefix_target_name,
    set_up_data_dir,
    target_exists,
    TargetNotCreated,
    tgt_admin_delete,
    tgt_admin_update,
    tgt_conf_d,
    write_conf,
    write_info_file,
    )
from provisioningserver.utils import read_text_file
from testtools.matchers import (
    Contains,
    DirExists,
    FileContains,
    FileExists,
    Not,
    StartsWith,
    )


class TestTGT(MAASTestCase):
    def test_tgt_conf_d_adds_config_dir(self):
        data_dir = self.make_dir()
        self.assertEqual(
            os.path.join(data_dir, 'tgt.conf.d'),
            tgt_conf_d(data_dir))

    def test_tgt_conf_d_returns_absolute_path(self):
        data_dir = factory.make_name('tgtdata')
        conf_dir = tgt_conf_d(data_dir)
        self.assertThat(conf_dir, StartsWith(os.path.sep))
        self.assertThat(conf_dir, Contains(data_dir))

    def test_get_conf_path(self):
        data_dir = self.make_dir()
        conf_name = factory.make_name()

        self.assertEquals(
            os.path.join(data_dir, 'tgt.conf.d', conf_name + ".conf"),
            get_conf_path(data_dir, conf_name))

    def test_get_target_name(self):
        release = factory.make_name('release', sep='_')
        version = factory.make_name('version', sep='_')
        arch = factory.make_name('arch', sep='_')
        version_name = factory.make_name('vername', sep='_')
        self.assertEqual(
            'maas-%s-%s-%s-%s' % (release, version, arch, version_name),
            get_target_name(release, version, arch, version_name))

    def test_tgt_admin_delete_calls_tgt_admin(self):
        run = self.patch(subprocess, 'check_call')
        target = factory.make_name('target')

        tgt_admin_delete(target)

        run.assert_called_once_with([
            "tgt-admin",
            "--conf", "/etc/tgt/targets.conf",
            "--delete", prefix_target_name(target),
            ])

    def test_tgt_admin_update_calls_tgt_admin(self):
        check_call = self.patch(subprocess, 'check_call')
        target = factory.make_name('target')
        full_name = prefix_target_name(target)
        self.patch(tgt_module, 'target_exists').return_value = True
        target_dir = self.make_dir()

        tgt_admin_update(target_dir, target)

        check_call.assert_called_once_with([
            'tgt-admin',
            '--conf', '/etc/tgt/targets.conf',
            '--update',
            full_name,
            ])

    def test_tgt_admin_update_detects_target_not_created(self):
        self.patch(subprocess, 'check_call')
        # Simulate tgt-admin's failure to create the target.
        check_output = self.patch(subprocess, 'check_output')
        check_output.return_value = b""

        self.assertRaises(
            TargetNotCreated,
            tgt_admin_update, self.make_dir(), factory.make_name('target'))

    def make_target_line(self, target_name=None, number=None):
        """Create a fake line of `tgt` output for a given target.

        This is the header line which `target_exists` recognises as the header
        for the description of that target.

        The line is in ASCII `bytes`, not `unicode`.
        """
        if target_name is None:
            target_name = factory.make_name('target')
        if number is None:
            number = randint(0, 99999)
        line = "Target %d: %s" % (number, target_name)
        return line.encode('ascii')

    def test_target_exists_calls_tgt_admin(self):
        target_name = factory.make_name('target')
        check_output = self.patch(subprocess, 'check_output')
        check_output.return_value = self.make_target_line(target_name)

        target_exists(target_name)

        check_output.assert_called_once_with([
            "tgt-admin",
            '--conf', '/etc/tgt/targets.conf',
            '--show',
            ])

    def test_target_exists_reecognises_target_line(self):
        target_name = factory.make_name('target')
        self.patch(subprocess, 'check_output').return_value = (
            self.make_target_line(target_name))
        self.assertTrue(target_exists(target_name))

    def test_target_exists_ignores_other_lines(self):
        target_name = factory.make_name('target')
        self.patch(subprocess, 'check_output').return_value = dedent(b"""\
            Other targets.
            %s
            Further text.
            """ % self.make_target_line(target_name))

        self.assertTrue(target_exists(target_name))

    def test_target_exists_requires_target_line(self):
        self.patch(subprocess, 'check_output').return_value = b"""
            Lots of stuff here.
            But not the target we're looking for.
            Sorry.
            """
        self.assertFalse(target_exists(factory.make_name('target')))

    def test_target_exists_requires_unindented_target_line(self):
        target_name = factory.make_name('target')
        self.patch(subprocess, 'check_output').return_value = (
            b"  " + self.make_target_line(target_name))
        self.assertFalse(target_exists(target_name))

    def test_target_exists_tolerates_trailing_whitespace(self):
        target_name = factory.make_name('target')
        self.patch(subprocess, 'check_output').return_value = (
            self.make_target_line(target_name) + b"  ")
        self.assertTrue(target_exists(target_name))

    def test_target_exists_ignores_other_targets(self):
        self.patch(subprocess, 'check_output').return_value = (
            self.make_target_line())
        self.assertFalse(target_exists(factory.make_name('missing-target')))

    def test_target_exists_ignores_superset_target_names(self):
        target_name = factory.make_name('target')
        self.patch(subprocess, 'check_output').return_value = (
            self.make_target_line(target_name + "PLUS"))
        self.assertFalse(target_exists(target_name))

    def test_target_exists_escapes_target_name(self):
        self.patch(subprocess, 'check_output').return_value = (
            self.make_target_line())

        self.assertFalse(target_exists('.*'))

    def test_set_up_data_dir_creates_dir(self):
        data_dir = os.path.join(self.make_dir(), factory.make_name('data'))
        set_up_data_dir(data_dir)
        self.assertThat(data_dir, DirExists())

    def test_set_up_data_dir_creates_conf_dir(self):
        data_dir = os.path.join(self.make_dir(), factory.make_name('data'))
        set_up_data_dir(data_dir)
        self.assertThat(tgt_conf_d(data_dir), DirExists())

    def test_set_up_data_dir_writes_tgt_conf(self):
        data_dir = os.path.join(self.make_dir(), factory.make_name('data'))
        set_up_data_dir(data_dir)
        self.assertThat(os.path.join(data_dir, 'tgt.conf'), FileExists())

    def test_set_up_data_dir_accepts_existing_dir(self):
        data_dir = self.make_dir()

        set_up_data_dir(data_dir)
        set_up_data_dir(data_dir)

        self.assertThat(data_dir, DirExists())
        self.assertThat(tgt_conf_d(data_dir), DirExists())
        self.assertThat(os.path.join(data_dir, 'tgt.conf'), FileExists())

    def test_write_info_file_writes_file(self):
        target_dir = self.make_dir()
        target = factory.make_name('target')
        release = factory.make_name('release')
        label = factory.make_name('label')
        serial = factory.make_name('serial')
        arch = factory.make_name('arch')

        write_info_file(target_dir, target, release, label, serial, arch)

        info = read_text_file(os.path.join(target_dir, 'info'))
        self.assertItemsEqual(
            info.strip().splitlines(),
            [
                'name=%s' % target,
                'release=%s' % release,
                'label=%s' % label,
                'serial=%s' % serial,
                'arch=%s' % arch,
            ])

    def test_clean_up_info_file_accepts_nonexistent_info_file(self):
        target_dir = self.make_dir()
        clean_up_info_file(target_dir)
        self.assertThat(os.path.join(target_dir, 'info'), Not(FileExists()))

    def test_clean_up_info_file_moves_info_file(self):
        text = factory.getRandomString()
        info_file = self.make_file(name='info', contents=text)
        clean_up_info_file(os.path.dirname(info_file))
        self.assertThat(info_file, Not(FileExists()))
        self.assertThat(info_file + '.failed', FileContains(text))

    def test_clean_up_info_file_removes_old_info_failed_file(self):
        target_dir = self.make_dir()
        info_file = factory.make_file(target_dir, 'info')
        info_failed_file = factory.make_file(target_dir, 'info.failed')
        read_text_file(info_failed_file)
        new_text = read_text_file(info_file)

        clean_up_info_file(target_dir)

        self.assertThat(info_failed_file, FileContains(new_text))

    def test_write_conf_writes_conf_file(self):
        conf = self.make_file()
        target = factory.make_name('target')
        image = factory.make_name('image')

        write_conf(conf, target, image)

        self.assertThat(
            read_text_file(conf),
            ContainsAll([
                'com.ubuntu:maas:%s' % target,
                'backing-store "%s"' % image,
                '</target>',
                ]))
