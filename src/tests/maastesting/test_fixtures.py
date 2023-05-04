# Copyright 2012-2016 Canonical Ltd. This software is licensed under the GNU
# Affero General Public License version 3 (see the file LICENSE).

import builtins
from itertools import repeat
import os
import sys
from unittest.mock import call

from fixtures import EnvironmentVariable
from testtools.matchers import Equals, Is, Not, PathExists, SamePath
from testtools.testcase import ExpectedException

from maastesting import dev_root
from maastesting.factory import factory
from maastesting.fixtures import (
    CaptureStandardIO,
    ImportErrorFixture,
    MAASRootFixture,
    ProxiesDisabledFixture,
    TempDirectory,
    TempWDFixture,
)
from maastesting.matchers import MockCallsMatch
from maastesting.testcase import MAASTestCase
from maastesting.utils import sample_binary_data


class TestImportErrorFixture(MAASTestCase):
    """Tests for :class:`TestImportErrorFixture`."""

    def test_import_non_targeted_module_successfull(self):
        self.useFixture(ImportErrorFixture("maastesting", "dev_root"))
        from maastesting import bindir  # noqa

    def test_import_targeted_module_unsuccessfull(self):
        self.useFixture(ImportErrorFixture("maastesting", "dev_root"))
        with ExpectedException(ImportError):
            from maastesting import dev_root  # noqa

    def test_import_restores_original__import__(self):
        __real_import = builtins.__import__
        with ImportErrorFixture("maastesting", "dev_root"):
            self.assertNotEqual(
                __real_import,
                builtins.__import__,
                "ImportErrorFixture did not properly "
                "patch __builtin__.__import__",
            )
        self.assertEqual(
            __real_import,
            builtins.__import__,
            "ImportErrorFixture did not properly restore "
            "the original __builtin__.__import__ upon cleanup",
        )


class TestProxiedDisabledFixture(MAASTestCase):
    """Tests for :class:`ProxiesDisabledFixture`."""

    def test_removes_http_proxy_from_environment(self):
        http_proxy = factory.make_name("http-proxy")
        initial = EnvironmentVariable("http_proxy", http_proxy)
        self.useFixture(initial)
        # On entry, http_proxy is removed from the environment.
        with ProxiesDisabledFixture():
            self.assertNotIn("http_proxy", os.environ)
        # On exit, http_proxy is restored.
        self.assertEqual(http_proxy, os.environ.get("http_proxy"))

    def test_removes_https_proxy_from_environment(self):
        https_proxy = factory.make_name("https-proxy")
        initial = EnvironmentVariable("https_proxy", https_proxy)
        self.useFixture(initial)
        # On entry, https_proxy is removed from the environment.
        with ProxiesDisabledFixture():
            self.assertNotIn("https_proxy", os.environ)
        # On exit, http_proxy is restored.
        self.assertEqual(https_proxy, os.environ.get("https_proxy"))


class TestTempDirectory(MAASTestCase):
    def test_path_is_unicode(self):
        with TempDirectory() as fixture:
            self.assertIsInstance(fixture.path, str)

    def test_path_is_decoded_using_filesystem_encoding(self):
        with TempDirectory() as outer:
            # Create a nested temporary directory from a BYTE path.
            with TempDirectory(outer.path.encode("ascii")) as inner:
                self.assertIsInstance(inner.path, str)


class TestTempWDFixture(MAASTestCase):
    def test_changes_dir_and_cleans_up(self):
        orig_cwd = os.getcwd()
        with TempWDFixture() as temp_wd:
            new_cwd = os.getcwd()
            self.assertTrue(os.path.isdir(temp_wd.path))
            self.assertNotEqual(orig_cwd, new_cwd)
            self.assertEqual(new_cwd, temp_wd.path)
        final_cwd = os.getcwd()
        self.assertEqual(orig_cwd, final_cwd)
        self.assertFalse(os.path.isdir(new_cwd))


class TestCaptureStandardIO(MAASTestCase):
    """Test `CaptureStandardIO`."""

    def test_captures_stdin(self):
        stdin_before = sys.stdin
        with CaptureStandardIO():
            stdin_during = sys.stdin
        stdin_after = sys.stdin

        self.expectThat(stdin_during, Not(Is(stdin_before)))
        self.expectThat(stdin_during, Not(Is(stdin_after)))
        self.expectThat(stdin_after, Is(stdin_before))

    def test_captures_stdout(self):
        stdout_before = sys.stdout
        with CaptureStandardIO():
            stdout_during = sys.stdout
        stdout_after = sys.stdout

        self.expectThat(stdout_during, Not(Is(stdout_before)))
        self.expectThat(stdout_during, Not(Is(stdout_after)))
        self.expectThat(stdout_after, Is(stdout_before))

    def test_captures_stderr(self):
        stderr_before = sys.stderr
        with CaptureStandardIO():
            stderr_during = sys.stderr
        stderr_after = sys.stderr

        self.expectThat(stderr_during, Not(Is(stderr_before)))
        self.expectThat(stderr_during, Not(Is(stderr_after)))
        self.expectThat(stderr_after, Is(stderr_before))

    def test_addInput_feeds_stdin(self):
        text = factory.make_name("text")
        with CaptureStandardIO() as stdio:
            stdio.addInput(text + "111")
            self.expectThat(sys.stdin.read(2), Equals(text[:2]))
            stdio.addInput(text + "222")
            self.expectThat(
                sys.stdin.read(), Equals(text[2:] + "111" + text + "222")
            )

    def test_getInput_returns_data_waiting_to_be_read(self):
        stdio = CaptureStandardIO()
        stdio.addInput("one\ntwo\n")
        with stdio:
            self.expectThat(sys.stdin.readline(), Equals("one\n"))
            self.expectThat(stdio.getInput(), Equals("two\n"))

    def test_getOutput_returns_data_written_to_stdout(self):
        self.assert_getter_returns_data_written_to_stream(
            CaptureStandardIO.getOutput, "stdout"
        )

    def test_getError_returns_data_written_to_stderr(self):
        self.assert_getter_returns_data_written_to_stream(
            CaptureStandardIO.getError, "stderr"
        )

    def assert_getter_returns_data_written_to_stream(self, getter, name):
        stream = self.patch(sys, name)

        before = factory.make_name("before")
        during = factory.make_name("during")
        after = factory.make_name("after")
        end = factory.make_name("end")

        print(before, file=getattr(sys, name), end=end)
        with CaptureStandardIO() as stdio:
            print(during, file=getattr(sys, name), end=end)
        print(after, file=getattr(sys, name), end=end)

        self.expectThat(getter(stdio), Equals(during + end))
        self.expectThat(
            stream.write,
            MockCallsMatch(call(before), call(end), call(after), call(end)),
        )

    def test_clearInput_clears_input(self):
        text = factory.make_name("text")
        with CaptureStandardIO() as stdio:
            stdio.addInput(text + "111")
            sys.stdin.read(2)
            stdio.clearInput()
            self.expectThat(sys.stdin.read(2), Equals(""))

    def test_clearOutput_clears_output(self):
        text = factory.make_name("text")
        with CaptureStandardIO() as stdio:
            sys.stdout.write(text)
            self.expectThat(stdio.getOutput(), Equals(text))
            stdio.clearOutput()
            self.expectThat(stdio.getOutput(), Equals(""))

    def test_clearError_clears_error(self):
        text = factory.make_name("text")
        with CaptureStandardIO() as stdio:
            sys.stderr.write(text)
            self.expectThat(stdio.getError(), Equals(text))
            stdio.clearError()
            self.expectThat(stdio.getError(), Equals(""))

    def test_clearAll_clears_input_output_and_error(self):
        text = factory.make_name("text")
        with CaptureStandardIO() as stdio:
            stdio.addInput(text)
            sys.stdout.write(text)
            sys.stderr.write(text)
            stdio.clearAll()
            self.expectThat(stdio.getInput(), Equals(""))
            self.expectThat(stdio.getOutput(), Equals(""))
            self.expectThat(stdio.getError(), Equals(""))

    def test_non_text_strings_are_rejected_on_stdout(self):
        with CaptureStandardIO():
            error = self.assertRaises(
                TypeError, sys.stdout.write, sample_binary_data
            )
        self.assertDocTestMatches(
            "write() argument must be str, not bytes", str(error)
        )

    def test_non_text_strings_are_rejected_on_stderr(self):
        with CaptureStandardIO():
            error = self.assertRaises(
                TypeError, sys.stderr.write, sample_binary_data
            )
        self.assertDocTestMatches(
            "write() argument must be str, not bytes", str(error)
        )


def listdirs(start):
    """Recursively generate paths for all directories and files in `start`.

    Paths generated are relative to `start`. Symbolic links are followed.
    """
    for dirpath, dirnames, filenames in os.walk(start, followlinks=True):
        dirpath = os.path.relpath(dirpath, start)
        yield from map(os.path.join, repeat(dirpath), dirnames)
        yield from map(os.path.join, repeat(dirpath), filenames)


class TestMAASRootFixture(MAASTestCase):
    """Tests for `MAASRootFixture`."""

    def setUp(self):
        super().setUp()
        self.skel = os.path.join(dev_root, "run-skel")
        self.package_files = os.path.join(dev_root, "package-files")
        self.useFixture(EnvironmentVariable("MAAS_ROOT", "/"))

    def test_creates_populates_and_removes_new_directory(self):
        fixture = MAASRootFixture()
        with fixture:
            self.assertThat(fixture.path, PathExists())
            self.assertThat(fixture.path, Not(SamePath(self.skel)))
            files_expected = set(listdirs(self.skel)) | set(
                listdirs(self.package_files)
            )
            files_observed = set(listdirs(fixture.path))
            self.assertEqual(files_expected, files_observed)
        self.assertThat(fixture.path, Not(PathExists()))

    def test_updates_MAAS_ROOT_in_the_environment(self):
        self.assertThat(os.environ["MAAS_ROOT"], Not(SamePath(self.skel)))
        with MAASRootFixture() as fixture:
            self.assertThat(os.environ["MAAS_ROOT"], SamePath(fixture.path))
        self.assertThat(os.environ["MAAS_ROOT"], Not(SamePath(self.skel)))
