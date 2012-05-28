# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""HTTP server fixture."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    "HTTPServerFixture",
    ]

from BaseHTTPServer import HTTPServer
from SimpleHTTPServer import SimpleHTTPRequestHandler
from SocketServer import ThreadingMixIn
import threading

from fixtures import Fixture


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    """A simple HTTP server that will run in its own thread."""


class SilentHTTPRequestHandler(SimpleHTTPRequestHandler):
    # SimpleHTTPRequestHandler logs to stdout: silence it.
    log_request = lambda *args, **kwargs: None
    log_error = lambda *args, **kwargs: None


class HTTPServerFixture(Fixture):
    """Bring up a very simple, threaded, web server.

    Files are served from the current working directory and below.
    """

    def __init__(self, host="localhost", port=0):
        super(HTTPServerFixture, self).__init__()
        self.server = ThreadingHTTPServer(
            (host, port), SilentHTTPRequestHandler)

    @property
    def url(self):
        return "http://%s:%d/" % self.server.server_address

    def setUp(self):
        super(HTTPServerFixture, self).setUp()
        threading.Thread(target=self.server.serve_forever).start()
        self.addCleanup(self.server.shutdown)
