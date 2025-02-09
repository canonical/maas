# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""HTTP server fixture."""

import gzip
from http import HTTPStatus
from http.server import HTTPServer, SimpleHTTPRequestHandler
from io import BytesIO
import os
from shutil import copyfileobj
from socketserver import ThreadingMixIn
import threading
import urllib

from fixtures import Fixture


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    """A simple HTTP server that will run in its own thread."""


def gzip_compress(f):
    gz_out = BytesIO()
    gz = gzip.GzipFile(mode="wb", fileobj=gz_out)
    copyfileobj(f, gz)
    gz.close()
    return gz_out


class SilentHTTPRequestHandler(SimpleHTTPRequestHandler):
    # SimpleHTTPRequestHandler logs to stdout: silence it.
    def log_request(*args, **kwargs):
        pass

    def log_error(*args, **kwargs):
        pass

    def is_gzip_accepted(self):
        accepted = set()
        for header in self.headers.get_all("Accept-Encoding"):
            # Then, you are allowed to specify a comma separated list of
            # acceptable encodings. You are also allowed to specify
            # 'encoding;q=XXX' to specify what encodings you would prefer.
            # We'll allow it to be set, but just ignore it.
            #   http://www.w3.org/Protocols/rfc2616/rfc2616-sec14.html
            accepted.update(
                encoding.strip().split(";", 1)[0]
                for encoding in header.split(",")
            )
        return "gzip" in accepted

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
            parts = urllib.parse.urlsplit(self.path)
            if not parts.path.endswith("/"):
                # redirect browser - doing basically what apache does
                self.send_response(HTTPStatus.MOVED_PERMANENTLY)
                new_parts = (
                    parts[0],
                    parts[1],
                    parts[2] + "/",
                    parts[3],
                    parts[4],
                )
                new_url = urllib.parse.urlunsplit(new_parts)
                self.send_header("Location", new_url)
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
            f = open(path, "rb")
        except OSError:
            self.send_error(HTTPStatus.NOT_FOUND, "File not found")
            return None
        # Customisation starts here:
        if self.is_gzip_accepted():
            return self.start_gz_response(ctype, f)
        else:
            return self.start_response(ctype, f)

    def start_gz_response(self, ctype, f):
        try:
            fs = os.fstat(f.fileno())
            gz_out = gzip_compress(f)
        except Exception:
            f.close()
            raise
        else:
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Encoding", "gzip")
            self.send_header("Content-Length", str(gz_out.tell()))
            mtime = self.date_time_string(fs.st_mtime)
            self.send_header("Last-Modified", mtime)
            self.end_headers()
            gz_out.seek(0)
            return gz_out

    def start_response(self, ctype, f):
        try:
            fs = os.fstat(f.fileno())
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(fs.st_size))
            mtime = self.date_time_string(fs.st_mtime)
            self.send_header("Last-Modified", mtime)
            self.end_headers()
            return f
        except Exception:
            f.close()
            raise


class HTTPServerFixture(Fixture):
    """Bring up a very simple, threaded, web server.

    Files are served from the current working directory and below.
    """

    def __init__(self, host="localhost", port=0):
        super().__init__()
        self.server = ThreadingHTTPServer(
            (host, port), SilentHTTPRequestHandler
        )

    @property
    def url(self):
        return "http://%s:%d/" % self.server.server_address

    def setUp(self):
        super().setUp()
        threading.Thread(target=self.server.serve_forever).start()
        self.addCleanup(self.server.shutdown)
