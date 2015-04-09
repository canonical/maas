# Copyright 2012 Canonical Ltd.  This software is licensed under the
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
    "DisplayFixture",
    "LoggerSilencerFixture",
    "ProxiesDisabledFixture",
    "SSTFixture",
    "TempDirectory",
]

import __builtin__
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


class SSTFixture(Fixture):
    """Setup a javascript-enabled testing browser instance with SST."""

    logger_names = ['selenium.webdriver.remote.remote_connection']

    def __init__(self, browser_name):
        self.browser_name = browser_name

    def setUp(self):
        super(SSTFixture, self).setUp()
        # Import late to avoid hard dependency.
        from sst.actions import start, stop
        start(self.browser_name)
        self.useFixture(LoggerSilencerFixture(self.logger_names))
        self.addCleanup(stop)


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
