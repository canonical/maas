# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""HTTP server fixture."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "HTTPServerFixture",
    ]

from BaseHTTPServer import HTTPServer
import gzip
from io import BytesIO
import os
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

    def _gzip_compress(self, f):
        gz_out = BytesIO()
        gz = gzip.GzipFile(mode='wb', fileobj=gz_out)
        gz.write(f.read())
        gz.flush()
        gz_out.getvalue()
        return gz_out

    def is_gzip_accepted(self):
        accepted = set()
        for header in self.headers.getallmatchingheaders('Accept-Encoding'):
            # getallmatchingheaders returns the whole line, so first we have to
            # split off the header definition
            _, content = header.split(':', 1)
            content = content.strip()
            # Then, you are allowed to specify a comma separated list of
            # acceptable encodings. You are also allowed to specify
            # 'encoding;q=XXX' to specify what encodings you would prefer.
            # We'll allow it to be set, but just ignore it.
            #   http://www.w3.org/Protocols/rfc2616/rfc2616-sec14.html
            encodings = [encoding.strip().split(';', )[0]
                         for encoding in content.split(',')]
            accepted.update(encodings)
        if 'gzip' in accepted:
            return True
        return False

    # This is a copy & paste and minor modification of
    # SimpleHTTPRequestHandler's send_head code. Because to support
    # Content-Encoding gzip, we have to change what headers get returned (as it
    # affects Content-Length headers.
    def send_head(self):
        """Common code for GET and HEAD commands.

        This sends the response code and MIME headers.

        Return value is either a file object (which has to be copied
        to the outputfile by the caller unless the command was HEAD,
        and must be closed by the caller under all circumstances), or
        None, in which case the caller has nothing further to do.

        """
        path = self.translate_path(self.path)
        f = None
        if os.path.isdir(path):
            if not self.path.endswith('/'):
                # redirect browser - doing basically what apache does
                self.send_response(301)
                self.send_header("Location", self.path + "/")
                self.end_headers()
                return None
            for index in "index.html", "index.htm":
                index = os.path.join(path, index)
                if os.path.exists(index):
                    path = index
                    break
            else:
                return self.list_directory(path)
        ctype = self.guess_type(path)
        try:
            # Always read in binary mode. Opening files in text mode may cause
            # newline translations, making the actual size of the content
            # transmitted *less* than the content-length!
            f = open(path, 'rb')
        except IOError:
            self.send_error(404, "File not found")
            return None
        if self.is_gzip_accepted():
            return self.start_gz_response(ctype, f)
        else:
            return self.start_response(ctype, f)

    def start_gz_response(self, ctype, f):
        self.send_response(200)
        self.send_header("Content-type", ctype)
        self.send_header("Content-Encoding", 'gzip')
        gz_out = self._gzip_compress(f)
        self.send_header("Content-Length", unicode(gz_out.tell()))
        gz_out.seek(0)
        self.end_headers()
        return gz_out

    def start_response(self, ctype, f):
        self.send_response(200)
        self.send_header("Content-type", ctype)
        fs = os.fstat(f.fileno())
        self.send_header("Content-Length", unicode(fs[6]))
        self.send_header("Last-Modified", self.date_time_string(fs.st_mtime))
        self.end_headers()
        return f


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
