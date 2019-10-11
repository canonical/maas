# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Miscellaneous fixtures, here until they find a better home."""

__all__ = [
    "CaptureStandardIO",
    "DetectLeakedFileDescriptors",
    "DisplayFixture",
    "LoggerSilencerFixture",
    "ProxiesDisabledFixture",
    "TempDirectory",
]

import builtins
import codecs
from errno import ENOENT
from io import BytesIO, TextIOWrapper
import logging
import os
from pathlib import Path
from subprocess import CalledProcessError, PIPE, Popen
import sys

import fixtures
from fixtures import EnvironmentVariable
from maastesting import root
from testtools.monkey import MonkeyPatcher


class ImportErrorFixture(fixtures.Fixture):
    """Fixture to generate an artificial ImportError when the
    interpreter would otherwise successfully import the given module.

    While this fixture is within context, any import of the form:

        from <module_name> import <sub_name>

    will raise an ImportError.

    :param module_name: name of the module to import from
    :param sub_name: submodule to import from the module named <module_name>
    """

    def __init__(self, module_name, sub_name):
        super(ImportErrorFixture, self).__init__()
        self.module_name = module_name
        self.sub_name = sub_name

    def setUp(self):
        super(ImportErrorFixture, self).setUp()

        def mock_import(name, *import_args, **kwargs):
            if name == self.module_name:
                module_list = import_args[2]
                if self.sub_name in module_list:
                    raise ImportError(
                        "ImportErrorFixture raising ImportError "
                        "exception on targeted import: %s.%s"
                        % (self.module_name, self.sub_name)
                    )

            return self.__real_import(name, *import_args, **kwargs)

        self.__real_import = builtins.__import__
        builtins.__import__ = mock_import

        self.addCleanup(setattr, builtins, "__import__", self.__real_import)


class LoggerSilencerFixture(fixtures.Fixture):
    """Fixture to change the log level of loggers.

    All the loggers with names self.logger_names will have their log level
    changed to self.level (logging.ERROR by default).
    """

    def __init__(self, names, level=logging.ERROR):
        super(LoggerSilencerFixture, self).__init__()
        self.names = names
        self.level = level

    def setUp(self):
        super(LoggerSilencerFixture, self).setUp()
        for name in self.names:
            logger = logging.getLogger(name)
            self.addCleanup(logger.setLevel, logger.level)
            logger.setLevel(self.level)


class DisplayFixture(fixtures.Fixture):
    """Fixture to create a virtual display with `xvfb-run`.

    This will set the ``DISPLAY`` environment variable once it's up and
    running (and reset it when it shuts down).
    """

    def __init__(self, size=(1280, 1024), depth=24):
        super(DisplayFixture, self).__init__()
        self.width, self.height = size
        self.depth = depth

    @property
    def command(self):
        """The command this fixture will start.

        ``xvfb-run`` is the executable used, to which the following arguments
        are passed:

          ``--server-args=``
            ``-ac`` disables host-based access control mechanisms. See
              Xserver(1).
            ``-screen`` forces a screen configuration. At the time of writing
               there is some disagreement between xvfb-run(1) and Xvfb(1)
               about what the default is.

          ``--auto-servernum``
            Try to get a free server number, starting at 99. See xvfb-run(1).

        ``xvfb-run`` is asked to chain to ``bash``, which echos the
        ``DISPLAY`` environment variable and execs ``cat``. This lets us shut
        down the framebuffer simply by closing the process's stdin.
        """
        spec = "{self.width}x{self.height}x{self.depth}".format(self=self)
        args = "-ac -screen 0 %s" % spec
        return (
            "xvfb-run",
            "--server-args",
            args,
            "--auto-servernum",
            "--",
            "bash",
            "-c",
            "echo $DISPLAY && exec cat",
        )

    def setUp(self):
        super(DisplayFixture, self).setUp()
        self.process = Popen(self.command, stdin=PIPE, stdout=PIPE)
        self.display = self.process.stdout.readline().decode("ascii").strip()
        if not self.display or self.process.poll() is not None:
            raise CalledProcessError(self.process.returncode, self.command)
        self.useFixture(EnvironmentVariable("DISPLAY", self.display))
        self.addCleanup(self.shutdown)

    def shutdown(self):
        self.process.stdin.close()
        if self.process.wait() != 0:
            raise CalledProcessError(self.process.returncode, self.command)


class ProxiesDisabledFixture(fixtures.Fixture):
    """Disables all HTTP/HTTPS proxies set in the environment."""

    def setUp(self):
        super(ProxiesDisabledFixture, self).setUp()
        self.useFixture(EnvironmentVariable("http_proxy"))
        self.useFixture(EnvironmentVariable("https_proxy"))


class TempDirectory(fixtures.TempDir):
    """Create a temporary directory, ensuring Unicode paths."""

    def setUp(self):
        super(TempDirectory, self).setUp()
        if isinstance(self.path, bytes):
            encoding = sys.getfilesystemencoding()
            self.path = self.path.decode(encoding)


class TempWDFixture(TempDirectory):
    """Change the current working directory into a temp dir.

    This will restore the original WD and delete the temp directory on cleanup.
    """

    def setUp(self):
        cwd = os.getcwd()
        super(TempWDFixture, self).setUp()
        self.addCleanup(os.chdir, cwd)
        os.chdir(self.path)


class ChromiumWebDriverFixture(fixtures.Fixture):
    """Starts and starts the selenium Chromium webdriver."""

    def setUp(self):
        super(ChromiumWebDriverFixture, self).setUp()
        # Import late to avoid hard dependency.
        from selenium.webdriver.chrome.service import Service as ChromeService

        service = ChromeService("/usr/lib/chromium-browser/chromedriver", 4444)

        # Set the LD_LIBRARY_PATH so the chrome driver can find the required
        # libraries.
        self.useFixture(
            EnvironmentVariable(
                "LD_LIBRARY_PATH", "/usr/lib/chromium-browser/libs"
            )
        )
        service.start()

        # Stop service on cleanup.
        self.addCleanup(service.stop)


class CaptureStandardIO(fixtures.Fixture):
    """Capture stdin, stdout, and stderr.

    Reading from `sys.stdin` will yield *unicode* strings, much like the
    default in Python 3. This differs from the usual behaviour in Python 2, so
    beware.

    Writing unicode strings to `sys.stdout` or `sys.stderr` will work; they'll
    be encoded with the `encoding` chosen when creating this fixture.

    `addInput(...)` should be used to prepare more input to be read.

    The `output` and `error` properties can be used to obtain what's been
    written to stdout and stderr.

    The buffers used internally have the same lifetime as the fixture
    *instance* itself, so the `output`, and `error` properties remain useful
    even after the fixture has been cleaned-up, and there's no need to capture
    them before exiting.

    However, `clearInput()`, `clearOutput()`, `clearError()`, and `clearAll()`
    can be used to truncate the buffers during this fixture's lifetime.
    """

    stdin = None
    stdout = None
    stderr = None

    def __init__(self, encoding="utf-8"):
        super(CaptureStandardIO, self).__init__()
        self.codec = codecs.lookup(encoding)
        self.encoding = encoding
        # Create new buffers.
        self._buf_in = BytesIO()
        self._buf_out = BytesIO()
        self._buf_err = BytesIO()

    def setUp(self):
        super(CaptureStandardIO, self).setUp()
        self.patcher = MonkeyPatcher()
        self.addCleanup(self.patcher.restore)
        # Patch sys.std* and self.std*. Use TextIOWrapper to provide an
        # identical API to the "real" stdin, stdout, and stderr objects.
        self._addStream("stdin", self._wrapStream(self._buf_in))
        self._addStream("stdout", self._wrapStream(self._buf_out))
        self._addStream("stderr", self._wrapStream(self._buf_err))
        self.patcher.patch()

    def _wrapStream(self, stream):
        return TextIOWrapper(
            stream, encoding=self.encoding, write_through=True
        )

    def _addStream(self, name, stream):
        self.patcher.add_patch(self, name, stream)
        self.patcher.add_patch(sys, name, stream)

    def addInput(self, data):
        """Add input to be read later, as a unicode string."""
        position = self._buf_in.tell()
        stream = self.codec.streamwriter(self._buf_in)
        try:
            self._buf_in.seek(0, 2)
            stream.write(data)
        finally:
            self._buf_in.seek(position)

    def getInput(self):
        """The input remaining to be read, as a unicode string."""
        position = self._buf_in.tell()
        if self.stdin is None:
            stream = self.codec.streamreader(self._buf_in)
        else:
            stream = self.stdin
        try:
            return stream.read()
        finally:
            self._buf_in.seek(position)

    def getOutput(self):
        """The output written thus far, as a unicode string."""
        if self.stdout is not None:
            self.stdout.flush()
        output_bytes = self._buf_out.getvalue()
        output_string, _ = self.codec.decode(output_bytes)
        return output_string

    def getError(self):
        """The error written thus far, as a unicode string."""
        if self.stderr is not None:
            self.stderr.flush()
        error_bytes = self._buf_err.getvalue()
        error_string, _ = self.codec.decode(error_bytes)
        return error_string

    def clearInput(self):
        """Truncate the input buffer."""
        self._buf_in.seek(0, 0)
        self._buf_in.truncate()
        if self.stdin is not None:
            self.stdin.seek(0, 0)

    def clearOutput(self):
        """Truncate the output buffer."""
        self._buf_out.seek(0, 0)
        self._buf_out.truncate()
        if self.stdout is not None:
            self.stdout.seek(0, 0)

    def clearError(self):
        """Truncate the error buffer."""
        self._buf_err.seek(0, 0)
        self._buf_err.truncate()
        if self.stderr is not None:
            self.stderr.seek(0, 0)

    def clearAll(self):
        """Truncate all buffers."""
        self.clearInput()
        self.clearOutput()
        self.clearError()


class DetectLeakedFileDescriptors(fixtures.Fixture):
    """Detect FDs that have leaked during the lifetime of this fixture.

    Raises `AssertionError` with details if anything has leaked.

    It does this by referring to the listing of ``/proc/self/fd``, a "magic"
    directory that the kernel populates with details of open file-descriptors.
    It captures this list during fixture set-up and compares against it at
    fixture tear-down.
    """

    def setUp(self):
        super(DetectLeakedFileDescriptors, self).setUp()
        self.fdpath = "/proc/%d/fd" % os.getpid()
        self.addCleanup(self.check, os.listdir(self.fdpath))

    def check(self, fds_ref):
        fds_now = os.listdir(self.fdpath)
        fds_new = {}

        for fd in set(fds_now) - set(fds_ref):
            try:
                fds_new[fd] = os.readlink(os.path.join(self.fdpath, fd))
            except OSError as error:
                if error.errno == ENOENT:
                    # The FD has been closed since listing the directory,
                    # presumably by another thread in this process. Twisted's
                    # reactor is likely. In any case, this is not a leak,
                    # though it may indicate a somewhat racy test.
                    pass
                else:
                    raise

        if len(fds_new) != 0:
            message = ["File descriptor(s) leaked:"]
            message.extend(
                "* %s --> %s" % (fd, desc) for (fd, desc) in fds_new.items()
            )
            raise AssertionError("\n".join(message))


class MAASRootFixture(fixtures.Fixture):
    """Create a new, pristine, `MAAS_ROOT` in a temporary location.

    Also updates `MAAS_ROOT` in the environment to point to this new location.
    """

    def _setUp(self):
        skel = Path(root).joinpath("run-skel")
        if skel.is_dir():
            self.path = self.useFixture(TempDirectory()).join("run")
            # Work only in `run`; reference the old $MAAS_ROOT.
            etc = Path(self.path).joinpath("etc")
            # Create and populate $MAAS_ROOT/run/etc/{chrony,c/chrony.conf}.
            # The `.keep` file is not strictly necessary, but it's created for
            # consistency with the source tree's `run` directory.
            ntp = etc.joinpath("chrony")
            ntp.mkdir(parents=True)
            ntp.joinpath(".keep").touch()
            ntp_conf = ntp.joinpath("chrony.conf")
            ntp_conf.write_bytes(
                skel.joinpath("etc", "chrony", "chrony.conf").read_bytes()
            )
            # Create and populate $MAAS_ROOT/run/etc/maas.
            maas = etc.joinpath("maas")
            maas.mkdir(parents=True)
            maas.joinpath("drivers.yaml").symlink_to(
                skel.joinpath("etc", "maas", "drivers.yaml").resolve()
            )
            maas.joinpath("templates").mkdir()
            # Update the environment.
            self.useFixture(EnvironmentVariable("MAAS_ROOT", self.path))
        else:
            raise NotADirectoryError(
                "Skeleton MAAS_ROOT (%s) is not a directory." % skel
            )
