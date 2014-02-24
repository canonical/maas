# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the edit_named_options command."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from codecs import getwriter
from io import BytesIO
import os
import shutil
import textwrap

from django.core.management import call_command
from django.core.management.base import CommandError
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from testtools.matchers import (
    Contains,
    FileContains,
    Not,
    )
from provisioningserver.dns.config import MAAS_NAMED_CONF_OPTIONS_INSIDE_NAME


OPTIONS_FILE = textwrap.dedent("""\
    options {
        directory "/var/cache/bind";
        auth-nxdomain no;    # conform to RFC1035
        listen-on-v6 { any; };
    };
""")

OPTIONS_FILE_WITH_FORWARDERS = textwrap.dedent("""\
    options {
        directory "/var/cache/bind";
        forwarders { 192.168.1.1; };
        auth-nxdomain no;    # conform to RFC1035
        listen-on-v6 { any; };
    };
""")


class TestEditNamedOptionsCommand(MAASServerTestCase):

    def setUp(self):
        super(TestEditNamedOptionsCommand, self).setUp()
        out = BytesIO()
        self.stdout = getwriter("UTF-8")(out)

    def assertFailsWithMessage(self, config_path, message):
        e = self.assertRaises(
            CommandError,
            call_command, "edit_named_options", config_path=config_path,
            stdout=self.stdout)
        self.assertIn(message, e.message)

    def assertContentFailsWithMessage(self, content, message):
        options_file = self.make_file(contents=content)
        self.assertFailsWithMessage(options_file, message)
        # The original file must be untouched.
        self.assertThat(options_file, FileContains(content))

    def test_exits_when_no_file_to_edit(self):
        dir = self.make_dir()
        absent_file = os.path.join(dir, "foo")
        self.assertFailsWithMessage(absent_file, "does not exist")

    def test_exits_when_file_has_no_options_block(self):
        content = factory.getRandomString()
        self.assertContentFailsWithMessage(
            content, "Can't find options {} block")

    def test_exits_when_cant_parse_config(self):
        content = "options { forwarders {1.1.1.1} "
        # (missing a closing brace)
        self.assertContentFailsWithMessage(content, "Failed to parse")

    def test_exits_when_fails_to_make_backup(self):
        self.patch(shutil, "copyfile").side_effect = IOError("whatever")
        self.assertContentFailsWithMessage(
            OPTIONS_FILE, "Failed to make a backup")

    def test_removes_existing_forwarders_config(self):
        options_file = self.make_file(contents=OPTIONS_FILE_WITH_FORWARDERS)
        call_command(
            "edit_named_options", config_path=options_file,
            stdout=self.stdout)

        # Check that the file was re-written without forwarders (since
        # that's now in the included file).
        self.assertThat(
            options_file,
            Not(FileContains(
                matcher=Contains('forwarders'))))

    def test_normal_operation(self):
        options_file = self.make_file(contents=OPTIONS_FILE)
        call_command(
            "edit_named_options", config_path=options_file,
            stdout=self.stdout)
        expected_path = os.path.join(
            os.path.dirname(options_file),
            MAAS_NAMED_CONF_OPTIONS_INSIDE_NAME)

        # Check that the file was re-written with the include statement.
        self.assertThat(
            options_file,
            FileContains(
                matcher=Contains(
                    'include "%s";' % expected_path)))

        # Check that the backup was made.
        options_file_base = os.path.dirname(options_file)
        files = os.listdir(options_file_base)
        self.assertEqual(2, len(files))
        files.remove(os.path.basename(options_file))
        [backup_file] = files
        backup_file = os.path.join(options_file_base, backup_file)
        self.assertThat(backup_file, FileContains(OPTIONS_FILE))
