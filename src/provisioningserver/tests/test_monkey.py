# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test monkey patches."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    ]


import sys

from maastesting.testcase import MAASTestCase
from mock import sentinel
from provisioningserver.monkey import (
    add_term_error_code_to_tftp,
    force_simplestreams_to_use_urllib2,
)
from simplestreams import contentsource
import tftp.datagram


if sys.version_info > (3, 0):
    import urllib.request as urllib_request
    import urllib.error as urllib_error
else:
    import urllib2 as urllib_request
    urllib_error = urllib_request


class TestForceSimplestreamsToUseUrllib2Events(MAASTestCase):

    scenarios = (
        ('URL_READER',
            {
                'value': contentsource.Urllib2UrlReader,
                'key': 'URL_READER',
            }),
        ('URL_READER_CLASSNAME',
            {
                'value': 'Urllib2UrlReader',
                'key': 'URL_READER_CLASSNAME',
            }),
        ('urllib_error',
            {
                'value': urllib_error,
                'key': 'urllib_error',
            }),
        ('urllib_request',
            {
                'value': urllib_request,
                'key': 'urllib_request',
            }),
    )

    def test_replaces_urlreader_object(self):
        self.patch(contentsource, self.key, sentinel.pre_value)
        force_simplestreams_to_use_urllib2()
        self.assertEqual(
            self.value, getattr(contentsource, self.key))


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
