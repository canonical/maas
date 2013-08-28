# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test custom commissioning scripts."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from inspect import getsource
from io import BytesIO
from math import (
    ceil,
    floor,
    )
import os.path
from random import randint
import subprocess
from subprocess import (
    CalledProcessError,
    check_output,
    STDOUT,
    )
import tarfile
from textwrap import dedent
import time

from maasserver.testing.factory import factory
from maasserver.testing.testcase import TestCase
from maastesting.matchers import ContainsAll
from maastesting.utils import sample_binary_data
from metadataserver.fields import Bin
from metadataserver.models import (
    CommissioningScript,
    commissioningscript as cs_module,
    )
from metadataserver.models.commissioningscript import (
    ARCHIVE_PREFIX,
    make_function_call_script,
    )
from mock import call
from testtools.content import text_content


def open_tarfile(content):
    """Open tar file from raw binary data."""
    return tarfile.open(fileobj=BytesIO(content))


def make_script_name(base_name=None, number=None):
    """Make up a name for a commissioning script."""
    if base_name is None:
        base_name = 'script'
    if number is None:
        number = randint(0, 99)
    return factory.make_name(
        '%0.2d-%s' % (number, factory.make_name(base_name)))


class TestCommissioningScriptManager(TestCase):

    def test_get_archive_wraps_scripts_in_tar(self):
        script = factory.make_commissioning_script()
        path = os.path.join(ARCHIVE_PREFIX, script.name)
        archive = open_tarfile(CommissioningScript.objects.get_archive())
        self.assertTrue(archive.getmember(path).isfile())
        self.assertEqual(script.content, archive.extractfile(path).read())

    def test_get_archive_wraps_all_scripts(self):
        scripts = {factory.make_commissioning_script() for counter in range(3)}
        archive = open_tarfile(CommissioningScript.objects.get_archive())
        self.assertThat(
            archive.getnames(),
            ContainsAll({
                os.path.join(ARCHIVE_PREFIX, script.name)
                for script in scripts
                }))

    def test_get_archive_supports_binary_scripts(self):
        script = factory.make_commissioning_script(content=sample_binary_data)
        path = os.path.join(ARCHIVE_PREFIX, script.name)
        archive = open_tarfile(CommissioningScript.objects.get_archive())
        self.assertEqual(script.content, archive.extractfile(path).read())

    def test_get_archive_includes_builtin_scripts(self):
        name = factory.make_name('00-maas')
        path = os.path.join(ARCHIVE_PREFIX, name)
        content = factory.getRandomString().encode('ascii')
        data = dict(name=name, content=content, hook='hook')
        self.patch(cs_module, 'BUILTIN_COMMISSIONING_SCRIPTS', {name: data})
        archive = open_tarfile(CommissioningScript.objects.get_archive())
        self.assertIn(path, archive.getnames())
        self.assertEqual(content, archive.extractfile(path).read())

    def test_get_archive_sets_sensible_mode(self):
        for counter in range(3):
            factory.make_commissioning_script()
        archive = open_tarfile(CommissioningScript.objects.get_archive())
        self.assertEqual({0755}, {info.mode for info in archive.getmembers()})

    def test_get_archive_initializes_file_timestamps(self):
        # The mtime on a file inside the tarball is reasonable.
        # It would otherwise default to the Epoch, and GNU tar warns
        # annoyingly about improbably old files.
        start_time = floor(time.time())
        script = factory.make_commissioning_script()
        path = os.path.join(ARCHIVE_PREFIX, script.name)
        archive = open_tarfile(CommissioningScript.objects.get_archive())
        timestamp = archive.getmember(path).mtime
        end_time = ceil(time.time())
        self.assertGreaterEqual(timestamp, start_time)
        self.assertLessEqual(timestamp, end_time)


class TestCommissioningScript(TestCase):

    def test_scripts_may_be_binary(self):
        name = make_script_name()
        CommissioningScript.objects.create(
            name=name, content=Bin(sample_binary_data))
        stored_script = CommissioningScript.objects.get(name=name)
        self.assertEqual(sample_binary_data, stored_script.content)


class TestMakeFunctionCallScript(TestCase):

    def run_script(self, script):
        script_filename = self.make_file("test.py", script)
        os.chmod(script_filename, 0700)
        try:
            return check_output((script_filename,), stderr=STDOUT)
        except CalledProcessError as error:
            self.addDetail("output", text_content(error.output))
            raise

    def test_basic(self):
        def example_function():
            print("Hello, World!", end="")
        script = make_function_call_script(example_function)
        self.assertEqual(b"Hello, World!", self.run_script(script))

    def test_positional_args_get_passed_through(self):
        def example_function(a, b):
            print("a=%s, b=%d" % (a, b), end="")
        script = make_function_call_script(example_function, "foo", 12345)
        self.assertEqual(b"a=foo, b=12345", self.run_script(script))

    def test_keyword_args_get_passed_through(self):
        def example_function(a, b):
            print("a=%s, b=%d" % (a, b), end="")
        script = make_function_call_script(example_function, a="foo", b=12345)
        self.assertEqual(b"a=foo, b=12345", self.run_script(script))

    def test_positional_and_keyword_args_get_passed_through(self):
        def example_function(a, b):
            print("a=%s, b=%d" % (a, b), end="")
        script = make_function_call_script(example_function, "foo", b=12345)
        self.assertEqual(b"a=foo, b=12345", self.run_script(script))

    def test_non_ascii_positional_args_are_passed_without_corruption(self):
        def example_function(text):
            print(repr(text), end="")
        script = make_function_call_script(example_function, "abc\u1234")
        self.assertEqual(b"u'abc\\u1234'", self.run_script(script))

    def test_non_ascii_keyword_args_are_passed_without_corruption(self):
        def example_function(text):
            print(repr(text), end="")
        script = make_function_call_script(example_function, text="abc\u1234")
        self.assertEqual(b"u'abc\\u1234'", self.run_script(script))

    def test_structured_arguments_are_passed_though_too(self):
        # Anything that can be JSON serialized can be passed.
        def example_function(arg):
            if arg == {"123": "foo", "bar": [4, 5, 6]}:
                print("Equal")
            else:
                print("Unequal, got %s" % repr(arg))
        script = make_function_call_script(
            example_function, {"123": "foo", "bar": [4, 5, 6]})
        self.assertEqual(b"Equal\n", self.run_script(script))


def isolate_function(function):
    """Recompile the given function in an empty namespace."""
    source = dedent(getsource(function))
    modcode = compile(source, "lldpd.py", "exec")
    namespace = {}
    exec(modcode, namespace)
    return namespace[function.__name__]


class TestLLDPScripts(TestCase):

    def test_install_script_installs_configures_and_restarts(self):
        config_file = self.make_file("config", "# ...")
        check_call = self.patch(subprocess, "check_call")
        lldpd_install = isolate_function(cs_module.lldpd_install)
        lldpd_install(config_file)
        # lldpd is installed and restarted.
        self.assertEqual(
            check_call.call_args_list,
            [call(("apt-get", "install", "--yes", "lldpd")),
             call(("service", "lldpd", "restart"))])
        # lldpd's config was updated to include an updated DAEMON_ARGS
        # setting. Note that the new comment is on a new line, and
        # does not interfere with existing config.
        config_expected = dedent("""\
            # ...
            # Configured by MAAS:
            DAEMON_ARGS="-c -f -s -e -r"
            """).encode("ascii")
        with open(config_file, "rb") as fd:
            config_observed = fd.read()
        self.assertEqual(config_expected, config_observed)

    def test_wait_script_waits_for_lldpd(self):
        self.patch(os.path, "getmtime").return_value = 10.65
        self.patch(time, "time").return_value = 14.12
        self.patch(time, "sleep")
        reference_file = self.make_file("reference")
        time_delay = 8.98  # seconds
        lldpd_wait = isolate_function(cs_module.lldpd_wait)
        lldpd_wait(reference_file, time_delay)
        # lldpd_wait checks the mtime of the reference file,
        os.path.getmtime.assert_called_once_with(reference_file)
        # and gets the current time,
        time.time.assert_called_once_with()
        # then sleeps until time_delay seconds has passed since the
        # mtime of the reference file.
        time.sleep.assert_called_once_with(
            os.path.getmtime.return_value + time_delay -
            time.time.return_value)

    def test_capture_calls_lldpdctl(self):
        check_call = self.patch(subprocess, "check_call")
        lldpd_capture = isolate_function(cs_module.lldpd_capture)
        lldpd_capture()
        self.assertEqual(
            check_call.call_args_list,
            [call(("lldpctl", "-f", "xml"))])
