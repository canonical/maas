# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Run YUI3 unit tests with SST (http://testutils.org/sst/)."""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'TestYUIUnitTests',
    ]

import BaseHTTPServer
import json
import logging
import os
import SimpleHTTPServer
import SocketServer
import threading

from fixtures import Fixture
from pyvirtualdisplay import Display
from sst.actions import (
    assert_text,
    get_element,
    go_to,
    set_base_url,
    start,
    stop,
    wait_for,
    )
from testtools import TestCase

# Base path where the HTML files will be searched.
BASE_PATH = 'src/maasserver/static/js/tests/'


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


class ThreadingHTTPServer(SocketServer.ThreadingMixIn,
                          BaseHTTPServer.HTTPServer):
    """A simple HTTP Server that whill run in it's own thread."""


class SilentHTTPRequestHandler(SimpleHTTPServer.SimpleHTTPRequestHandler):
    # SimpleHTTPRequestHandler logs to stdout: silence it.
    log_request = lambda *args, **kwargs: None
    log_error = lambda *args, **kwargs: None


class StaticServerFixture(Fixture):
    """Setup an HTTP server that will serve static files.

    This is only required because SST forces us to request urls that start
    with 'http://' (and thus does not allow us to use urls starting with
    'file:///').
    """

    # Port used by the temporary http server used for testing.
    TESTING_HTTP_PORT = 18463

    port = TESTING_HTTP_PORT

    def __init__(self):
        self.server = ThreadingHTTPServer(
            ('localhost', self.port), SilentHTTPRequestHandler)
        self.server.daemon = True
        self.server_thread = threading.Thread(target=self.server.serve_forever)

    def setUp(self):
        super(StaticServerFixture, self).setUp()
        self.server_thread.start()
        self.addCleanup(self.server.shutdown)


class SSTFixture(Fixture):
    """Setup a javascript-enabled testing browser instance with SST."""

    logger_names = ['selenium.webdriver.remote.remote_connection']

    # Parameters used by SST for testing.
    BROWSER_TYPE = 'Firefox'
    BROWSER_VERSION = ''
    BROWSER_PLATFORM = 'ANY'

    def setUp(self):
        super(SSTFixture, self).setUp()
        start(
              self.BROWSER_TYPE, self.BROWSER_VERSION, self.BROWSER_PLATFORM,
              session_name=None, javascript_disabled=False,
              assume_trusted_cert_issuer=False,
              webdriver_remote=None)
        self.useFixture(LoggerSilencerFixture(self.logger_names))
        self.addCleanup(stop)


class TestYUIUnitTests(TestCase):

    def setUp(self):
        super(TestYUIUnitTests, self).setUp()
        self.useFixture(DisplayFixture())
        self.port = self.useFixture(StaticServerFixture()).port
        self.useFixture(SSTFixture())

    def _get_failed_tests_message(self, results):
        """Return a readable error message with the list of the failed tests.

        Given a YUI3 results_ json object, return a readable error message.

        .. _results: http://yuilibrary.com/yui/docs/test/
        """
        result = []
        suites = [item for item in results.values() if isinstance(item, dict)]
        for suite in suites:
            if suite['failed'] != 0:
                tests = [item for item in suite.values()
                         if isinstance(item, dict)]
                for test in tests:
                    if test['result'] != 'pass':
                        result.append('\n%s.%s: %s\n' % (
                            suite['name'], test['name'], test['message']))
        return ''.join(result)

    def test_YUI3_unit_tests(self):
        set_base_url('http://localhost:%d' % self.port)
        # Find all the HTML files in BASE_PATH.
        for fname in os.listdir(BASE_PATH):
            if fname.endswith('.html'):
                # Load the page and then wait for #suite to contain
                # 'done'.  Read the results in '#test_results'.
                go_to("%s%s" % (BASE_PATH, fname))
                wait_for(assert_text, 'suite', 'done')
                results = json.loads(get_element(id='test_results').text)
                if results['failed'] != 0:
                    raise AssertionError(
                        '%d test(s) failed.\n%s' % (
                            results['failed'],
                            self._get_failed_tests_message(results)))
