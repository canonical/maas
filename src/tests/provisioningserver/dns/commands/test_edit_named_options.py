# Copyright 2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the edit_named_options command."""

from argparse import ArgumentParser
import io
import os
import shutil
import textwrap

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver.dns.commands.edit_named_options import (
    add_arguments,
    run,
)
from provisioningserver.dns.config import MAAS_NAMED_CONF_OPTIONS_INSIDE_NAME
from provisioningserver.utils.isc import make_isc_string, read_isc_file

OPTIONS_FILE = textwrap.dedent(
    """\
    options {
        directory "/var/cache/bind";
        auth-nxdomain no;    # conform to RFC1035
        listen-on-v6 { any; };
    };
"""
)

OPTIONS_FILE_WITH_DNSSEC = textwrap.dedent(
    """\
    options {
        directory "/var/cache/bind";
        dnssec-validation auto;
        auth-nxdomain no;    # conform to RFC1035
        listen-on-v6 { any; };
    };
"""
)

OPTIONS_FILE_WITH_FORWARDERS = textwrap.dedent(
    """\
    options {
        directory "/var/cache/bind";
        forwarders { 192.168.1.1; 192.168.1.2; };
        auth-nxdomain no;    # conform to RFC1035
        listen-on-v6 { any; };
    };
"""
)

OPTIONS_FILE_WITH_FORWARDERS_AND_DNSSEC = textwrap.dedent(
    """\
    options {
        directory "/var/cache/bind";
        forwarders { 192.168.1.1; 192.168.1.2; };
        dnssec-validation no;
        auth-nxdomain no;    # conform to RFC1035
        listen-on-v6 { any; };
    };
"""
)

OPTIONS_FILE_WITH_EXTRA_AND_DUP_FORWARDER = textwrap.dedent(
    """\
    options {
        directory "/var/cache/bind";
        forwarders { 192.168.1.2; 192.168.1.3; };
        dnssec-validation no;
        auth-nxdomain no;    # conform to RFC1035
        listen-on-v6 { any; };
    };
"""
)


class TestGetNamedConfCommand(MAASTestCase):
    def setUp(self):
        super().setUp()
        self.output = io.StringIO()
        self.error_output = io.StringIO()
        self.parser = ArgumentParser()
        add_arguments(self.parser)

    def run_command(self, *args):
        parsed_args = self.parser.parse_args([*args])
        return run(parsed_args, stdout=self.output, stderr=self.error_output)

    def assertFailsWithMessage(self, config_path, message):
        rc = self.run_command("--config-path", config_path)
        self.assertEqual(1, rc)
        self.assertIn(message, self.error_output.getvalue())

    def assertContentFailsWithMessage(self, content, message):
        options_file = self.make_file(contents=content)
        self.assertFailsWithMessage(options_file, message)
        # The original file must be untouched.
        with open(options_file, "r") as fh:
            contents = fh.read()
        self.assertEqual(contents, content)

    def test_exits_when_no_file_to_edit(self):
        dir = self.make_dir()
        absent_file = os.path.join(dir, "foo")
        self.assertFailsWithMessage(absent_file, "does not exist")

    def test_exits_when_file_has_no_options_block(self):
        content = factory.make_string()
        self.assertContentFailsWithMessage(
            content, "Can't find options {} block"
        )

    def test_exits_when_cant_parse_config(self):
        content = "options { forwarders {1.1.1.1} "
        # (missing a closing brace)
        self.assertContentFailsWithMessage(content, "Failed to parse")

    def test_exits_when_fails_to_make_backup(self):
        self.patch(shutil, "copyfile").side_effect = IOError("whatever")
        self.assertContentFailsWithMessage(
            OPTIONS_FILE, "Failed to make a backup"
        )

    def test_removes_existing_forwarders_config(self):
        options_file = self.make_file(contents=OPTIONS_FILE_WITH_FORWARDERS)
        self.run_command("--config-path", options_file)

        # Check that the file was re-written without forwarders (since
        # that's now in the included file).
        options = read_isc_file(options_file)
        self.assertNotIn("forwarders", make_isc_string(options))

    def test_removes_existing_dnssec_validation_config(self):
        options_file = self.make_file(contents=OPTIONS_FILE_WITH_DNSSEC)
        self.run_command("--config-path", options_file)

        # Check that the file was re-written without dnssec-validation (since
        # that's now in the included file).
        options = read_isc_file(options_file)
        self.assertNotIn("dnssec-validation", make_isc_string(options))

    def test_normal_operation(self):
        options_file = self.make_file(contents=OPTIONS_FILE)
        self.run_command("--config-path", options_file)
        expected_path = os.path.join(
            os.path.dirname(options_file),
            "maas",
            MAAS_NAMED_CONF_OPTIONS_INSIDE_NAME,
        )

        # Check that the file was re-written with the include statement.
        options = read_isc_file(options_file)
        self.assertIn(
            'include "%s";' % expected_path, make_isc_string(options)
        )

        # Check that the backup was made.
        options_file_base = os.path.dirname(options_file)
        files = os.listdir(options_file_base)
        self.assertEqual(2, len(files))
        files.remove(os.path.basename(options_file))
        [backup_file] = files
        backup_file = os.path.join(options_file_base, backup_file)
        with open(backup_file, "r") as fh:
            contents = fh.read()
        self.assertIn(OPTIONS_FILE, contents)
