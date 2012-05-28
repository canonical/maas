# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Miscellaneous fixtures, here until they find a better home."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    "DisplayFixture",
    "LoggerSilencerFixture",
    "SSTFixture",
    ]

import logging

from fixtures import Fixture
from pyvirtualdisplay import Display
from sst.actions import (
    start,
    stop,
    )


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
    """Fixture to create a virtual display with pyvirtualdisplay.Display."""

    logger_names = ['easyprocess', 'pyvirtualdisplay']

    def __init__(self, visible=False, size=(1280, 1024)):
        super(DisplayFixture, self).__init__()
        self.visible = visible
        self.size = size

    def setUp(self):
        super(DisplayFixture, self).setUp()
        self.useFixture(LoggerSilencerFixture(self.logger_names))
        self.display = Display(
            visible=self.visible, size=self.size)
        self.display.start()
        self.addCleanup(self.display.stop)


class SSTFixture(Fixture):
    """Setup a javascript-enabled testing browser instance with SST."""

    logger_names = ['selenium.webdriver.remote.remote_connection']

    def __init__(self, browser_name):
        self.browser_name = browser_name

    def setUp(self):
        super(SSTFixture, self).setUp()
        start(self.browser_name)
        self.useFixture(LoggerSilencerFixture(self.logger_names))
        self.addCleanup(stop)
