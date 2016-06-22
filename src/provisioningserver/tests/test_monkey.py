# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test monkey patches."""

__all__ = [
    ]


import sys
from unittest.mock import sentinel

from maastesting.testcase import MAASTestCase
from provisioningserver.monkey import add_term_error_code_to_tftp
import tftp.datagram


if sys.version_info > (3, 0):
    import urllib.request as urllib_request
    import urllib.error as urllib_error
else:
    import urllib2 as urllib_request
    urllib_error = urllib_request


class TestAddTermErrorCodeToTFT(MAASTestCase):

    def test_adds_error_code_8(self):
        self.patch(tftp.datagram, 'errors', {})
        add_term_error_code_to_tftp()
        self.assertIn(8, tftp.datagram.errors)
        self.assertEqual(
            "Terminate transfer due to option negotiation",
            tftp.datagram.errors.get(8))

    def test_skips_adding_error_code_if_already_present(self):
        self.patch(tftp.datagram, 'errors', {8: sentinel.error_8})
        add_term_error_code_to_tftp()
        self.assertEqual(
            sentinel.error_8, tftp.datagram.errors.get(8))
