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
from provisioningserver.monkey import force_simplestreams_to_use_urllib2
from simplestreams import contentsource


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
