# Copyright 2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test monkey patches."""

__all__ = []

from twisted import version as twisted_version
from twisted.internet.error import ConnectionLost
from twisted.python.failure import Failure
from twisted.web import http
from twisted.web.test.requesthelper import DummyChannel

from maastesting.testcase import MAASTestCase


class TestTwistedDisconnectPatch(MAASTestCase):
    def test_write_after_connection_lost(self):
        """
        Calling L{Request.write} after L{Request.connectionLost} has been
        called should not throw an exception. L{RuntimeError} will be raised
        when finish is called on the request.

        NOTE: This test is taken from the upstream fix to verify the monkey
              patch: https://github.com/twisted/twisted/commit/169fd1d93b7af06bf0f6893b193ce19970881868
        """
        channel = DummyChannel()
        req = http.Request(channel, False)
        req.connectionLost(Failure(ConnectionLost("The end.")))
        req.write(b"foobar")
        self.assertRaises(RuntimeError, req.finish)

    def test_twisted_version(self):

        self.assertLess(
            (twisted_version.major, twisted_version.minor),
            (19, 7),
            "The fix_twisted_disconnect_write monkey patch is not longer "
            "required in Twisted versions >= 19.7.0",
        )
