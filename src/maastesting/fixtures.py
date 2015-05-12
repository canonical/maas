# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Miscellaneous fixtures, here until they find a better home."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
)

str = None

__metaclass__ = type
__all__ = [
    "CaptureStandardIO",
    "DisplayFixture",
    "LoggerSilencerFixture",
    "ProxiesDisabledFixture",
    "SeleniumFixture",
    "TempDirectory",
]

import __builtin__
import codecs
from io import BytesIO
import logging
import os
from subprocess import (
    CalledProcessError,
    PIPE,
    Popen,
)
import sys

import fixtures
from fixtures import (
    EnvironmentVariableFixture,
    Fixture,
)
from testtools.monkey import MonkeyPatcher
from twisted.python.reflect import namedObject


class ImportErrorFixture(Fixture):
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
                    raise ImportError("ImportErrorFixture raising ImportError "
                                      "exception on targeted import: %s.%s" % (
                                          self.module_name, self.sub_name))

            return self.__real_import(name, *import_args, **kwargs)

        self.__real_import = __builtin__.__import__
        __builtin__.__import__ = mock_import

        self.addCleanup(setattr, __builtin__, "__import__", self.__real_import)


class LoggerSilencerFixture(Fixture):
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


class DisplayFixture(Fixture):
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
            "xvfb-run", "--server-args", args, "--auto-servernum", "--",
            "bash", "-c", "echo $DISPLAY && exec cat",
        )

    def setUp(self):
        super(DisplayFixture, self).setUp()
        self.process = Popen(self.command, stdin=PIPE, stdout=PIPE)
        self.display = self.process.stdout.readline().strip()
        if not self.display or self.process.poll() is not None:
            raise CalledProcessError(self.process.returncode, self.command)
        self.useFixture(EnvironmentVariableFixture("DISPLAY", self.display))
        self.addCleanup(self.shutdown)

    def shutdown(self):
        self.process.stdin.close()
        if self.process.wait() != 0:
            raise CalledProcessError(self.process.returncode, self.command)


class SeleniumFixture(Fixture):
    """Set-up a JavaScript-enabled testing browser instance."""

    # browser-name -> (driver-name, driver-args)
    browsers = {
        "Chrome": (
            b"selenium.webdriver.Chrome",
            ("/usr/lib/chromium-browser/chromedriver",),
        ),
        "Firefox": (
            b"selenium.webdriver.Firefox",
            (),
        ),
        "PhantomJS": (
            b"selenium.webdriver.PhantomJS",
            (),
        ),
    }

    logger_names = ['selenium.webdriver.remote.remote_connection']

    def __init__(self, browser_name):
        super(SeleniumFixture, self).__init__()
        if browser_name in self.browsers:
            driver, driver_args = self.browsers[browser_name]
            self.driver = namedObject(driver)
            self.driver_args = driver_args
        else:
            raise ValueError("Unrecognised browser: %s" % (browser_name,))

    def setUp(self):
        super(SeleniumFixture, self).setUp()
        self.browser = self.driver(*self.driver_args)
        self.useFixture(LoggerSilencerFixture(self.logger_names))
        self.addCleanup(self.browser.quit)


class ProxiesDisabledFixture(Fixture):
    """Disables all HTTP/HTTPS proxies set in the environment."""

    def setUp(self):
        super(ProxiesDisabledFixture, self).setUp()
        self.useFixture(EnvironmentVariableFixture("http_proxy"))
        self.useFixture(EnvironmentVariableFixture("https_proxy"))


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


class ChromiumWebDriverFixture(Fixture):
    """Starts and starts the selenium Chromium webdriver."""

    def setUp(self):
        super(ChromiumWebDriverFixture, self).setUp()
        # Import late to avoid hard dependency.
        from selenium.webdriver.chrome.service import Service as ChromeService
        service = ChromeService(
            "/usr/lib/chromium-browser/chromedriver", 4444)

        # Set the LD_LIBRARY_PATH so the chrome driver can find the required
        # libraries.
        self.useFixture(EnvironmentVariableFixture(
            "LD_LIBRARY_PATH", "/usr/lib/chromium-browser/libs"))
        service.start()

        # Stop service on cleanup.
        self.addCleanup(service.stop)


class CaptureStandardIO(Fixture):
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
        # Create new buffers.
        self._buf_in = BytesIO()
        self._buf_out = BytesIO()
        self._buf_err = BytesIO()

    def setUp(self):
        super(CaptureStandardIO, self).setUp()
        self.patcher = MonkeyPatcher()
        self.addCleanup(self.patcher.restore)
        # Convenience.
        reader = self.codec.streamreader
        writer = self.codec.streamwriter
        # Patch sys.std* and self.std*.
        self._addStream("stdin", reader(self._buf_in))
        self._addStream("stdout", writer(self._buf_out))
        self._addStream("stderr", writer(self._buf_err))
        self.patcher.patch()

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
