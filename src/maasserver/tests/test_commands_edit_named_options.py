# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the edit_named_options command."""


from collections import OrderedDict
from io import StringIO
import os
import shutil
import textwrap

from django.core.management import call_command
from django.core.management.base import CommandError

from maasserver.models import Config
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import get_one
from provisioningserver.dns.commands import edit_named_options
from provisioningserver.dns.config import MAAS_NAMED_CONF_OPTIONS_INSIDE_NAME
from provisioningserver.utils.isc import (
    make_isc_string,
    parse_isc_string,
    read_isc_file,
)

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


class TestEditNamedOptionsCommand(MAASServerTestCase):
    def setUp(self):
        super().setUp()
        self.stdout = StringIO()

    def assertFailsWithMessage(self, config_path, message):
        e = self.assertRaises(
            CommandError,
            call_command,
            "edit_named_options",
            config_path=config_path,
            stdout=self.stdout,
        )
        self.assertIn(message, str(e))

    def assertContentFailsWithMessage(self, content, message):
        options_file = self.make_file(contents=content)
        self.assertFailsWithMessage(options_file, message)
        # The original file must be untouched.
        with open(options_file, "r") as fh:
            self.assertEqual(content, fh.read())

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

    def test_remove_existing_forwarders_config(self):
        options_file = self.make_file(contents=OPTIONS_FILE_WITH_FORWARDERS)
        call_command(
            "edit_named_options", config_path=options_file, stdout=self.stdout
        )

        options = read_isc_file(options_file)
        self.assertNotIn("forwarders", make_isc_string(options))

    def test_removes_existing_forwarders_config_if_migrate_set(self):
        options_file = self.make_file(contents=OPTIONS_FILE_WITH_FORWARDERS)
        call_command(
            "edit_named_options",
            config_path=options_file,
            migrate_conflicting_options=True,
            stdout=self.stdout,
        )

        # Check that the file was re-written without forwarders (since
        # that's now in the included file).
        options = read_isc_file(options_file)
        self.assertNotIn("forwarders", make_isc_string(options))

    def test_removes_existing_dnssec_validation_config(self):
        options_file = self.make_file(contents=OPTIONS_FILE_WITH_DNSSEC)
        call_command(
            "edit_named_options", config_path=options_file, stdout=self.stdout
        )

        # Check that the file was re-written without dnssec-validation (since
        # that's now in the included file).
        options = read_isc_file(options_file)
        self.assertNotIn("dnssec-validation", make_isc_string(options))

    def test_removes_existing_dnssec_validation_config_if_migration_set(self):
        options_file = self.make_file(contents=OPTIONS_FILE_WITH_DNSSEC)
        call_command(
            "edit_named_options",
            config_path=options_file,
            migrate_conflicting_options=True,
            stdout=self.stdout,
        )

        # Check that the file was re-written without dnssec-validation (since
        # that's now in the included file).
        options = read_isc_file(options_file)
        self.assertNotIn("dnssec-validation", make_isc_string(options))

    def test_normal_operation(self):
        options_file = self.make_file(contents=OPTIONS_FILE)
        call_command(
            "edit_named_options", config_path=options_file, stdout=self.stdout
        )
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
            self.assertEqual(fh.read(), OPTIONS_FILE)

    def test_migrates_bind_config_to_database(self):
        options_file = self.make_file(
            contents=OPTIONS_FILE_WITH_FORWARDERS_AND_DNSSEC
        )
        call_command(
            "edit_named_options",
            config_path=options_file,
            migrate_conflicting_options=True,
            stdout=self.stdout,
        )

        upstream_dns = get_one(Config.objects.filter(name="upstream_dns"))
        self.assertEqual(
            {"192.168.1.1", "192.168.1.2"},
            set(upstream_dns.value.split()),
        )

        dnssec_validation = get_one(
            Config.objects.filter(name="dnssec_validation")
        )
        self.assertEqual(dnssec_validation.value, "no")

    def test_migrate_combines_with_existing_forwarders(self):
        options_file = self.make_file(
            contents=OPTIONS_FILE_WITH_FORWARDERS_AND_DNSSEC
        )
        call_command(
            "edit_named_options",
            config_path=options_file,
            migrate_conflicting_options=True,
            stdout=self.stdout,
        )

        upstream_dns = get_one(Config.objects.filter(name="upstream_dns"))
        self.assertEqual(
            OrderedDict.fromkeys(["192.168.1.1", "192.168.1.2"]),
            OrderedDict.fromkeys(upstream_dns.value.split()),
        )

        dnssec_validation = get_one(
            Config.objects.filter(name="dnssec_validation")
        )
        self.assertEqual(dnssec_validation.value, "no")

        options_file = self.make_file(
            contents=OPTIONS_FILE_WITH_EXTRA_AND_DUP_FORWARDER
        )

        call_command(
            "edit_named_options",
            config_path=options_file,
            migrate_conflicting_options=True,
            stdout=self.stdout,
        )

        upstream_dns = get_one(Config.objects.filter(name="upstream_dns"))
        self.assertEqual(
            OrderedDict.fromkeys(
                ["192.168.1.1", "192.168.1.2", "192.168.1.3"]
            ),
            OrderedDict.fromkeys(upstream_dns.value.split()),
        )

    def test_dry_run_migrates_nothing_and_prints_config(self):
        options_file = self.make_file(
            contents=OPTIONS_FILE_WITH_FORWARDERS_AND_DNSSEC
        )
        call_command(
            "edit_named_options",
            config_path=options_file,
            migrate_conflicting_options=True,
            dry_run=True,
            stdout=self.stdout,
        )

        upstream_dns = get_one(Config.objects.filter(name="upstream_dns"))
        self.assertIsNone(upstream_dns)
        dnssec_validation = get_one(
            Config.objects.filter(name="dnssec_validation")
        )
        self.assertIsNone(dnssec_validation)

        # Check that a proper configuration was written to stdout.
        config = parse_isc_string(self.stdout.getvalue())
        self.assertIsNotNone(config)

    def test_repeat_migrations_migrate_nothing(self):
        options_file = self.make_file(
            contents=OPTIONS_FILE_WITH_FORWARDERS_AND_DNSSEC
        )
        backup_mock = self.patch(edit_named_options, "back_up_existing_file")

        call_command(
            "edit_named_options",
            config_path=options_file,
            migrate_conflicting_options=True,
            stdout=self.stdout,
        )

        self.assertTrue(backup_mock.called)
        backup_mock.reset_mock()

        write_mock = self.patch(
            edit_named_options, "write_new_named_conf_options"
        )

        call_command(
            "edit_named_options",
            config_path=options_file,
            migrate_conflicting_options=True,
            stdout=self.stdout,
        )

        self.assertFalse(backup_mock.called)
        self.assertFalse(write_mock.called)

    def test_repeat_forced_migrations_write_file_anyway(self):
        options_file = self.make_file(
            contents=OPTIONS_FILE_WITH_FORWARDERS_AND_DNSSEC
        )
        backup_mock = self.patch(edit_named_options, "back_up_existing_file")

        call_command(
            "edit_named_options",
            config_path=options_file,
            migrate_conflicting_options=True,
            stdout=self.stdout,
        )

        self.assertTrue(backup_mock.called)
        backup_mock.reset_mock()

        write_mock = self.patch(
            edit_named_options, "write_new_named_conf_options"
        )

        call_command(
            "edit_named_options",
            config_path=options_file,
            migrate_conflicting_options=True,
            force=True,
            stdout=self.stdout,
        )

        self.assertTrue(backup_mock.called)
        self.assertTrue(write_mock.called)
